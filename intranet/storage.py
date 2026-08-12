"""Backend de almacenamiento en Vercel Blob para los archivos de MEDIA_ROOT.

Se activa solo cuando existe la variable de entorno BLOB_READ_WRITE_TOKEN
(ver STORAGES en settings.py). Es necesario porque en Vercel las funciones
corren en un filesystem de solo lectura y efímero: cualquier PDF de firma
o QR guardado en disco desaparece apenas termina esa invocación. En
desarrollo local, sin ese token, se sigue usando el disco como hasta ahora.

Los blobs siempre quedan con acceso "public": la librería vercel_blob no
soporta "private" todavía. La protección sigue siendo la misma que hoy
tiene /media/ en desarrollo: la URL no es adivinable, pero cualquiera que
la obtenga puede ver el archivo sin autenticarse.
"""
import threading
from urllib.parse import urlparse

import requests
import vercel_blob
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class VercelBlobStorage(Storage):

    _base_url = None
    _lock = threading.Lock()

    def _resolve_base_url(self):
        """Dominio público del store (ej. https://xxxx.public.blob.vercel-storage.com).

        Se obtiene una sola vez por proceso: se cachea a nivel de clase a
        partir de la respuesta de la primera subida, o listando un blob
        existente si el proceso arrancó de nuevo y todavía no subió nada.
        """
        if VercelBlobStorage._base_url is not None:
            return VercelBlobStorage._base_url
        with VercelBlobStorage._lock:
            if VercelBlobStorage._base_url is None:
                resultado = vercel_blob.list({'limit': '1'})
                blobs = resultado.get('blobs') or []
                if blobs:
                    parsed = urlparse(blobs[0]['url'])
                    VercelBlobStorage._base_url = f"{parsed.scheme}://{parsed.netloc}"
        return VercelBlobStorage._base_url

    def _url_for(self, name):
        base_url = self._resolve_base_url()
        if not base_url:
            return None
        return f"{base_url}/{name}"

    def _open(self, name, mode='rb'):
        url = self._url_for(name)
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return ContentFile(response.content, name=name)

    def _save(self, name, content):
        data = content.read()
        resultado = vercel_blob.put(name, data, {'allowOverwrite': 'true'})
        if VercelBlobStorage._base_url is None:
            parsed = urlparse(resultado['url'])
            VercelBlobStorage._base_url = f"{parsed.scheme}://{parsed.netloc}"
        return resultado['pathname']

    def exists(self, name):
        url = self._url_for(name)
        if not url:
            return False
        try:
            vercel_blob.head(url)
            return True
        except Exception:
            return False

    def url(self, name):
        return self._url_for(name)

    def delete(self, name):
        url = self._url_for(name)
        if not url:
            return
        try:
            vercel_blob.delete(url)
        except Exception:
            pass

    def size(self, name):
        url = self._url_for(name)
        if not url:
            return 0
        try:
            return vercel_blob.head(url).get('size', 0)
        except Exception:
            return 0
