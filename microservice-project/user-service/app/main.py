from fastapi import FastAPI
from pydantic import BaseModel
import pika
import json

app = FastAPI()

# Define a Pydantic model for the request body
class RegisterUserRequest(BaseModel):
    email: str

def publish_user_registered_event(email: str):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
    channel = connection.channel()

    # Declare a custom exchange
    exchange_name = 'user_events'
    channel.exchange_declare(exchange=exchange_name, exchange_type='direct', durable=True)

    # Declare the queue and bind it to the exchange
    queue_name = 'user_registered'
    channel.queue_declare(queue=queue_name, durable=True)
    channel.queue_bind(exchange=exchange_name, queue=queue_name, routing_key='user_registered')

    # Publish the message to the exchange
    message = json.dumps({"email": email})
    channel.basic_publish(
        exchange=exchange_name,
        routing_key='user_registered',
        body=message,
        properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
    )
    print(f"UserRegistered event published for {email}")
    connection.close()

@app.post("/register")
def register_user(request: RegisterUserRequest):
    # Simulate user registration logic
    print(f"Registering user with email: {request.email}")
    publish_user_registered_event(request.email)
    return {"message": f"User registered successfully for {request.email}"}