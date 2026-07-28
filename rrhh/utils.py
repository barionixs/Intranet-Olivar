"""Cálculos que se derivan de otros datos en vez de guardarse aparte
(así nadie tiene que actualizarlos a mano): antigüedad y saldo de
vacaciones. El saldo es una ESTIMACIÓN legal simplificada — se muestra
siempre con una advertencia para que se confirme con RRHH."""

from datetime import date, timedelta

from .models import FichaLaboral, SolicitudPermiso


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


# --- Aprobación de jefatura ------------------------------------------------
# Es solo un VALIDADOR dentro del sistema: la jefatura marca la solicitud
# como aprobada/rechazada con un clic (queda registrado quién y cuándo),
# sin firma digital ni electrónica de por medio.

def es_jefatura(user):
    """True si esta persona encabeza al menos un departamento (sin
    importar su `rol`) — eso es lo que determina de quién puede ver
    y resolver solicitudes, no la etiqueta de rol."""
    funcionario = getattr(user, "funcionario", None)
    return bool(funcionario and funcionario.departamentos_a_cargo.exists())


def puede_gestionar_solicitudes(user):
    """RRHH/admin gestionan las de cualquiera; una jefatura solo las
    de su propio departamento."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.rol in ("admin", "rrhh"):
        return True
    return es_jefatura(user)


def solicitudes_gestionables(user):
    """Cola de solicitudes que esta persona puede ver/resolver."""
    qs = SolicitudPermiso.objects.select_related("funcionario", "funcionario__departamento")
    if user.is_superuser or user.rol in ("admin", "rrhh"):
        return qs
    funcionario = getattr(user, "funcionario", None)
    if not funcionario:
        return qs.none()
    return qs.filter(funcionario__departamento__jefe=funcionario)


def puede_gestionar_esta_solicitud(user, solicitud):
    """Igual que solicitudes_gestionables pero para un solo objeto —
    se usa para verificar en el momento de aprobar/rechazar, sin
    confiar solo en que la lista ya vino filtrada."""
    if user.is_superuser or user.rol in ("admin", "rrhh"):
        return True
    funcionario = getattr(user, "funcionario", None)
    return bool(funcionario) and solicitud.funcionario.departamento.jefe_id == funcionario.id
