from django.urls import path

from . import views

app_name = "rrhh"

urlpatterns = [
    path("", views.MiFichaView.as_view(), name="mi_ficha"),
    path("solicitar/", views.SolicitudPermisoCreateView.as_view(), name="solicitar_permiso"),
    path("solicitudes/<int:pk>/", views.SolicitudDetalleView.as_view(), name="detalle_solicitud"),
    path(
        "solicitudes/<int:pk>/eliminar/",
        views.SolicitudPermisoDeleteView.as_view(),
        name="eliminar_solicitud",
    ),
    path(
        "solicitudes/<int:solicitud_id>/firmar/<int:orden>/",
        views.FirmarSolicitudView.as_view(),
        name="firmar_solicitud",
    ),
    path("aprobaciones/", views.AprobacionesListView.as_view(), name="aprobaciones"),
    path("panel-firmantes/", views.PanelFirmantesView.as_view(), name="panel_firmantes"),
]
