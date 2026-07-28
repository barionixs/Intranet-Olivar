from django.conf import settings
from django.shortcuts import redirect
from django.urls import Resolver404, resolve

RUTAS_PERMITIDAS = {"cambiar_clave_obligatorio", "logout"}


class ForzarCambioPasswordMiddleware:
    """Si el usuario autenticado tiene debe_cambiar_password=True (cuentas
    creadas con la clave genérica 123456), lo manda directo a cambiar su
    clave antes de dejarlo usar cualquier otra vista de la intranet."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and getattr(user, "debe_cambiar_password", False)
            and not request.path.startswith(settings.STATIC_URL)
        ):
            try:
                nombre_url = resolve(request.path_info).url_name
            except Resolver404:
                nombre_url = None
            if nombre_url not in RUTAS_PERMITIDAS:
                return redirect("cambiar_clave_obligatorio")
        return self.get_response(request)
