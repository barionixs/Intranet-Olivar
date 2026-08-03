import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction

from directorio.models import Departamento, Funcionario

from .models import Usuario


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="RUT / usuario",
        widget=forms.TextInput(attrs={"autofocus": True, "class": "js-rut-input", "autocomplete": "username"}),
    )
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)

    def clean_username(self):
        # El campo se muestra formateado (20.026.280-8) pero en la BD el
        # username se guarda sin puntos (20026280-8), así que se limpia
        # antes de autenticar.
        valor = self.cleaned_data.get("username", "")
        return re.sub(r"[.\s]", "", valor).upper()


class UsuarioCreacionForm(forms.ModelForm):
    password = forms.CharField(
        label="Contraseña inicial",
        widget=forms.PasswordInput(render_value=False),
        help_text="La persona deberá cambiarla la primera vez que inicie sesión.",
    )
    fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    departamento = forms.ModelChoiceField(
        label="Departamento",
        queryset=Departamento.objects.order_by("nombre"),
    )
    cargo = forms.ChoiceField(
        label="Cargo",
        choices=[("", "---------")] + Funcionario.Cargo.choices,
        required=False,
    )

    class Meta:
        model = Usuario
        fields = ["username", "first_name", "last_name", "email", "rol", "is_active"]
        labels = {
            "username": "RUT / nombre de usuario",
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "email": "Correo",
            "rol": "Rol",
            "is_active": "Cuenta activa",
        }
        help_texts = {
            "rol": "Jefatura se asigna sola al poner a la persona como jefe de un "
            "departamento en Directorio (y se quita sola si deja de serlo). "
            "Elegirla acá a mano se puede sobrescribir en el próximo cambio de jefatura.",
        }

    def clean_username(self):
        username = self.cleaned_data["username"]
        if Funcionario.objects.filter(rut=username).exists():
            raise forms.ValidationError(
                "Ya existe una ficha de Directorio con este RUT."
            )
        return username

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password"])
        usuario.debe_cambiar_password = True
        if commit:
            with transaction.atomic():
                usuario.save()
                Funcionario.objects.create(
                    nombre_completo=f"{usuario.last_name} {usuario.first_name}".strip(),
                    rut=usuario.username,
                    cargo=self.cleaned_data.get("cargo", ""),
                    departamento=self.cleaned_data["departamento"],
                    fecha_nacimiento=self.cleaned_data["fecha_nacimiento"],
                    email=usuario.email,
                    usuario=usuario,
                )
        return usuario


class UsuarioEdicionForm(forms.ModelForm):
    nueva_password = forms.CharField(
        label="Restablecer contraseña",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Déjalo vacío para no cambiarla. Si escribes algo, la persona deberá cambiarla en su próximo inicio de sesión.",
    )

    class Meta:
        model = Usuario
        fields = ["username", "first_name", "last_name", "email", "rol", "is_active"]
        labels = {
            "username": "RUT / nombre de usuario",
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "email": "Correo",
            "rol": "Rol",
            "is_active": "Cuenta activa",
        }
        help_texts = {
            "rol": "Jefatura se asigna sola al poner a la persona como jefe de un "
            "departamento en Directorio (y se quita sola si deja de serlo). "
            "Elegirla acá a mano se puede sobrescribir en el próximo cambio de jefatura.",
        }

    def save(self, commit=True):
        usuario = super().save(commit=False)
        nueva = self.cleaned_data.get("nueva_password")
        if nueva:
            usuario.set_password(nueva)
            usuario.debe_cambiar_password = True
        if commit:
            usuario.save()
        return usuario
