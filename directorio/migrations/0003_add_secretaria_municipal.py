from django.db import migrations

NOMBRE = "Secretaría Municipal"


def crear(apps, schema_editor):
    Departamento = apps.get_model("directorio", "Departamento")
    Departamento.objects.get_or_create(nombre=NOMBRE)


def eliminar(apps, schema_editor):
    Departamento = apps.get_model("directorio", "Departamento")
    Departamento.objects.filter(nombre=NOMBRE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("directorio", "0002_seed_departamentos"),
    ]

    operations = [
        migrations.RunPython(crear, eliminar),
    ]
