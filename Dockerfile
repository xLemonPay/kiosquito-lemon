FROM python:3.12-slim

# Evitar que Python escriba archivos .pyc y forzar salida sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Argentina/Buenos_Aires

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del bot
COPY . .

# Crear carpeta de datos si no existe
RUN mkdir -p /app/data

# Ejecutar el bot
CMD ["python", "bot.py"]
