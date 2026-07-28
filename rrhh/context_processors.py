from .utils import puede_gestionar_solicitudes


def flags_rrhh(request):
    user = getattr(request, "user", None)
    puede_aprobar = bool(user and user.is_authenticated and puede_gestionar_solicitudes(user))
    return {"puede_aprobar_solicitudes": puede_aprobar}
