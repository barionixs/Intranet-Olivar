from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import ExtractDay

MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def dividir_nombre_chileno(nombre_completo):
    """`nombre_completo` viene de la nómina como "Apellido paterno,
    Apellido materno, Nombres" (orden chileno), no "Nombre, Apellido"
    como asume Django. Se asume que los primeros dos tokens son los
    apellidos y el resto son los nombres — funciona para la gran
    mayoría de los casos reales, salvo apellidos compuestos (ej.
    "San Juan"), que quedan mal y hay que corregirlos a mano."""
    tokens = nombre_completo.split()
    apellidos = " ".join(tokens[:2])
    nombres = " ".join(tokens[2:])
    return nombres, apellidos


class FuncionarioManager(models.Manager):
    def cumpleañeros_del_mes(self, mes):
        return (
            self.filter(fecha_nacimiento__month=mes)
            .annotate(dia=ExtractDay("fecha_nacimiento"))
            .order_by("dia")
            .select_related("departamento")
        )


def _sincronizar_rol_jefatura(funcionario_id):
    """El rol 'jefatura' de Usuario es un espejo de "¿esta persona
    encabeza al menos un Departamento?" (directorio manda). Sube a
    jefatura cuando corresponde, y la baja a funcionario cuando deja
    de encabezar algo — pero nunca toca cuentas admin/rrhh, esas se
    asignan a mano y son un nivel más alto que jefatura."""
    if not funcionario_id:
        return
    Usuario = get_user_model()
    funcionario = Funcionario.objects.filter(pk=funcionario_id).select_related("usuario").first()
    if not funcionario or not funcionario.usuario_id:
        return
    rol_actual = funcionario.usuario.rol
    es_jefe = funcionario.departamentos_a_cargo.exists()
    if es_jefe and rol_actual == Usuario.Rol.FUNCIONARIO:
        Usuario.objects.filter(pk=funcionario.usuario_id).update(rol=Usuario.Rol.JEFATURA)
    elif not es_jefe and rol_actual == Usuario.Rol.JEFATURA:
        Usuario.objects.filter(pk=funcionario.usuario_id).update(rol=Usuario.Rol.FUNCIONARIO)


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

    def save(self, *args, **kwargs):
        jefe_anterior_id = None
        if self.pk:
            jefe_anterior_id = (
                Departamento.objects.filter(pk=self.pk).values_list("jefe_id", flat=True).first()
            )
        super().save(*args, **kwargs)
        if jefe_anterior_id != self.jefe_id:
            _sincronizar_rol_jefatura(jefe_anterior_id)
            _sincronizar_rol_jefatura(self.jefe_id)

    def delete(self, *args, **kwargs):
        jefe_id = self.jefe_id
        resultado = super().delete(*args, **kwargs)
        _sincronizar_rol_jefatura(jefe_id)
        return resultado


class Funcionario(models.Model):
    class Cargo(models.TextChoices):
        FUNCIONARIO = "funcionario", "Funcionario"
        JEFE = "jefe", "Jefe"
        ENCARGADO = "encargado", "Encargado"
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
        on_delete=models.CASCADE,
        related_name="funcionario",
        help_text="Se completa cuando la persona recibe su cuenta de acceso a la intranet. "
        "Al eliminar la cuenta de usuario, esta ficha de directorio se elimina con ella.",
    )
    jefe_directo = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subordinados",
        help_text="Excepción manual: quién firma como 'jefatura directa' en las solicitudes de "
        "esta persona, si es distinto al jefe de su departamento (ej. unidades que dependen "
        "funcionalmente de otra dirección). Dejar vacío para usar el jefe del departamento.",
    )

    objects = FuncionarioManager()

    class Meta:
        ordering = ["nombre_completo"]
        verbose_name = "Funcionario"
        verbose_name_plural = "Funcionarios"

    def __str__(self):
        return self.nombre_completo

    def clean(self):
        super().clean()
        if self.jefe_directo_id and self.jefe_directo_id == self.id:
            raise ValidationError({"jefe_directo": "Una persona no puede ser jefe directo de sí misma."})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.usuario_id:
            nombres, apellidos = dividir_nombre_chileno(self.nombre_completo)
            get_user_model().objects.filter(pk=self.usuario_id).update(
                first_name=nombres,
                last_name=apellidos,
                email=self.email,
            )

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
