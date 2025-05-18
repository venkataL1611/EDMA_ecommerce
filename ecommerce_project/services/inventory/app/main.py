import os
import sys
import asyncio
import logging
import json
from fastapi import FastAPI, HTTPException, Depends, Request, status
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(override=True)

# Add shared directory to Python path
shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared'))
sys.path.append(shared_path)

from shared.rabbitmq import RabbitMQ
from shared.database import Database  # Updated to use async Database class

# Initialize services
rabbitmq = RabbitMQ(queue_name="inventory_queue")
db = Database()

API_TOKEN = os.getenv("API_TOKEN", "your-secret-token")

def verify_token(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or auth != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API token")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Async context manager for FastAPI lifespan events"""
    # Startup
    logger.info("Starting inventory service initialization...")
    
    try:
        # Initialize database connection
        logger.info("Connecting to database...")
        await db._ensure_connection()
        
        # Connect to RabbitMQ and start consumer
        logger.info("Initializing RabbitMQ...")
        app.state.rabbitmq_ready = asyncio.Event()
        app.state.startup_task = asyncio.create_task(_initialize_rabbitmq(app))
        
        # Wait for initialization to complete
        await asyncio.wait_for(app.state.rabbitmq_ready.wait(), timeout=30.0)
        logger.info("Inventory service initialization complete")
        
        yield
        
    except asyncio.TimeoutError:
        logger.error("Initialization timed out")
        raise
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down inventory service...")
        if hasattr(app.state, 'startup_task') and not app.state.startup_task.done():
            app.state.startup_task.cancel()
        
        await rabbitmq.close()
        await db.close()
        logger.info("Inventory service shutdown complete")

async def _initialize_rabbitmq(app: FastAPI):
    """Initialize RabbitMQ connection and start consuming messages"""
    try:
        logger.info("Connecting to RabbitMQ...")
        await rabbitmq._ensure_connection()
        logger.info("RabbitMQ connection established. Starting consumer...")
        
        await rabbitmq.start_consuming(process_inventory_update)
        logger.info("RabbitMQ consumer started successfully")
        
        app.state.rabbitmq_ready.set()
    except Exception as e:
        logger.error(f"Failed to initialize RabbitMQ: {str(e)}", exc_info=True)
        if not app.state.rabbitmq_ready.is_set():
            app.state.rabbitmq_ready.set()
        raise

async def process_inventory_update(message):
    """Process inventory update messages from RabbitMQ"""
    async with message.process():
        try:
            # Parse message
            inventory_data = json.loads(message.body.decode())
            logger.info(f"Processing inventory update: {inventory_data}")
            
            # Extract data
            product_id = inventory_data["product_id"]
            quantity = inventory_data["quantity"]
            
            # Update inventory
            query = "UPDATE products SET stock = stock - $1 WHERE id = $2"
            await db.execute_query(query, [quantity, product_id], fetch=False)
            
            logger.info(f"Inventory updated - Product: {product_id}, Quantity: {quantity}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid message format: {str(e)}")
            raise
        except KeyError as e:
            logger.error(f"Missing required field in message: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error processing inventory update: {str(e)}", exc_info=True)
            raise

app = FastAPI(lifespan=lifespan)

@app.get("/status")
async def status(dep=Depends(verify_token)):
    """Service status endpoint"""
    return {
        "status": "running",
        "services": {
            "rabbitmq": "connected" if rabbitmq._is_connected.is_set() else "disconnected",
            "database": "connected" if db._is_connected.is_set() else "disconnected"
        }
    }

@app.get("/health")
async def health_check(dep=Depends(verify_token)):
    """Health check endpoint"""
    if not rabbitmq._is_connected.is_set():
        raise HTTPException(
            status_code=503,
            detail="RabbitMQ not connected",
            headers={"Retry-After": "5"}
        )
    if not db._is_connected.is_set():
        raise HTTPException(
            status_code=503,
            detail="Database not connected",
            headers={"Retry-After": "5"}
        )
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",  # Assuming your file is named app.py
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5002)),
        log_level="info",
        reload=False  # Disable reload in production
    )