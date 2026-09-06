FROM python:3.11-slim

WORKDIR /app

# libgomp1 provides libgomp.so.1, the OpenMP runtime lightgbm needs at import
# time - not present in the slim base image.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
