# The WODCraft compilation service. Build from the repository root:
#   docker build -f deploy/Dockerfile -t wodcraft-service .
#   docker run --rm -p 8000:8000 -e WODCRAFT_API_KEY=… wodcraft-service
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY spec ./spec
RUN pip install --no-cache-dir build && python -m build --wheel --outdir /dist

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
RUN useradd --create-home --uid 10001 wodcraft
WORKDIR /home/wodcraft
COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl[service] && rm /tmp/*.whl
USER wodcraft
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", 8000)}/health').status == 200 else 1)"
CMD ["sh", "-c", "uvicorn wodcraft.service:app --host 0.0.0.0 --port ${PORT}"]
