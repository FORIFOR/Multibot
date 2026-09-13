FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 AGENTTEAM_MODE=production AGENTTEAM_DATA_DIR=/data AGENTTEAM_ACCESS_FILE=/run/secrets/access.json
WORKDIR /app
COPY backend/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY backend /app/backend
RUN pip install --no-cache-dir --no-deps /app/backend && mkdir /data && chown 10001:10001 /data
USER 10001:10001
VOLUME ["/data"]
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import json,urllib.request,urllib.parse,os; c=json.load(open(os.environ['AGENTTEAM_ACCESS_FILE'])); r=urllib.request.Request('http://127.0.0.1:8787/api/health/live',headers={'Host':urllib.parse.urlsplit(c['public_origin']).netloc}); urllib.request.urlopen(r,timeout=3)"
ENTRYPOINT ["agentteam"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8787"]
