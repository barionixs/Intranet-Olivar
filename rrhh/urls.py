from django.urls import path

from . import views

app_name = "rrhh"

urlpatterns = [
    path("", views.MiFichaView.as_view(), name="mi_ficha"),
    path("solicitar/", views.SolicitudPermisoCreateView.as_view(), name="solicitar_permiso"),
    path("aprobaciones/", views.AprobacionesListView.as_view(), name="aprobaciones"),
    path("aprobaciones/<int:pk>/resolver/", views.ResolverSolicitudView.as_view(), name="resolver_solicitud"),
]
