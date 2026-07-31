from django.conf import settings
from django.db import models

from directorio.models import Funcionario

# Todos los modelos de esta app cuelgan de Funcionario (no de Usuario):
# así la ficha, permisos, licencias, liquidaciones y documentos quedan
# ligados al RUT de la persona aunque todavía no tenga cuenta de acceso,
# o si el día de mañana cambia de cuenta.
#
# Privacidad: igual que rut/fecha_nacimiento en Funcionario, estos datos
# (sueldo, salud, contrato) solo deben mostrarse al propio funcionario y a
# RRHH/admin — nunca en vistas públicas ni API sin autenticación. Todavía
# no hay vistas para esto (se agregan cuando se defina el ingreso de datos).


class FichaLaboral(models.Model):
    """Datos contractuales del funcionario. Es aparte de Funcionario
    (que es más bien el dato "de directorio") porque esta información
    es sensible y de uso exclusivo de RRHH/admin/el propio funcionario."""

    class TipoContrato(models.TextChoices):
        PLANTA = "planta", "Planta"
        CONTRATA = "contrata", "Contrata"
        HONORARIOS = "honorarios", "Honorarios"
        CODIGO_TRABAJO = "codigo_trabajo", "Código del Trabajo"

    funcionario = models.OneToOneField(
        Funcionario, on_delete=models.CASCADE, related_name="ficha_laboral"
    )
    tipo_contrato = models.CharField(max_length=20, choices=TipoContrato.choices)
    fecha_ingreso = models.DateField()
    grado = models.CharField(max_length=20, blank=True, help_text="Grado EUS, si corresponde.")
    jornada = models.CharField(max_length=100, blank=True, help_text='Ej: "44 horas semanales".')
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Ficha laboral"
        verbose_name_plural = "Fichas laborales"

    def __str__(self):
        return f"Ficha laboral de {self.funcionario}"


class SolicitudPermiso(models.Model):
    """Vacaciones y días administrativos comparten la misma forma
    (rango de fechas + aprobación de jefatura), así que usan un solo
    modelo con un campo `tipo` en vez de duplicar la estructura."""

    class Tipo(models.TextChoices):
        VACACIONES = "vacaciones", "Vacaciones"
        ADMINISTRATIVO = "administrativo", "Día administrativo"
        SIN_GOCE = "sin_goce", "Permiso sin goce de sueldo"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name="permisos")
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    fecha_inicio = models.DateField()
    fecha_termino = models.DateField()
    dias_solicitados = models.PositiveSmallIntegerField()
    motivo = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="permisos_aprobados",
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_solicitud"]
        verbose_name = "Solicitud de permiso"
        verbose_name_plural = "Solicitudes de permiso"

    def __str__(self):
        return f"{self.get_tipo_display()} de {self.funcionario} ({self.fecha_inicio} a {self.fecha_termino})"


class CargoUnico(models.Model):
    """Cargos que solo tiene UNA persona en toda la municipalidad y que
    firman solicitudes sin importar el departamento del solicitante
    (Jefa de Personal, Alcaldesa). Configuración, no código: si cambia
    la persona en el cargo, se actualiza esta fila, no el código. Si
    queda sin `funcionario` asignado, solo bloquea ESE paso de firma,
    no el sistema completo."""

    class Nombre(models.TextChoices):
        JEFA_PERSONAL = "jefa_personal", "Jefa de Personal"
        ALCALDESA = "alcaldesa", "Alcaldesa"

    nombre = models.CharField(max_length=50, choices=Nombre.choices, unique=True)
    funcionario = models.ForeignKey(
        Funcionario, null=True, blank=True, on_delete=models.SET_NULL, related_name="cargos_unicos"
    )

    class Meta:
        verbose_name = "Cargo único"
        verbose_name_plural = "Cargos únicos"

    def __str__(self):
        return f"{self.get_nombre_display()}: {self.funcionario or 'sin asignar'}"


class FirmaSolicitud(models.Model):
    """Un registro de firma por cada uno de los 4 firmantes de una
    SolicitudPermiso (interesado, Jefa de Personal, jefatura directa,
    Alcaldesa). Firma electrónica SIMPLE (Ley 19.799): no usa
    certificador acreditado, la atribución a la persona se logra
    pidiendo la contraseña de nuevo al momento de firmar (no basta la
    sesión activa) + hash del contenido + IP + timestamp."""

    class RolFirmante(models.TextChoices):
        INTERESADO = "interesado", "Interesado"
        JEFA_PERSONAL = "jefa_personal", "Jefa de Personal"
        JEFATURA_DIRECTA = "jefatura_directa", "Jefatura directa"
        ALCALDESA = "alcaldesa", "Alcaldesa"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        FIRMADO = "firmado", "Firmado"
        RECHAZADO = "rechazado", "Rechazado"

    solicitud = models.ForeignKey(SolicitudPermiso, related_name="firmas", on_delete=models.CASCADE)
    orden = models.PositiveSmallIntegerField(help_text="1 a 4: orden en que debe firmarse.")
    rol_firmante = models.CharField(max_length=20, choices=RolFirmante.choices)
    funcionario_firmante = models.ForeignKey(
        Funcionario, null=True, blank=True, on_delete=models.SET_NULL, related_name="firmas"
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha_firma = models.DateTimeField(null=True, blank=True)
    ip_firma = models.GenericIPAddressField(null=True, blank=True)
    hash_documento = models.CharField(
        max_length=64, blank=True, help_text="sha256 del contenido de la solicitud al momento de firmar."
    )
    comentario = models.TextField(blank=True)

    class Meta:
        ordering = ["solicitud", "orden"]
        unique_together = ("solicitud", "orden")
        verbose_name = "Firma de solicitud"
        verbose_name_plural = "Firmas de solicitud"

    def __str__(self):
        return f"Firma {self.orden} ({self.get_rol_firmante_display()}) de {self.solicitud}"


class LicenciaMedica(models.Model):
    """A diferencia de SolicitudPermiso, una licencia médica no la
    aprueba la jefatura: la emite un médico y RRHH solo la registra."""

    class Estado(models.TextChoices):
        REGISTRADA = "registrada", "Registrada"
        EN_TRAMITE = "en_tramite", "En trámite (Compin/Isapre)"
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name="licencias_medicas")
    folio = models.CharField(max_length=50, blank=True, help_text="Número de licencia, si viene en el documento.")
    fecha_inicio = models.DateField()
    fecha_termino = models.DateField()
    dias = models.PositiveSmallIntegerField()
    documento = models.FileField(upload_to="licencias_medicas/%Y/%m/", blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.REGISTRADA)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_inicio"]
        verbose_name = "Licencia médica"
        verbose_name_plural = "Licencias médicas"

    def __str__(self):
        return f"Licencia médica de {self.funcionario} ({self.fecha_inicio} a {self.fecha_termino})"


class LiquidacionSueldo(models.Model):
    MESES = [
        (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
        (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
        (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
    ]

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name="liquidaciones")
    anio = models.PositiveSmallIntegerField()
    mes = models.PositiveSmallIntegerField(choices=MESES)
    archivo = models.FileField(upload_to="liquidaciones/%Y/")
    fecha_carga = models.DateTimeField(auto_now_add=True)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="liquidaciones_subidas"
    )

    class Meta:
        ordering = ["-anio", "-mes"]
        unique_together = ("funcionario", "anio", "mes")
        verbose_name = "Liquidación de sueldo"
        verbose_name_plural = "Liquidaciones de sueldo"

    def __str__(self):
        return f"Liquidación {self.get_mes_display()} {self.anio} — {self.funcionario}"


class DocumentoPersonal(models.Model):
    class Categoria(models.TextChoices):
        CEDULA_IDENTIDAD = "cedula_identidad", "Cédula de identidad"
        CONTRATO = "contrato", "Contrato / anexo"
        TITULO = "titulo", "Título o certificado de estudios"
        CERTIFICADO = "certificado", "Certificado (antigüedad, tipo de contrato, etc.)"
        CERTIFICADO_RENTA = "certificado_renta", "Certificado de renta"
        OTRO = "otro", "Otro"

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name="documentos_personales")
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    nombre = models.CharField(max_length=150, help_text="Ej: “Contrato 2026”, “Título Ingeniería”.")
    archivo = models.FileField(upload_to="documentos_personales/%Y/")
    fecha_subida = models.DateTimeField(auto_now_add=True)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="documentos_subidos"
    )

    class Meta:
        ordering = ["-fecha_subida"]
        verbose_name = "Documento personal"
        verbose_name_plural = "Documentos personales"

    def __str__(self):
        return f"{self.nombre} ({self.funcionario})"
