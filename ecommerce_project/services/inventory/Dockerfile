# Dockerfile for inventory service
FROM python:3.11-slim
WORKDIR /app
COPY ./services/shared /app/shared
COPY ./services/inventory/requirements.txt /app/requirements.txt
ENV PYTHONPATH="/app/shared"
RUN pip install --no-cache-dir -r requirements.txt
COPY ./services/inventory/app /app/app
COPY . .
ENV PYTHONPATH="/app/shared"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5002"]
