import os
import asyncio
import sys 
import logging
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Add shared directory to Python path
shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared'))
sys.path.append(shared_path)

from shared.rabbitmq import RabbitMQ

# Setup RabbitMQ instance globally
rabbitmq = RabbitMQ(queue_name="notification_queue")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting notification service initialization...")
    
    # Connect to RabbitMQ and start consumer
    app.state.rabbitmq_ready = asyncio.Event()
    app.state.startup_task = asyncio.create_task(_initialize_rabbitmq(app))
    
    try:
        await asyncio.wait_for(app.state.rabbitmq_ready.wait(), timeout=30.0)
        logger.info("Notification service initialization complete")
    except asyncio.TimeoutError:
        logger.error("RabbitMQ initialization timed out")
        if hasattr(app.state, 'startup_task'):
            app.state.startup_task.cancel()
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down notification service...")
    if hasattr(app.state, 'startup_task') and not app.state.startup_task.done():
        app.state.startup_task.cancel()
    
    await rabbitmq.close()
    logger.info("Notification service shutdown complete")

async def _initialize_rabbitmq(app: FastAPI):
    try:
        await rabbitmq._ensure_connection()
        await rabbitmq.start_consuming(process_notification)
        app.state.rabbitmq_ready.set()
    except Exception as e:
        logger.error(f"Failed to initialize RabbitMQ: {str(e)}")
        if not app.state.rabbitmq_ready.is_set():
            app.state.rabbitmq_ready.set()
        raise

async def process_notification(message):
    async with message.process():
        try:
            notification_data = message.body.decode()
            logger.info(f"Processing notification: {notification_data}")
            # Business logic: Send email notification to the user
            notification = eval(notification_data)  # Convert string to dictionary
            user_id = notification["user_id"]
            order_id = notification["order_id"]
            status = notification["status"]
            # Example: Log the notification (replace with actual email logic)
            logger.info(f"Email sent to user_id: {user_id} for order_id: {order_id} with status: {status}")
        except Exception as e:
            logger.error(f"Error processing notification: {str(e)}")
            raise

app = FastAPI(lifespan=lifespan)

@app.get("/status")
def status():
    return {"status": "Notification service is running"}

@app.get("/health")
async def health_check():
    if not rabbitmq._is_connected.is_set():
        raise HTTPException(status_code=503, detail="RabbitMQ not connected")
    return {"status": "healthy", "rabbitmq": "connected"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5003)