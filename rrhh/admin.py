from django.contrib import admin

from .models import (
    CargoUnico,
    DocumentoPersonal,
    FichaLaboral,
    FirmaSolicitud,
    LicenciaMedica,
    LiquidacionSueldo,
    SolicitudPermiso,
)


@admin.register(FichaLaboral)
class FichaLaboralAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "tipo_contrato", "fecha_ingreso", "grado")
    list_filter = ("tipo_contrato",)
    search_fields = ("funcionario__nombre_completo", "funcionario__rut")
    autocomplete_fields = ("funcionario",)


@admin.register(SolicitudPermiso)
class SolicitudPermisoAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "tipo", "fecha_inicio", "fecha_termino", "dias_solicitados", "estado")
    list_filter = ("tipo", "estado")
    search_fields = ("funcionario__nombre_completo", "funcionario__rut")
    autocomplete_fields = ("funcionario",)


@admin.register(LicenciaMedica)
class LicenciaMedicaAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "fecha_inicio", "fecha_termino", "dias", "estado")
    list_filter = ("estado",)
    search_fields = ("funcionario__nombre_completo", "funcionario__rut", "folio")
    autocomplete_fields = ("funcionario",)


@admin.register(LiquidacionSueldo)
class LiquidacionSueldoAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "mes", "anio", "fecha_carga", "subido_por")
    list_filter = ("anio", "mes")
    search_fields = ("funcionario__nombre_completo", "funcionario__rut")
    autocomplete_fields = ("funcionario",)


@admin.register(DocumentoPersonal)
class DocumentoPersonalAdmin(admin.ModelAdmin):
    list_display = ("funcionario", "categoria", "nombre", "fecha_subida", "subido_por")
    list_filter = ("categoria",)
    search_fields = ("funcionario__nombre_completo", "funcionario__rut", "nombre")
    autocomplete_fields = ("funcionario",)


@admin.register(CargoUnico)
class CargoUnicoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "funcionario")
    autocomplete_fields = ("funcionario",)


@admin.register(FirmaSolicitud)
class FirmaSolicitudAdmin(admin.ModelAdmin):
    list_display = ("solicitud", "orden", "rol_firmante", "funcionario_firmante", "estado", "fecha_firma")
    list_filter = ("rol_firmante", "estado")
    search_fields = ("solicitud__funcionario__nombre_completo", "funcionario_firmante__nombre_completo")
    autocomplete_fields = ("funcionario_firmante",)
