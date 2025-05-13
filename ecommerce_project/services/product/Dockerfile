# Dockerfile for product service
FROM python:3.11-slim
WORKDIR /app
COPY ./services/shared /app/shared
COPY ./services/product/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH="/app/shared"
COPY ./services/product/app /app/app
COPY . .
CMD ["python", "-m", "app.main"]
