FROM python:3.11-slim
WORKDIR /app

# Конвертер DWG: предпочтительно упакованный в tools/ (pack_converter.sh на сборщике);
# apt — только fallback, его отсутствие не роняет сборку.
COPY tools/ tools/
RUN apt-get update \
 && (apt-get install -y --no-install-recommends libredwg-tools \
     || echo "WARN: libredwg-tools unavailable; will use bundled tools/ if present") \
 && rm -rf /var/lib/apt/lists/* || true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY data/ data/
COPY web/ web/
COPY examples/ examples/
COPY serve.py ./

ENV GREENPLAN_HOST=0.0.0.0
EXPOSE 8000
CMD ["python", "serve.py"]