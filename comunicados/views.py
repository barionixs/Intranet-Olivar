from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from directorio.models import MESES_ES, Funcionario

from .forms import ComunicadoForm
from .models import Comunicado


class SoloComunicacionesMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Publicar/editar/eliminar comunicados queda para admin y RRHH
    (o superusuario); cualquier persona autenticada puede leerlos."""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or user.rol in ("admin", "rrhh"))

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "No tienes permiso para publicar comunicados.")
        return redirect("comunicados:lista")


class ComunicadoListView(LoginRequiredMixin, ListView):
    model = Comunicado
    template_name = "comunicados/lista.html"
    context_object_name = "comunicados"
    paginate_by = 15

    def get_queryset(self):
        return Comunicado.objects.select_related("autor").all()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoy = date.today()
        contexto["mes_actual_nombre"] = MESES_ES[hoy.month - 1]
        contexto["dia_hoy"] = hoy.day
        cumpleañeros = list(Funcionario.objects.cumpleañeros_del_mes(hoy.month))
        for persona in cumpleañeros:
            persona.cargo_mostrar = persona.cargo or persona.departamento.nombre
        contexto["cumpleañeros_mes"] = cumpleañeros
        return contexto


class ComunicadoCreateView(SoloComunicacionesMixin, CreateView):
    model = Comunicado
    form_class = ComunicadoForm
    template_name = "comunicados/formulario.html"
    success_url = reverse_lazy("comunicados:lista")

    def form_valid(self, form):
        form.instance.autor = self.request.user
        respuesta = super().form_valid(form)
        messages.success(self.request, "Comunicado publicado.")
        return respuesta


class ComunicadoUpdateView(SoloComunicacionesMixin, UpdateView):
    model = Comunicado
    form_class = ComunicadoForm
    template_name = "comunicados/formulario.html"
    success_url = reverse_lazy("comunicados:lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, "Comunicado actualizado.")
        return respuesta


class ComunicadoDeleteView(SoloComunicacionesMixin, DeleteView):
    model = Comunicado
    template_name = "comunicados/confirmar_eliminar.html"
    success_url = reverse_lazy("comunicados:lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, "Comunicado eliminado.")
        return respuesta
