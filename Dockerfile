FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends libgeos-c1v5 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
ENV DATA_DIR=/data DB_PATH=/data/signals.db ENABLE_SCHEDULER=1 DEV_MODE=0
VOLUME ["/data"]
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.web.main:app", "--host", "0.0.0.0", "--port", "8080"]
