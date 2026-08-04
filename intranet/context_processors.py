from datetime import date

from comunicados.models import Comunicado
from directorio.models import Funcionario


def barra_lateral(request):
    """Datos para la barra lateral opcional (cumpleaños del mes,
    últimos comunicados): páginas con contenido más escueto (Mi Ficha,
    Directorio, etc.) la activan con `{% block tiene_barra_lateral %}si{% endblock %}`
    para no dejar tanto espacio vacío a los costados. Nunca se calcula
    para visitantes sin sesión (ej. la verificación pública de firma)."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}
    hoy = date.today()
    cumpleañeros = list(Funcionario.objects.cumpleañeros_del_mes(hoy.month)[:6])
    return {
        "barra_cumpleañeros": cumpleañeros,
        "barra_dia_hoy": hoy.day,
        "barra_comunicados": Comunicado.objects.select_related("autor")[:3],
    }
