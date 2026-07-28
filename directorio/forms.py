from django import forms

from .models import Funcionario


class FuncionarioEditForm(forms.ModelForm):
    class Meta:
        model = Funcionario
        fields = ["nombre_completo", "cargo", "departamento", "email", "telefono"]
        labels = {
            "nombre_completo": "Nombre completo",
            "cargo": "Cargo",
            "departamento": "Departamento",
            "email": "Correo",
            "telefono": "Teléfono",
        }
