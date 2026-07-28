from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from comunicados.models import Comunicado
from directorio.models import MESES_ES, Funcionario

from .forms import UsuarioCreacionForm, UsuarioEdicionForm
from .models import Usuario


class InicioView(LoginRequiredMixin, TemplateView):
    template_name = "inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["comunicados_recientes"] = Comunicado.objects.select_related("autor")[:5]

        hoy = date.today()
        contexto["mes_actual_nombre"] = MESES_ES[hoy.month - 1]
        contexto["dia_hoy"] = hoy.day
        cumpleañeros = list(Funcionario.objects.cumpleañeros_del_mes(hoy.month))
        for persona in cumpleañeros:
            persona.mostrar_anio = persona.puede_ver_datos_sensibles(self.request.user)
        contexto["cumpleañeros_mes"] = cumpleañeros
        return contexto


class SoloAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe la vista a usuarios con rol admin (o superusuario de Django)."""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or user.rol == Usuario.Rol.ADMIN)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "No tienes permiso para acceder a esa sección.")
        return redirect("inicio")


class UsuarioListView(SoloAdminMixin, ListView):
    model = Usuario
    template_name = "usuarios/lista.html"
    context_object_name = "usuarios"
    paginate_by = 25

    def get_queryset(self):
        qs = Usuario.objects.all().order_by("first_name", "last_name", "username")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "")
        return contexto


class UsuarioCreateView(SoloAdminMixin, CreateView):
    model = Usuario
    form_class = UsuarioCreacionForm
    template_name = "usuarios/formulario.html"
    success_url = reverse_lazy("usuarios:lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Cuenta creada para {self.object}.")
        return respuesta


class UsuarioUpdateView(SoloAdminMixin, UpdateView):
    model = Usuario
    form_class = UsuarioEdicionForm
    template_name = "usuarios/formulario.html"
    success_url = reverse_lazy("usuarios:lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Datos de {self.object} actualizados.")
        return respuesta


class UsuarioDeleteView(SoloAdminMixin, DeleteView):
    model = Usuario
    template_name = "usuarios/confirmar_eliminar.html"
    success_url = reverse_lazy("usuarios:lista")
    context_object_name = "usuario_objetivo"

    def post(self, request, *args, **kwargs):
        usuario_objetivo = self.get_object()
        if usuario_objetivo == request.user:
            messages.error(request, "No puedes eliminar tu propia cuenta.")
            return redirect("usuarios:lista")
        try:
            respuesta = super().post(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                f"No se puede eliminar a {usuario_objetivo}: tiene registros asociados "
                "(por ejemplo, comunicados publicados). Desactiva la cuenta en vez de eliminarla.",
            )
            return redirect("usuarios:lista")
        messages.success(request, f"Cuenta de {usuario_objetivo} eliminada.")
        return respuesta


class CambiarPasswordObligatorioView(LoginRequiredMixin, PasswordChangeView):
    template_name = "usuarios/cambiar_password.html"
    success_url = reverse_lazy("inicio")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        self.request.user.debe_cambiar_password = False
        self.request.user.save(update_fields=["debe_cambiar_password"])
        messages.success(self.request, "Contraseña actualizada.")
        return respuesta
