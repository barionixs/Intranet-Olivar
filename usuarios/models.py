from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Usuario de la intranet. Reemplaza al User por defecto de Django
    para poder agregarle el campo `rol`, usado en todos los permisos
    de la intranet (directorio, comunicados, RRHH, documentos)."""

    class Rol(models.TextChoices):
        FUNCIONARIO = "funcionario", "Funcionario"
        JEFATURA = "jefatura", "Jefatura"
        RRHH = "rrhh", "RRHH"
        ADMIN = "admin", "Administrador"

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.FUNCIONARIO)
    debe_cambiar_password = models.BooleanField(
        default=True,
        help_text="Si está activo, se le pide cambiar la clave apenas inicia sesión "
        "(se usa para las cuentas creadas con la clave genérica).",
    )

    def __str__(self):
        return self.get_full_name() or self.username
