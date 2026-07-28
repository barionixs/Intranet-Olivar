from django.db import migrations

DEPARTAMENTOS = [
    "Alcaldía",
    "Administración Municipal",
    "SECPLAN",
    "Dirección de Administración y Finanzas",
    "Dirección de Obras",
    "Dirección de Control",
    "Jurídico",
    "DIDECO",
    "Operaciones",
    "Tránsito",
    "Juzgado de Policía Local",
    "OIRS",
    "CEDIAM",
    "Biblioteca",
    "Informática",
]


def crear_departamentos(apps, schema_editor):
    Departamento = apps.get_model("directorio", "Departamento")
    for nombre in DEPARTAMENTOS:
        Departamento.objects.get_or_create(nombre=nombre)


def eliminar_departamentos(apps, schema_editor):
    Departamento = apps.get_model("directorio", "Departamento")
    Departamento.objects.filter(nombre__in=DEPARTAMENTOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("directorio", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_departamentos, eliminar_departamentos),
    ]
