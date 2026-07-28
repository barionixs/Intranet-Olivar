from django.conf import settings
from django.db import models
from django.db.models.functions import ExtractDay

MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


class FuncionarioManager(models.Manager):
    def cumpleañeros_del_mes(self, mes):
        return (
            self.filter(fecha_nacimiento__month=mes)
            .annotate(dia=ExtractDay("fecha_nacimiento"))
            .order_by("dia")
            .select_related("departamento")
        )


class Departamento(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    departamento_padre = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subdepartamentos",
        help_text="Dejar vacío si es un departamento de primer nivel. "
        "Ajustar una vez que se cargue el organigrama oficial.",
    )
    jefe = models.ForeignKey(
        "Funcionario",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="departamentos_a_cargo",
        help_text="Jefatura directa de este departamento. Pendiente de completar con el organigrama oficial.",
    )

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Departamento"
        verbose_name_plural = "Departamentos"

    def __str__(self):
        return self.nombre


class Funcionario(models.Model):
    class Cargo(models.TextChoices):
        FUNCIONARIO = "funcionario", "Funcionario"
        JEFE = "jefe", "Jefe"
        DIRECTOR = "director", "Director"

    nombre_completo = models.CharField(max_length=200)
    rut = models.CharField(max_length=12, unique=True)
    cargo = models.CharField(max_length=150, choices=Cargo.choices, blank=True)
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT, related_name="funcionarios"
    )
    fecha_nacimiento = models.DateField()
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="funcionario",
        help_text="Se completa cuando la persona recibe su cuenta de acceso a la intranet.",
    )

    objects = FuncionarioManager()

    class Meta:
        ordering = ["nombre_completo"]
        verbose_name = "Funcionario"
        verbose_name_plural = "Funcionarios"

    def __str__(self):
        return self.nombre_completo

    def puede_ver_datos_sensibles(self, user):
        """RUT y fecha de nacimiento completa: solo RRHH, admin o la
        propia persona. Se usa en cualquier vista que muestre estos
        campos (directorio, ficha laboral, etc.), nunca se exponen
        directamente en una plantilla sin pasar por acá."""
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.rol in ("admin", "rrhh"):
            return True
        return self.usuario_id is not None and self.usuario_id == user.id
