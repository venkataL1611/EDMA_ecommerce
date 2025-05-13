# Dockerfile for user service
FROM python:3.11-slim
WORKDIR /app
COPY ./services/shared /app/shared
COPY ./services/user/requirements.txt /app/requirements.txt
ENV PYTHONPATH="/app/shared"
RUN pip install --no-cache-dir -r requirements.txt
COPY ./services/user/app /app/app
COPY . .
CMD ["python", "-m", "app.main"]
