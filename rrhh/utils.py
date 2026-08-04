"""Cálculos que se derivan de otros datos en vez de guardarse aparte
(así nadie tiene que actualizarlos a mano): antigüedad y saldo de
vacaciones. El saldo es una ESTIMACIÓN legal simplificada — se muestra
siempre con una advertencia para que se confirme con RRHH."""

import hashlib
import io
from datetime import date, timedelta

from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from .models import CargoUnico, FichaLaboral, FirmaSolicitud, SolicitudPermiso


def calcular_antiguedad(fecha_ingreso, hoy=None):
    """Retorna (años, meses) completos entre fecha_ingreso y hoy."""
    hoy = hoy or date.today()
    años = hoy.year - fecha_ingreso.year
    meses = hoy.month - fecha_ingreso.month
    if hoy.day < fecha_ingreso.day:
        meses -= 1
    if meses < 0:
        años -= 1
        meses += 12
    return max(años, 0), max(meses, 0)


def _dias_legales_por_año(tipo_contrato, años_antiguedad):
    """Días hábiles de feriado legal por año, según tipo de contrato.
    Aproximación:
    - Honorarios: sin derecho legal a vacaciones (0).
    - Planta/Contrata (Estatuto Administrativo, Ley 18.834 art. 103):
      15 días con <15 años, 20 días con 15-19 años, 25 días con 20+ años.
    - Código del Trabajo (art. 68): 15 días base + 1 día extra por cada
      3 años trabajados para el mismo empleador después de 10 años."""
    if tipo_contrato == FichaLaboral.TipoContrato.HONORARIOS:
        return 0
    if tipo_contrato == FichaLaboral.TipoContrato.CODIGO_TRABAJO:
        extra = max(0, (años_antiguedad - 10) // 3)
        return 15 + extra
    # Planta o Contrata
    if años_antiguedad >= 20:
        return 25
    if años_antiguedad >= 15:
        return 20
    return 15


def calcular_saldo_vacaciones(funcionario):
    """Devuelve un dict con la estimación de saldo de vacaciones, o
    None si el funcionario no tiene ficha laboral cargada todavía.

    El feriado legal es un derecho ANUAL, no algo que se acumula sin
    límite con los años trabajados — por eso "correspondientes" es el
    cupo del período actual (últimos 12 meses), no la tasa multiplicada
    por toda la antigüedad (eso daría números absurdos, ej. 100+ días)."""
    try:
        ficha = funcionario.ficha_laboral
    except FichaLaboral.DoesNotExist:
        return None

    años, _ = calcular_antiguedad(ficha.fecha_ingreso)
    dias_por_año = _dias_legales_por_año(ficha.tipo_contrato, años)

    hace_un_año = date.today() - timedelta(days=365)
    usados = SolicitudPermiso.objects.filter(
        funcionario=funcionario,
        tipo=SolicitudPermiso.Tipo.VACACIONES,
        estado=SolicitudPermiso.Estado.APROBADO,
        fecha_inicio__gte=hace_un_año,
    ).values_list("dias_solicitados", flat=True)
    usados_total = sum(usados)

    return {
        "dias_por_año": dias_por_año,
        "correspondientes": dias_por_año,
        "usados": usados_total,
        "saldo": dias_por_año - usados_total,
    }


# --- Firma electrónica simple (Ley 19.799) ----------------------------------
# Cada SolicitudPermiso lleva 3 firmas en orden: interesado, jefatura
# directa, Alcaldesa. No es firma avanzada ni usa certificador
# acreditado — la atribución razonable a la persona se logra pidiendo
# la contraseña de nuevo al firmar (no basta la sesión activa) + hash
# del contenido + IP + timestamp, registrado en FirmaSolicitud.

def resolver_jefatura_directa(funcionario):
    """Asignación directa, sin cadenas ni niveles de cargo: si esta
    persona tiene un `jefe_directo` asignado a mano (excepción, ej.
    Norma Vidal), ese es el firmante — sin seguir subiendo más allá.
    Si no, se usa el Jefe de su departamento (o el del departamento
    padre si el suyo no tiene uno propio, un solo salto por nivel,
    tal como está armado el organigrama). Devuelve None si nada de
    esto está configurado todavía — hay que bloquear el envío de la
    solicitud con un mensaje claro, no es un error real."""
    if funcionario.jefe_directo_id:
        return funcionario.jefe_directo
    depto = funcionario.departamento
    visitados = set()
    while depto and depto.id not in visitados:
        if depto.jefe_id and depto.jefe_id != funcionario.id:
            return depto.jefe
        visitados.add(depto.id)
        depto = depto.departamento_padre
    return None


def hash_solicitud(solicitud):
    """sha256 de los campos que definen QUÉ se está firmando. No incluye
    `estado` (cambia después de firmar) ni fecha_solicitud/fecha_resolucion
    (metadata, no contenido) — así la firma queda ligada a la versión
    exacta de la solicitud en ese momento."""
    campos = "|".join(str(v) for v in [
        solicitud.pk,
        solicitud.funcionario_id,
        solicitud.tipo,
        solicitud.fecha_inicio,
        solicitud.fecha_termino,
        solicitud.dias_solicitados,
        solicitud.motivo,
    ])
    return hashlib.sha256(campos.encode("utf-8")).hexdigest()


def obtener_ip_cliente(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def hash_firma(firma):
    """sha256 de ESTA firma en particular, no solo del documento: liga
    el hash del contenido a quién firmó, cuándo y desde qué IP. Sin
    esto, las 3 firmas de una misma solicitud (interesado, jefatura,
    Alcaldesa) tendrían el mismo hash por firmar el mismo documento —
    correcto para probar que todos vieron la misma versión, pero no
    sirve para distinguir una firma de otra. Requiere que `fecha_firma`
    e `ip_firma` ya estén asignados en la instancia antes de llamarla."""
    campos = "|".join(str(v) for v in [
        hash_solicitud(firma.solicitud),
        firma.funcionario_firmante_id,
        firma.fecha_firma,
        firma.ip_firma,
    ])
    return hashlib.sha256(campos.encode("utf-8")).hexdigest()


def crear_firmas_para_solicitud(solicitud):
    """Genera las 3 FirmaSolicitud pendientes al crear una solicitud.
    El cargo único (Alcaldesa) puede no tener funcionario asignado
    todavía — esa firma queda pendiente sin firmante hasta que se
    configure, sin bloquear el resto."""
    alcaldesa = CargoUnico.objects.filter(nombre=CargoUnico.Nombre.ALCALDESA).first()
    jefatura_directa = resolver_jefatura_directa(solicitud.funcionario)

    pasos = [
        (1, FirmaSolicitud.RolFirmante.INTERESADO, solicitud.funcionario),
        (2, FirmaSolicitud.RolFirmante.JEFATURA_DIRECTA, jefatura_directa),
        (3, FirmaSolicitud.RolFirmante.ALCALDESA, alcaldesa.funcionario if alcaldesa else None),
    ]
    FirmaSolicitud.objects.bulk_create([
        FirmaSolicitud(solicitud=solicitud, orden=orden, rol_firmante=rol, funcionario_firmante=firmante)
        for orden, rol, firmante in pasos
    ])


def generar_comprobante_firma(solicitud):
    """PDF de respaldo/auditoría con el detalle de las 4 firmas (no es
    la firma en sí, esa ya quedó registrada en cada FirmaSolicitud).
    Se genera una sola vez, al momento exacto en que la solicitud
    queda aprobada."""
    firmas = list(
        solicitud.firmas.select_related("funcionario_firmante").order_by("orden")
    )
    html = render_to_string(
        "rrhh/comprobante_firma.html", {"solicitud": solicitud, "firmas": firmas}
    )
    buffer = io.BytesIO()
    resultado = pisa.CreatePDF(src=html, dest=buffer)
    if resultado.err:
        return
    solicitud.comprobante_firma.save(
        f"solicitud_{solicitud.pk}.pdf", ContentFile(buffer.getvalue()), save=True
    )


def actualizar_estado_solicitud(solicitud):
    """El estado de la solicitud es derivado de sus firmas, no se
    setea a mano: todas firmadas -> aprobada; alguna rechazada ->
    rechazada; si no, sigue pendiente."""
    firmas = list(solicitud.firmas.all())
    if any(f.estado == FirmaSolicitud.Estado.RECHAZADO for f in firmas):
        nuevo_estado = SolicitudPermiso.Estado.RECHAZADO
    elif firmas and all(f.estado == FirmaSolicitud.Estado.FIRMADO for f in firmas):
        nuevo_estado = SolicitudPermiso.Estado.APROBADO
    else:
        nuevo_estado = SolicitudPermiso.Estado.PENDIENTE
    if solicitud.estado != nuevo_estado:
        solicitud.estado = nuevo_estado
        solicitud.save(update_fields=["estado"])
        if nuevo_estado == SolicitudPermiso.Estado.APROBADO:
            generar_comprobante_firma(solicitud)


def es_su_turno(firma):
    """Una firma solo se puede resolver si todos los pasos anteriores
    (menor `orden`) ya están firmados — no se puede firmar fuera de
    orden."""
    return not firma.solicitud.firmas.filter(orden__lt=firma.orden).exclude(
        estado=FirmaSolicitud.Estado.FIRMADO
    ).exists()


def puede_firmar(user, firma):
    """Solo la persona exacta asignada a esa firma puede firmarla —
    a propósito, sin bypass de superusuario/admin: si un tercero
    pudiera firmar por otro, dejaría de ser una firma electrónica
    válida bajo la Ley 19.799 (no se podría atribuir razonablemente
    el acto a la persona)."""
    return bool(firma.funcionario_firmante) and firma.funcionario_firmante.usuario_id == user.id


def puede_gestionar_solicitudes(user):
    """Determina si se muestra el ítem 'Aprobaciones' en la navegación:
    RRHH/admin/superuser siempre (ven todo), o cualquiera que participe
    como firmante de al menos una solicitud."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.rol in ("admin", "rrhh"):
        return True
    funcionario = getattr(user, "funcionario", None)
    return bool(funcionario and funcionario.firmas.exists())


def firmas_visibles_para(user):
    """Bandeja de firmas: RRHH/admin/superuser ven todas (supervisión);
    el resto solo las suyas."""
    qs = FirmaSolicitud.objects.select_related(
        "solicitud", "solicitud__funcionario", "solicitud__funcionario__departamento", "funcionario_firmante"
    )
    if user.is_superuser or user.rol in ("admin", "rrhh"):
        return qs
    funcionario = getattr(user, "funcionario", None)
    if not funcionario:
        return qs.none()
    return qs.filter(funcionario_firmante=funcionario)
