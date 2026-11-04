FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema requeridas para postgres y compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar requerimientos de Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del proyecto
COPY . /app/

# Exponer puerto de la aplicación
EXPOSE 8000

# Script de entrada para migraciones y arranque de Gunicorn
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_data && gunicorn mundial_project.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
