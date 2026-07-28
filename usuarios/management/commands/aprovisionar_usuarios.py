from django.core.management.base import BaseCommand

from directorio.models import Funcionario
from usuarios.models import Usuario

RUT_SUPER_ADMIN = "20026280-8"
PASSWORD_SUPER_ADMIN = "Olivar.2026"
PASSWORD_GENERICA = "123456"


class Command(BaseCommand):
    help = (
        "Crea la cuenta de super admin (vinculada a su Funcionario) y una cuenta "
        "genérica (clave 123456, debe cambiarla al entrar) para cada Funcionario "
        "que todavía no tenga usuario de acceso."
    )

    def handle(self, *args, **options):
        super_admin, creado = Usuario.objects.update_or_create(
            username=RUT_SUPER_ADMIN,
            defaults={"rol": Usuario.Rol.ADMIN, "is_staff": True, "is_superuser": True, "debe_cambiar_password": False},
        )
        super_admin.set_password(PASSWORD_SUPER_ADMIN)

        funcionario_admin = Funcionario.objects.filter(rut=RUT_SUPER_ADMIN).first()
        if funcionario_admin:
            super_admin.first_name = funcionario_admin.nombre_completo.split(" ")[0]
            super_admin.last_name = " ".join(funcionario_admin.nombre_completo.split(" ")[1:])
            funcionario_admin.usuario = super_admin
            funcionario_admin.save(update_fields=["usuario"])
        super_admin.save()

        self.stdout.write(self.style.SUCCESS(
            f"{'Creado' if creado else 'Actualizado'} super admin: {super_admin.username}"
        ))

        creados = 0
        for funcionario in Funcionario.objects.filter(usuario__isnull=True).exclude(rut=RUT_SUPER_ADMIN):
            partes = funcionario.nombre_completo.split(" ")
            usuario = Usuario.objects.create(
                username=funcionario.rut,
                first_name=partes[0],
                last_name=" ".join(partes[1:]),
                email=funcionario.email,
                rol=Usuario.Rol.FUNCIONARIO,
                debe_cambiar_password=True,
            )
            usuario.set_password(PASSWORD_GENERICA)
            usuario.save()
            funcionario.usuario = usuario
            funcionario.save(update_fields=["usuario"])
            creados += 1

        self.stdout.write(self.style.SUCCESS(f"Cuentas genéricas creadas: {creados}"))
