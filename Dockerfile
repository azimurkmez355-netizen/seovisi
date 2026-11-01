# seovisi sunucu görüntüsü: yalnızca Python standart kütüphanesi, dışarıdan paket yok.
# Veri (mağazalar, sunucu.json) /app/data birimindedir; görüntü yeniden kurulunca kaybolmaz.
FROM python:3.12-slim

# PORT: dinlenen kapı; Railway kendi değerini verir
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 PORT=8080
WORKDIR /app
COPY *.py paketler.json ./
COPY ui ./ui
COPY platformlar ./platformlar
RUN useradd --system --uid 1000 seovisi && mkdir -p /app/data /yedek && chown seovisi /app/data /yedek
USER seovisi

EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/saglik' % os.environ['PORT'], timeout=8).status == 200 else 1)"
CMD ["python", "app.py", "--sunucu", "--host", "0.0.0.0"]
