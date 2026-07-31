from django.contrib import admin

from .models import Departamento, Funcionario


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "departamento_padre", "jefe")
    search_fields = ("nombre",)
    autocomplete_fields = ("jefe", "departamento_padre")


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ("nombre_completo", "rut", "cargo", "departamento", "jefe_directo", "telefono", "usuario")
    list_filter = ("departamento",)
    search_fields = ("nombre_completo", "rut", "cargo")
    autocomplete_fields = ("departamento", "jefe_directo")
