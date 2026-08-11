from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView

from directorio.models import Departamento, Funcionario
from directorio.views import SoloSuperAdminMixin

from .forms import ReautenticacionFirmaForm, SolicitudPermisoForm
from .models import CargoUnico, FichaLaboral, FirmaSolicitud, SolicitudPermiso
from .utils import (
    actualizar_estado_solicitud,
    calcular_antiguedad,
    crear_firmas_para_solicitud,
    es_su_turno,
    firmas_visibles_para,
    hash_firma,
    obtener_ip_cliente,
    puede_firmar,
    puede_gestionar_solicitudes,
    puede_ver_solicitud,
    renderizar_documento_permiso,
    resolver_jefatura_directa,
    resumen_saldos,
    tiene_formato_institucional,
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
        contexto["saldos_permiso"] = resumen_saldos(funcionario)
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["funcionario"] = self.request.user.funcionario
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["saldos_permiso"] = resumen_saldos(self.request.user.funcionario)
        return contexto

    def form_valid(self, form):
        funcionario = self.request.user.funcionario
        jefatura_directa = resolver_jefatura_directa(funcionario)
        if not jefatura_directa:
            messages.error(
                self.request,
                "Todavía no se puede enviar tu solicitud: tu jefatura directa no está configurada "
                "en el sistema. Avisa a TI para que complete tu jerarquía y vuelve a intentarlo.",
            )
            return redirect("rrhh:mi_ficha")

        form.instance.funcionario = funcionario
        respuesta = super().form_valid(form)
        crear_firmas_para_solicitud(self.object)
        messages.success(
            self.request,
            "Tu solicitud quedó registrada. Debes firmarla tú primero para que siga su curso.",
        )
        return respuesta


class SolicitudDetalleView(LoginRequiredMixin, DetailView):
    model = SolicitudPermiso
    template_name = "rrhh/detalle_solicitud.html"
    context_object_name = "solicitud"

    def get_queryset(self):
        return SolicitudPermiso.objects.select_related("funcionario", "funcionario__departamento")

    def get_object(self, queryset=None):
        solicitud = super().get_object(queryset)
        if not puede_ver_solicitud(self.request.user, solicitud):
            raise PermissionDenied("No puedes ver esta solicitud.")
        return solicitud

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        firmas = list(self.object.firmas.select_related("funcionario_firmante").order_by("orden"))
        contexto["firmas"] = firmas
        contexto["tiene_formato_institucional"] = tiene_formato_institucional(self.object)
        funcionario = getattr(self.request.user, "funcionario", None)
        for firma in firmas:
            firma.es_mi_turno = (
                firma.estado == FirmaSolicitud.Estado.PENDIENTE
                and puede_firmar(self.request.user, firma)
                and es_su_turno(firma)
            )
        contexto["mi_turno_pendiente"] = next((f for f in firmas if f.es_mi_turno), None)
        return contexto


class FormatoPermisoAdministrativoView(LoginRequiredMixin, View):
    """Vista previa/descarga del formato institucional en cualquier
    momento: si la solicitud ya está aprobada se sirve la versión final
    guardada (`documento_permiso`); si aún está en trámite, se genera al
    vuelo con el estado actual de las firmas (las que faltan se ven como
    "PENDIENTE", sin bloquear la vista previa)."""

    def get(self, request, *args, **kwargs):
        solicitud = get_object_or_404(
            SolicitudPermiso.objects.select_related("funcionario", "funcionario__departamento"),
            pk=kwargs["pk"],
        )
        if not puede_ver_solicitud(request.user, solicitud):
            raise PermissionDenied("No puedes ver esta solicitud.")
        if not tiene_formato_institucional(solicitud):
            raise PermissionDenied("Este tipo de solicitud no tiene formato institucional.")

        if solicitud.documento_permiso:
            contenido = solicitud.documento_permiso.read()
        else:
            contenido = renderizar_documento_permiso(solicitud)
            if contenido is None:
                messages.error(request, "No se pudo generar el documento.")
                return redirect("rrhh:detalle_solicitud", pk=solicitud.pk)

        respuesta = HttpResponse(contenido, content_type="application/pdf")
        respuesta["Content-Disposition"] = f'inline; filename="permiso_{solicitud.pk}.pdf"'
        return respuesta


class VerificarFirmaView(DetailView):
    """Verificación pública de una solicitud, sin iniciar sesión: quien
    reciba el comprobante puede confirmar que es auténtico ingresando el
    código impreso en el PDF. Se busca por `codigo_verificacion` (no
    adivinable), nunca por el folio interno, para que nadie pueda
    recorrer solicitudes ajenas probando números."""

    model = SolicitudPermiso
    template_name = "rrhh/verificar_firma.html"
    context_object_name = "solicitud"
    slug_field = "codigo_verificacion"
    slug_url_kwarg = "codigo"

    def get_queryset(self):
        return SolicitudPermiso.objects.select_related("funcionario", "funcionario__departamento")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["firmas"] = self.object.firmas.select_related("funcionario_firmante").order_by("orden")
        return contexto


class SolicitudPermisoDeleteView(SoloSuperAdminMixin, DeleteView):
    model = SolicitudPermiso
    template_name = "rrhh/confirmar_eliminar_solicitud.html"
    success_url = reverse_lazy("rrhh:aprobaciones")
    context_object_name = "solicitud"

    def post(self, request, *args, **kwargs):
        solicitud = self.get_object()
        descripcion = str(solicitud)
        respuesta = super().post(request, *args, **kwargs)
        messages.success(request, f"Solicitud eliminada: {descripcion}.")
        return respuesta


class FirmarSolicitudView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        self.firma = get_object_or_404(
            FirmaSolicitud, solicitud_id=kwargs["solicitud_id"], orden=kwargs["orden"]
        )
        if not puede_firmar(request.user, self.firma):
            raise PermissionDenied("No eres quien debe firmar este paso.")
        if self.firma.estado != FirmaSolicitud.Estado.PENDIENTE:
            messages.info(request, "Este paso ya fue resuelto.")
            return redirect("rrhh:detalle_solicitud", pk=self.firma.solicitud_id)
        if not es_su_turno(self.firma):
            messages.error(request, "Todavía faltan firmas anteriores en el orden correspondiente.")
            return redirect("rrhh:detalle_solicitud", pk=self.firma.solicitud_id)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = ReautenticacionFirmaForm()
        return render(request, "rrhh/firmar_solicitud.html", {"firma": self.firma, "form": form})

    def post(self, request, *args, **kwargs):
        form = ReautenticacionFirmaForm(request.POST)
        accion = request.POST.get("accion", "firmar")
        if form.is_valid():
            if not request.user.check_password(form.cleaned_data["password"]):
                form.add_error("password", "Contraseña incorrecta.")
            else:
                self.firma.fecha_firma = timezone.now()
                self.firma.ip_firma = obtener_ip_cliente(request)
                if accion == "rechazar":
                    self.firma.estado = FirmaSolicitud.Estado.RECHAZADO
                else:
                    self.firma.estado = FirmaSolicitud.Estado.FIRMADO
                    self.firma.hash_documento = hash_firma(self.firma)
                self.firma.comentario = form.cleaned_data.get("comentario", "")
                self.firma.save()
                actualizar_estado_solicitud(self.firma.solicitud)
                messages.success(
                    request, "Solicitud rechazada." if accion == "rechazar" else "Firma registrada."
                )
                return redirect("rrhh:detalle_solicitud", pk=self.firma.solicitud_id)
        return render(request, "rrhh/firmar_solicitud.html", {"firma": self.firma, "form": form})


class AprobacionesListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Una fila por solicitud, no por firma: antes se repetía el nombre
    del solicitante hasta 3 veces (una por cada firma de su cadena). El
    filtro de estado usa `SolicitudPermiso.estado`, que ya es el mismo
    derivado de las firmas (pendiente/aprobado/rechazado)."""

    model = SolicitudPermiso
    template_name = "rrhh/aprobaciones.html"
    context_object_name = "solicitudes"

    MAPA_ESTADO = {
        "pendiente": SolicitudPermiso.Estado.PENDIENTE,
        "firmado": SolicitudPermiso.Estado.APROBADO,
        "rechazado": SolicitudPermiso.Estado.RECHAZADO,
    }

    def test_func(self):
        return puede_gestionar_solicitudes(self.request.user)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "No tienes solicitudes por firmar.")
        return redirect("inicio")

    def get_queryset(self):
        solicitud_ids = firmas_visibles_para(self.request.user).values_list(
            "solicitud_id", flat=True
        ).distinct()
        qs = SolicitudPermiso.objects.filter(id__in=solicitud_ids).select_related(
            "funcionario"
        ).prefetch_related(
            Prefetch(
                "firmas",
                queryset=FirmaSolicitud.objects.select_related("funcionario_firmante").order_by("orden"),
            )
        ).order_by("-fecha_solicitud")
        self.estado = self.request.GET.get("estado", "pendiente")
        if self.estado != "todas":
            qs = qs.filter(estado=self.MAPA_ESTADO.get(self.estado, SolicitudPermiso.Estado.PENDIENTE))
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["estado_filtro"] = self.estado
        contexto["total_pendientes"] = SolicitudPermiso.objects.filter(
            id__in=firmas_visibles_para(self.request.user).values_list("solicitud_id", flat=True),
            estado=SolicitudPermiso.Estado.PENDIENTE,
        ).distinct().count()
        for solicitud in contexto["solicitudes"]:
            solicitud.firma_pendiente_mia = next(
                (
                    firma for firma in solicitud.firmas.all()
                    if firma.estado == FirmaSolicitud.Estado.PENDIENTE
                    and puede_firmar(self.request.user, firma)
                    and es_su_turno(firma)
                ),
                None,
            )
        return contexto


class PanelFirmantesView(SoloSuperAdminMixin, View):
    """Panel de asignación manual y directa de firmantes: jefes de
    departamento, cargos únicos (Jefa de Personal, Alcaldesa) y
    excepciones de jefe directo por persona. Sin cálculo automático de
    por medio — lo que se asigna acá es exactamente quién firma."""

    template_name = "rrhh/panel_firmantes.html"

    def get_contexto(self):
        return {
            "departamentos": Departamento.objects.select_related("jefe", "departamento_padre").order_by("nombre"),
            "funcionarios": Funcionario.objects.order_by("nombre_completo"),
            "cargo_alcaldesa": CargoUnico.objects.filter(nombre=CargoUnico.Nombre.ALCALDESA).first(),
            "excepciones": Funcionario.objects.filter(jefe_directo__isnull=False)
                .select_related("jefe_directo", "departamento").order_by("nombre_completo"),
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_contexto())

    def post(self, request, *args, **kwargs):
        accion = request.POST.get("accion")
        if accion == "guardar_departamentos":
            self._guardar_departamentos(request)
        elif accion == "guardar_cargos_unicos":
            self._guardar_cargos_unicos(request)
        elif accion == "guardar_jefe_directo":
            self._guardar_jefe_directo(request)
        elif accion == "quitar_jefe_directo":
            self._quitar_jefe_directo(request)
        return redirect("rrhh:panel_firmantes")

    def _guardar_departamentos(self, request):
        actualizados = 0
        for depto in Departamento.objects.all():
            valor = request.POST.get(f"jefe_{depto.pk}") or None
            nuevo_jefe_id = int(valor) if valor else None
            if depto.jefe_id != nuevo_jefe_id:
                depto.jefe_id = nuevo_jefe_id
                depto.save()
                actualizados += 1
        messages.success(request, f"Se actualizó el jefe de {actualizados} departamento(s).")

    def _guardar_cargos_unicos(self, request):
        for nombre in CargoUnico.Nombre.values:
            valor = request.POST.get(f"cargo_{nombre}") or None
            cargo, _ = CargoUnico.objects.get_or_create(nombre=nombre)
            nuevo_id = int(valor) if valor else None
            if cargo.funcionario_id != nuevo_id:
                cargo.funcionario_id = nuevo_id
                cargo.save()
        messages.success(request, "Cargos únicos actualizados.")

    def _guardar_jefe_directo(self, request):
        funcionario = get_object_or_404(Funcionario, pk=request.POST.get("funcionario"))
        jefe_directo_id = request.POST.get("jefe_directo") or None
        if jefe_directo_id and int(jefe_directo_id) == funcionario.id:
            messages.error(request, "Una persona no puede ser su propio jefe directo.")
            return
        funcionario.jefe_directo_id = int(jefe_directo_id) if jefe_directo_id else None
        funcionario.save(update_fields=["jefe_directo"])
        if funcionario.jefe_directo_id:
            messages.success(request, f"{funcionario} ahora firma con {funcionario.jefe_directo} como jefatura directa.")
        else:
            messages.success(request, f"Excepción de {funcionario} eliminada — vuelve a usar el jefe de su departamento.")

    def _quitar_jefe_directo(self, request):
        funcionario_id = request.POST.get("funcionario_id")
        Funcionario.objects.filter(pk=funcionario_id).update(jefe_directo=None)
        messages.success(request, "Excepción eliminada.")
