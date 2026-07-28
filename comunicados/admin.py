from django.contrib import admin

from .models import Comunicado


@admin.register(Comunicado)
class ComunicadoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "autor", "fecha_publicacion", "destacado")
    list_filter = ("destacado",)
    search_fields = ("titulo", "cuerpo")
    date_hierarchy = "fecha_publicacion"
