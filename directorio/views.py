from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DeleteView, DetailView, ListView, UpdateView

from .forms import FuncionarioEditForm
from .models import Departamento, Funcionario


class SoloSuperAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    """El directorio completo (listado, ficha y edición) es exclusivo del super admin."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "Solo el super admin puede acceder al directorio.")
        return redirect("inicio")


class DirectorioListView(SoloSuperAdminMixin, ListView):
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


class DirectorioDetalleView(SoloSuperAdminMixin, DetailView):
    model = Funcionario
    template_name = "directorio/detalle.html"
    context_object_name = "funcionario"

    def get_queryset(self):
        return Funcionario.objects.select_related("departamento")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["puede_ver_sensible"] = self.object.puede_ver_datos_sensibles(self.request.user)
        return contexto


class FuncionarioUpdateView(SoloSuperAdminMixin, UpdateView):
    model = Funcionario
    form_class = FuncionarioEditForm
    template_name = "directorio/editar.html"

    def get_success_url(self):
        url = reverse("directorio:detalle", kwargs={"pk": self.object.pk})
        volver = self.request.GET.get("volver")
        if volver:
            url += f"?volver={quote(volver)}"
        return url

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Datos de {self.object} actualizados.")
        return respuesta


class FuncionarioDeleteView(SoloSuperAdminMixin, DeleteView):
    model = Funcionario
    template_name = "directorio/confirmar_eliminar.html"
    success_url = reverse_lazy("directorio:lista")
    context_object_name = "funcionario"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        funcionario = self.object
        contexto["tiene_usuario"] = funcionario.usuario_id is not None
        contexto["registros_rrhh"] = sum([
            1 if hasattr(funcionario, "ficha_laboral") else 0,
            funcionario.permisos.count(),
            funcionario.licencias_medicas.count(),
            funcionario.liquidaciones.count(),
            funcionario.documentos_personales.count(),
        ])
        return contexto

    def post(self, request, *args, **kwargs):
        funcionario = self.get_object()
        nombre = str(funcionario)
        usuario_vinculado = funcionario.usuario
        try:
            with transaction.atomic():
                if usuario_vinculado:
                    # Funcionario.usuario es CASCADE: borrar el usuario ya borra
                    # este Funcionario solo. No hay que borrarlo de nuevo.
                    usuario_vinculado.delete()
                else:
                    funcionario.delete()
        except ProtectedError:
            messages.error(
                request,
                f"No se puede eliminar a {nombre}: su cuenta de usuario tiene registros asociados "
                "(por ejemplo, comunicados publicados). Elimina o reasigna esos registros primero.",
            )
            return redirect("directorio:lista")
        messages.success(request, f"{nombre} eliminado del directorio.")
        respuesta = redirect(self.success_url)
        return respuesta
