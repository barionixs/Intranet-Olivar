from comunicados.models import Comunicado


def barra_lateral(request):
    """Datos para la barra lateral opcional (últimos comunicados):
    páginas con contenido más escueto (Mi Ficha, Directorio, etc.) la
    activan con `{% block tiene_barra_lateral %}si{% endblock %}` para
    no dejar tanto espacio vacío a los costados. Nunca se calcula para
    visitantes sin sesión (ej. la verificación pública de firma)."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}
    return {
        "barra_comunicados": Comunicado.objects.select_related("autor")[:3],
    }
