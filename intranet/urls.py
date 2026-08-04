from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from rrhh.views import VerificarFirmaView
from usuarios.forms import LoginForm
from usuarios.views import CambiarPasswordObligatorioView, InicioView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='usuarios/login.html', authentication_form=LoginForm), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('cambiar-clave/', CambiarPasswordObligatorioView.as_view(), name='cambiar_clave_obligatorio'),
    path('verificar/<str:codigo>/', VerificarFirmaView.as_view(), name='verificar_firma'),
    path('usuarios/', include('usuarios.urls', namespace='usuarios')),
    path('directorio/', include('directorio.urls', namespace='directorio')),
    path('mi-ficha/', include('rrhh.urls', namespace='rrhh')),
    path('comunicados/', include('comunicados.urls', namespace='comunicados')),
    path('', InicioView.as_view(), name='inicio'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
