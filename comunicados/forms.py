from django import forms

from .models import Comunicado


class ComunicadoForm(forms.ModelForm):
    class Meta:
        model = Comunicado
        fields = ["titulo", "cuerpo", "destacado"]
        labels = {
            "titulo": "Título",
            "cuerpo": "Contenido",
            "destacado": "Destacar en Inicio",
        }
        widgets = {
            "cuerpo": forms.Textarea(attrs={"rows": 8}),
        }
