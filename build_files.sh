#!/bin/bash
# Paso de build de Vercel: instala dependencias y junta los estáticos
# (STATIC_ROOT) para que @vercel/static-build los publique.
set -e
if command -v uv >/dev/null 2>&1; then
    # El pip de este entorno está protegido por uv (PEP 668); --system
    # es la forma sancionada de uv de instalar fuera de un venv.
    uv pip install --system -r requirements.txt
else
    python3 -m pip install --break-system-packages -r requirements.txt
fi
python3 manage.py collectstatic --noinput --clear
