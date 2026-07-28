from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView

from .forms import SolicitudPermisoForm
from .models import FichaLaboral, SolicitudPermiso
from .utils import (
    calcular_antiguedad,
    calcular_saldo_vacaciones,
    puede_gestionar_esta_solicitud,
    puede_gestionar_solicitudes,
    solicitudes_gestionables,
)


class MiFichaView(LoginRequiredMixin, TemplateView):
    template_name = "rrhh/mi_ficha.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        funcionario = getattr(self.request.user, "funcionario", None)
        contexto["funcionario"] = funcionario

        if funcionario is None:
            return contexto

        try:
            ficha_laboral = funcionario.ficha_laboral
        except FichaLaboral.DoesNotExist:
            ficha_laboral = None
        contexto["ficha_laboral"] = ficha_laboral

        if ficha_laboral:
            años, meses = calcular_antiguedad(ficha_laboral.fecha_ingreso)
            contexto["antiguedad_años"] = años
            contexto["antiguedad_meses"] = meses

        contexto["jefatura"] = funcionario.departamento.jefe
        contexto["saldo_vacaciones"] = calcular_saldo_vacaciones(funcionario)
        contexto["liquidaciones"] = funcionario.liquidaciones.all()
        contexto["permisos"] = funcionario.permisos.all()
        contexto["licencias"] = funcionario.licencias_medicas.all()
        contexto["certificados_renta"] = funcionario.documentos_personales.filter(
            categoria="certificado_renta"
        )
        contexto["documentos_personales"] = funcionario.documentos_personales.exclude(
            categoria="certificado_renta"
        )
        return contexto


class SolicitudPermisoCreateView(LoginRequiredMixin, CreateView):
    form_class = SolicitudPermisoForm
    template_name = "rrhh/solicitar_permiso.html"
    success_url = reverse_lazy("rrhh:mi_ficha")

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request.user, "funcionario", None):
            messages.error(request, "Tu cuenta no está vinculada a una ficha de funcionario.")
            return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.funcionario = self.request.user.funcionario
        respuesta = super().form_valid(form)
        messages.success(self.request, "Tu solicitud quedó registrada como pendiente.")
        return respuesta


class AprobacionesListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = SolicitudPermiso
    template_name = "rrhh/aprobaciones.html"
    context_object_name = "solicitudes"

    def test_func(self):
        return puede_gestionar_solicitudes(self.request.user)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "No tienes equipo a cargo, así que no hay solicitudes que aprobar.")
        return redirect("inicio")

    def get_queryset(self):
        qs = solicitudes_gestionables(self.request.user).order_by("-fecha_solicitud")
        self.estado = self.request.GET.get("estado", "pendiente")
        if self.estado != "todas":
            qs = qs.filter(estado=self.estado)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["estado_filtro"] = self.estado
        contexto["total_pendientes"] = solicitudes_gestionables(self.request.user).filter(
            estado=SolicitudPermiso.Estado.PENDIENTE
        ).count()
        return contexto


class ResolverSolicitudView(LoginRequiredMixin, View):
    def post(self, request, pk):
        solicitud = get_object_or_404(SolicitudPermiso, pk=pk)
        if not puede_gestionar_esta_solicitud(request.user, solicitud):
            messages.error(request, "No puedes resolver esa solicitud.")
            return redirect("rrhh:aprobaciones")

        accion = request.POST.get("accion")
        if accion == "aprobar":
            solicitud.estado = SolicitudPermiso.Estado.APROBADO
        elif accion == "rechazar":
            solicitud.estado = SolicitudPermiso.Estado.RECHAZADO
        else:
            messages.error(request, "Acción no reconocida.")
            return redirect("rrhh:aprobaciones")

        solicitud.aprobado_por = request.user
        solicitud.fecha_resolucion = timezone.now()
        solicitud.save(update_fields=["estado", "aprobado_por", "fecha_resolucion"])
        messages.success(request, f"Solicitud de {solicitud.funcionario} marcada como {solicitud.get_estado_display().lower()}.")
        return redirect("rrhh:aprobaciones")
