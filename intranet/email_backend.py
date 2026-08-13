"""Envío de correo vía Microsoft Graph API en vez de SMTP.

Necesario para cuentas @muniolivar.cl: el tenant de Microsoft 365 tiene
"Security Defaults" activado, que bloquea la autenticación SMTP básica
(usuario + contraseña) sin importar lo que se configure en el buzón
individual -- es una política a nivel de todo el tenant. Graph API con
OAuth (client credentials) no pasa por esa restricción."""

import base64
import logging

import msal
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]


class MicrosoftGraphEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        token = self._obtener_token()
        if not token:
            if not self.fail_silently:
                raise RuntimeError("No se pudo obtener un token de Microsoft Graph.")
            return 0
        enviados = 0
        for message in email_messages:
            if self._enviar_uno(message, token):
                enviados += 1
        return enviados

    def _obtener_token(self):
        app = msal.ConfidentialClientApplication(
            settings.MS_GRAPH_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{settings.MS_GRAPH_TENANT_ID}",
            client_credential=settings.MS_GRAPH_CLIENT_SECRET,
        )
        resultado = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
        token = resultado.get("access_token")
        if not token:
            logger.error(
                "No se pudo obtener token de Microsoft Graph: %s",
                resultado.get("error_description", resultado.get("error")),
            )
        return token

    def _enviar_uno(self, message, token):
        content_type = "Text"
        contenido = message.body
        for cuerpo_alternativo, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                content_type = "HTML"
                contenido = cuerpo_alternativo
                break

        payload = {
            "message": {
                "subject": message.subject,
                "body": {"contentType": content_type, "content": contenido},
                "toRecipients": [{"emailAddress": {"address": destino}} for destino in message.to],
                "attachments": self._armar_adjuntos(message),
            },
            # Se guarda copia en "Elementos enviados" del buzón remitente
            # a propósito -- sirve de respaldo verificable (con fecha y
            # hora puestas por el propio servidor de Microsoft) frente a
            # un reclamo de "nunca me llegó la notificación".
            "saveToSentItems": "true",
        }
        url = f"https://graph.microsoft.com/v1.0/users/{settings.MS_GRAPH_SENDER}/sendMail"
        try:
            respuesta = requests.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
        except requests.RequestException:
            if not self.fail_silently:
                raise
            logger.exception("Fallo de red enviando correo vía Microsoft Graph.")
            return False
        if respuesta.status_code == 202:
            return True
        if not self.fail_silently:
            respuesta.raise_for_status()
        logger.error(
            "Microsoft Graph rechazó el envío (status %s): %s",
            respuesta.status_code, respuesta.text,
        )
        return False

    def _armar_adjuntos(self, message):
        """Traduce los adjuntos de Django (tuplas simples, o objetos
        MIME como el logo inline que arma rrhh.utils.notificar_turno_firma
        vía MIMEImage + Content-ID) al formato que espera Graph. Una
        imagen inline referenciada en el HTML como `cid:logo_olivar`
        necesita `isInline: true` y `contentId` igual al Content-ID."""
        adjuntos = []
        for adjunto in message.attachments:
            if hasattr(adjunto, "get_payload"):
                content_id = (adjunto.get("Content-ID") or "").strip("<>")
                adjuntos.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": adjunto.get_filename() or content_id or "adjunto",
                    "contentType": adjunto.get_content_type(),
                    "contentBytes": base64.b64encode(adjunto.get_payload(decode=True)).decode(),
                    "isInline": bool(content_id),
                    "contentId": content_id,
                })
            else:
                nombre, contenido_adj, mimetype = adjunto
                if isinstance(contenido_adj, str):
                    contenido_adj = contenido_adj.encode()
                adjuntos.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": nombre,
                    "contentType": mimetype or "application/octet-stream",
                    "contentBytes": base64.b64encode(contenido_adj).decode(),
                })
        return adjuntos
