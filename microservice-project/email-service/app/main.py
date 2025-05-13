import sys
from fastapi import FastAPI
import pika
import threading

app = FastAPI()

def callback(ch, method, properties, body):
    try:
        email = body.decode()
        print(f"Processing message: {email}")
        print(f"Welcome email sent to {email}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print("Message acknowledged")
    except Exception as e:
        print(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def start_rabbitmq_consumer():
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
            print("Connected to RabbitMQ")
            channel = connection.channel()

            exchange_name = 'user_events'
            queue_name = 'user_registered'
            channel.exchange_declare(exchange=exchange_name, exchange_type='direct', durable=True)
            channel.queue_declare(queue=queue_name, durable=True)
            channel.queue_bind(exchange=exchange_name, queue=queue_name, routing_key='user_registered')

            channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=False)
            print('Waiting for UserRegistered events. To exit press CTRL+C')
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            print("RabbitMQ is not ready. Retrying in 5 seconds...")
            import time
            time.sleep(5)

# Start the RabbitMQ consumer in a separate thread
#@app.on_event("startup")
# def start_consumer_thread():
#     consumer_thread = threading.Thread(target=start_rabbitmq_consumer, daemon=True)
#     consumer_thread.start()
#     print("RabbitMQ consumer thread started")

if __name__ == "__main__":
    if "--consumer" in sys.argv:
        start_rabbitmq_consumer()
