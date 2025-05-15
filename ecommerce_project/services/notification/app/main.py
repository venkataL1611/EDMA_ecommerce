import os
import asyncio
import sys 
import logging
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import json 
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Add shared directory to Python path
shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared'))
sys.path.append(shared_path)

from shared.rabbitmq import RabbitMQ
from shared.database import Database 

db=Database()

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
        await rabbitmq.start_consuming(process_notification_message)
        app.state.rabbitmq_ready.set()
    except Exception as e:
        logger.error(f"Failed to initialize RabbitMQ: {str(e)}")
        if not app.state.rabbitmq_ready.is_set():
            app.state.rabbitmq_ready.set()
        raise

async def process_notification_message(message):
    """Process notification messages from RabbitMQ"""
    async with message.process():
        try:
            # Parse message
            notification_data = json.loads(message.body.decode())
            logger.info(f"Processing notification: {notification_data}")
            
            # Extract data
            user_id = notification_data["user_id"]
            order_id = notification_data["order_id"]
            status = notification_data["status"]
            
            # Look up user email
            query = "SELECT email FROM users WHERE id = $1"
            result = await db.execute_query(query, [user_id], fetch=True)
            if not result:
                logger.error(f"User with ID {user_id} not found")
                return
            
            email = result[0]["email"]
            
            # Simulate sending email
            logger.info(f"Sending email to {email}: Order {order_id} is {status}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid message format: {str(e)}")
            raise
        except KeyError as e:
            logger.error(f"Missing required field in message: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error processing notification: {str(e)}", exc_info=True)
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