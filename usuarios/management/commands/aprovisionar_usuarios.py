import csv
import os
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string

from directorio.models import Funcionario, dividir_nombre_chileno
from usuarios.models import Usuario

RUT_SUPER_ADMIN = "20026280-8"

# Caracteres usados para generar contraseñas aleatorias (letras y números,
# sin caracteres ambiguos como 0/O o 1/l).
ALFABETO_PASSWORD = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generar_password(largo=12):
    return get_random_string(largo, allowed_chars=ALFABETO_PASSWORD)


class Command(BaseCommand):
    help = (
        "Crea la cuenta de super admin (vinculada a su Funcionario) y una cuenta "
        "con contraseña aleatoria individual (debe cambiarla al entrar) para cada "
        "Funcionario que todavía no tenga usuario de acceso."
    )

    def handle(self, *args, **options):
        super_admin, creado = Usuario.objects.update_or_create(
            username=RUT_SUPER_ADMIN,
            # "admin" ya no está en Usuario.Rol (se sacó del desplegable de Rol en
            # el panel de Usuarios), pero sigue siendo un valor válido guardado a
            # mano acá: los chequeos de permisos en comunicados/rrhh/directorio
            # siguen comparando contra el string "admin" directamente.
            defaults={"rol": "admin", "is_staff": True, "is_superuser": True, "debe_cambiar_password": False},
        )

        # La contraseña del super admin solo se fija (o se rota) cuando la
        # cuenta recién se crea, o si se pasa SUPERADMIN_PASSWORD a propósito.
        # NOTA: la contraseña anterior ("Olivar.2026") quedó expuesta en el
        # código fuente y debe considerarse comprometida; si ya se usó en
        # algún ambiente, rótala manualmente desde el panel de Usuarios.
        password_env = os.environ.get("SUPERADMIN_PASSWORD")
        if creado or password_env:
            password_admin = password_env or generar_password(14)
            super_admin.set_password(password_admin)
            if not password_env:
                self.stdout.write(self.style.WARNING(
                    f"Contraseña generada para el super admin ({super_admin.username}): {password_admin}\n"
                    "Guárdala ahora por un canal seguro: no queda registrada en ningún archivo."
                ))

        funcionario_admin = Funcionario.objects.filter(rut=RUT_SUPER_ADMIN).first()
        if funcionario_admin:
            super_admin.first_name, super_admin.last_name = dividir_nombre_chileno(funcionario_admin.nombre_completo)
            funcionario_admin.usuario = super_admin
            funcionario_admin.save(update_fields=["usuario"])
        super_admin.save()

        self.stdout.write(self.style.SUCCESS(
            f"{'Creado' if creado else 'Actualizado'} super admin: {super_admin.username}"
        ))

        credenciales_nuevas = []
        for funcionario in Funcionario.objects.filter(usuario__isnull=True).exclude(rut=RUT_SUPER_ADMIN):
            nombres, apellidos = dividir_nombre_chileno(funcionario.nombre_completo)
            password_generada = generar_password(10)
            usuario = Usuario.objects.create(
                username=funcionario.rut,
                first_name=nombres,
                last_name=apellidos,
                email=funcionario.email,
                rol=Usuario.Rol.FUNCIONARIO,
                debe_cambiar_password=True,
            )
            usuario.set_password(password_generada)
            usuario.save()
            funcionario.usuario = usuario
            funcionario.save(update_fields=["usuario"])
            credenciales_nuevas.append((funcionario.rut, password_generada))

        self.stdout.write(self.style.SUCCESS(f"Cuentas nuevas creadas: {len(credenciales_nuevas)}"))

        if credenciales_nuevas:
            carpeta = settings.BASE_DIR / "data_privada"
            carpeta.mkdir(exist_ok=True)
            marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
            archivo_csv = carpeta / f"credenciales_nuevas_{marca_tiempo}.csv"
            with open(archivo_csv, "w", newline="", encoding="utf-8") as f:
                escritor = csv.writer(f)
                escritor.writerow(["rut", "password_inicial"])
                escritor.writerows(credenciales_nuevas)

            self.stdout.write(self.style.WARNING(
                f"Contraseñas iniciales guardadas en: {archivo_csv}\n"
                "Ese archivo queda fuera del repo (data_privada/ está en .gitignore). "
                "Entrégalas a RRHH por un canal seguro y luego elimina el archivo."
            ))
