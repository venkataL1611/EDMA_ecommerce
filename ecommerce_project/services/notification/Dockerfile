# Dockerfile for notification service
FROM python:3.11-slim
WORKDIR /app
COPY ./services/shared /app/shared
COPY ./services/notification/requirements.txt /app/requirements.txt
ENV PYTHONPATH="/app/shared"
RUN pip install --no-cache-dir -r requirements.txt
COPY ./services/notification/app /app/app
COPY . .
CMD ["python", "-m", "app.main"]
