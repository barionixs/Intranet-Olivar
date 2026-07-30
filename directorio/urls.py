from django.urls import path

from . import views

app_name = "directorio"

urlpatterns = [
    path("", views.DirectorioListView.as_view(), name="lista"),
    path("<int:pk>/", views.DirectorioDetalleView.as_view(), name="detalle"),
    path("<int:pk>/editar/", views.FuncionarioUpdateView.as_view(), name="editar"),
    path("<int:pk>/eliminar/", views.FuncionarioDeleteView.as_view(), name="eliminar"),
]
