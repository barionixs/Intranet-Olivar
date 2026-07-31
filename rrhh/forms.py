from django import forms

from .models import SolicitudPermiso


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

    def clean(self):
        limpio = super().clean()
        inicio = limpio.get("fecha_inicio")
        termino = limpio.get("fecha_termino")
        if inicio and termino and termino < inicio:
            raise forms.ValidationError("La fecha de término no puede ser anterior a la de inicio.")
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
