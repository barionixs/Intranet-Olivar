#!/bin/bash
# Paso de build de Vercel: instala dependencias y junta los estáticos
# (STATIC_ROOT) para que @vercel/static-build los publique.
python3 -m pip install --break-system-packages -r requirements.txt
python3 manage.py collectstatic --noinput --clear
