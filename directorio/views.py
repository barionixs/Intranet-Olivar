from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView, UpdateView

from .forms import FuncionarioEditForm
from .models import Departamento, Funcionario


class DirectorioListView(LoginRequiredMixin, ListView):
    model = Funcionario
    template_name = "directorio/lista.html"
    context_object_name = "funcionarios"
    paginate_by = 24

    def get_queryset(self):
        qs = Funcionario.objects.select_related("departamento").all()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(nombre_completo__icontains=q)
                | Q(cargo__icontains=q)
                | Q(departamento__nombre__icontains=q)
            )
        departamento_id = self.request.GET.get("departamento", "").strip()
        if departamento_id:
            qs = qs.filter(departamento_id=departamento_id)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "")
        contexto["departamento_id"] = self.request.GET.get("departamento", "")
        contexto["departamentos"] = Departamento.objects.all()
        return contexto


class DirectorioDetalleView(LoginRequiredMixin, DetailView):
    model = Funcionario
    template_name = "directorio/detalle.html"
    context_object_name = "funcionario"

    def get_queryset(self):
        return Funcionario.objects.select_related("departamento")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["puede_ver_sensible"] = self.object.puede_ver_datos_sensibles(self.request.user)
        return contexto


class SoloSuperAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    """A diferencia de SoloAdminMixin (usuarios app, admite rol=admin),
    esto exige ser superusuario de Django — editar el directorio queda
    reservado a la cuenta de super admin, no a cualquier rol admin."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "Solo el super admin puede editar el directorio.")
        return redirect("directorio:detalle", pk=self.kwargs["pk"])


class FuncionarioUpdateView(SoloSuperAdminMixin, UpdateView):
    model = Funcionario
    form_class = FuncionarioEditForm
    template_name = "directorio/editar.html"

    def get_success_url(self):
        return reverse_lazy("directorio:detalle", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Datos de {self.object} actualizados.")
        return respuesta
