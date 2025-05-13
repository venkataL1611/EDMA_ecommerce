# Main application file for notification service
import sys
import os
import asyncio
from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add shared directory to Python path
shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared'))
sys.path.append(shared_path)

from shared.rabbitmq import RabbitMQ

app = FastAPI()

@app.get("/status")
def status():
    return {"status": "Notification service is running"}

@app.on_event("startup")
async def startup_event():
    rabbitmq = RabbitMQ(queue_name="notification_queue")
    await rabbitmq.connect()

    async def process_email_notification(message):
        print(f"Sending email: {message.body.decode()}")
        # Logic to send email notification
        await message.ack()

    await rabbitmq.consume_message(process_email_notification)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5003)
