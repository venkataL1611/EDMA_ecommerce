# Dockerfile for gateway service
FROM python:3.11-slim
WORKDIR /app
COPY ./services/gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY ./services/shared /app/shared
COPY ./services/gateway/app /app/app
COPY . .
ENV PYTHONPATH="/app/shared"
CMD ["python", "-m", "app.main"]
