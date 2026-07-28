from django.conf import settings
from django.db import models
from django.utils import timezone


class Comunicado(models.Model):
    titulo = models.CharField(max_length=200)
    cuerpo = models.TextField()
    fecha_publicacion = models.DateTimeField(default=timezone.now)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comunicados"
    )
    destacado = models.BooleanField(default=False)

    class Meta:
        ordering = ["-fecha_publicacion"]
        verbose_name = "Comunicado"
        verbose_name_plural = "Comunicados"

    def __str__(self):
        return self.titulo
