# Main application file for gateway service
import sys
import os
from fastapi import FastAPI
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Add shared directory to Python path
shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared'))
sys.path.append(shared_path)

from shared.rabbitmq import RabbitMQ

app = FastAPI()


@app.get("/status")
def status():
    return {"status": "Gateway service is running"}

@app.post("/orders")
async def create_order(order: dict):
    rabbitmq = RabbitMQ(queue_name="order_queue")
    await rabbitmq.connect()
    await rabbitmq.publish_message(f"New order created: {order}")
    await rabbitmq.close()
    return {"message": "Order event published to RabbitMQ."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050)
