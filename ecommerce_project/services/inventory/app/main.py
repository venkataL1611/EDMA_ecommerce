# Main application file for inventory service
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
    return {"status": "Inventory service is running"}

@app.on_event("startup")
async def startup_event():
    rabbitmq = RabbitMQ(queue_name="inventory_queue")
    await rabbitmq.connect()

    async def process_inventory_update(message):
        print(f"Updating inventory: {message.body.decode()}")
        # Logic to update inventory in the database
        await message.ack()

    await rabbitmq.consume_message(process_inventory_update)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)
