# Contexto de build: raíz del repositorio
FROM python:3.12.8-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /srv
COPY libs/ruta_comun /tmp/ruta_comun
COPY services/auditoria/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt /tmp/ruta_comun && rm -rf /tmp/ruta_comun
COPY services/auditoria/app ./app
COPY services/auditoria/tests ./tests
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
