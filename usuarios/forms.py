import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm

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
        initial="123456",
        widget=forms.TextInput,
        help_text="La persona deberá cambiarla la primera vez que inicie sesión.",
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

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password"])
        usuario.debe_cambiar_password = True
        if commit:
            usuario.save()
        return usuario


class UsuarioEdicionForm(forms.ModelForm):
    nueva_password = forms.CharField(
        label="Restablecer contraseña",
        required=False,
        widget=forms.TextInput,
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

    def save(self, commit=True):
        usuario = super().save(commit=False)
        nueva = self.cleaned_data.get("nueva_password")
        if nueva:
            usuario.set_password(nueva)
            usuario.debe_cambiar_password = True
        if commit:
            usuario.save()
        return usuario
