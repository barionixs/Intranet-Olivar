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
