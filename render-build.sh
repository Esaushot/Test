#!/usr/bin/env bash
# Salir inmediatamente si un comando falla
set -o errexit

# Instalar las dependencias de Python
pip install -r requirements.txt

# Aquí puedes agregar comandos para inicializar tu base de datos si fuera necesario
# python seed.py