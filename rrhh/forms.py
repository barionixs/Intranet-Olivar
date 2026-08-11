from django import forms

from .models import SolicitudPermiso
from .utils import dias_disponibles


class SolicitudPermisoForm(forms.ModelForm):
    class Meta:
        model = SolicitudPermiso
        fields = ["tipo", "fecha_inicio", "fecha_termino", "dias_solicitados", "motivo"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_termino": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "tipo": "Tipo de solicitud",
            "fecha_inicio": "Desde",
            "fecha_termino": "Hasta",
            "dias_solicitados": "Días solicitados",
            "motivo": "Motivo (opcional)",
        }

    def __init__(self, *args, funcionario=None, **kwargs):
        self.funcionario = funcionario
        super().__init__(*args, **kwargs)

    def clean(self):
        limpio = super().clean()
        inicio = limpio.get("fecha_inicio")
        termino = limpio.get("fecha_termino")
        if inicio and termino and termino < inicio:
            raise forms.ValidationError("La fecha de término no puede ser anterior a la de inicio.")

        tipo = limpio.get("tipo")
        dias = limpio.get("dias_solicitados")
        if self.funcionario and tipo and dias and inicio:
            disponibles = dias_disponibles(self.funcionario, tipo, inicio.year)
            if disponibles is not None and dias > disponibles:
                self.add_error(
                    "dias_solicitados",
                    f"Solo te quedan {disponibles} día{'s' if disponibles != 1 else ''} disponibles de "
                    f"{dict(SolicitudPermiso.Tipo.choices)[tipo]} para {inicio.year}.",
                )
        return limpio


class ReautenticacionFirmaForm(forms.Form):
    """No basta con la sesión activa para firmar: se vuelve a pedir la
    contraseña para poder atribuir razonablemente el acto a la persona
    en ese instante exacto, tal como exige una firma electrónica simple
    bajo la Ley 19.799."""

    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    declaracion = forms.BooleanField(
        label="Declaro que esta es mi decisión respecto a esta solicitud, firmada electrónicamente "
        "conforme a la Ley 19.799 sobre documentos electrónicos, firma electrónica y servicios de "
        "certificación de dicha firma.",
        required=True,
        error_messages={"required": "Debes marcar la declaración para continuar."},
    )
    comentario = forms.CharField(
        label="Comentario (opcional)", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
