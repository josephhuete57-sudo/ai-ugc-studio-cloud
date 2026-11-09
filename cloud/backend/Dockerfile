FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY cloud/common cloud/common
COPY cloud/backend cloud/backend
COPY cloud/worker cloud/worker
ENV PYTHONUNBUFFERED=1 CLOUD_MODE=FREE_CLOUD
EXPOSE 8002
CMD ["python", "-m", "uvicorn", "cloud.backend.app:app", "--host", "0.0.0.0", "--port", "8002"]
