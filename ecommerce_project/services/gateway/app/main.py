# # Main application file for gateway service
# import sys
# import os
# from fastapi import FastAPI
# from dotenv import load_dotenv
# import asyncio

# # Load environment variables
# load_dotenv()

# # Add shared directory to Python path
# shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared'))
# sys.path.append(shared_path)

# from shared.rabbitmq import RabbitMQ

# app = FastAPI()


# @app.get("/status")
# def status():
#     return {"status": "Gateway service is running"}

# @app.post("/orders")
# async def create_order(order: dict):
#     rabbitmq = RabbitMQ(queue_name="order_queue")
#     await rabbitmq.connect()
#     print(f"Publishing order to RabbitMQ: {order}")
#     await rabbitmq.publish_message(str(order))
#     await rabbitmq.close()
#     return {"message": "Order event published to RabbitMQ."}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=5050)

import os
import asyncio
import logging
from fastapi import FastAPI, HTTPException, status
from dotenv import load_dotenv
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional

from shared.rabbitmq import RabbitMQ

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Setup RabbitMQ instance
rabbitmq = RabbitMQ(queue_name="order_queue")

class OrderCreateRequest(BaseModel):
    product_id: int
    user_id: int
    quantity: int

class OrderResponse(BaseModel):
    id: int
    product_id: int
    user_id: int
    quantity: int
    status: str
    message: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting gateway service initialization...")
    
    # Initialize RabbitMQ connection
    app.state.rabbitmq_ready = asyncio.Event()
    app.state.startup_task = asyncio.create_task(_initialize_rabbitmq(app))
    
    try:
        await asyncio.wait_for(app.state.rabbitmq_ready.wait(), timeout=30.0)
        logger.info("Gateway service initialization complete")
    except asyncio.TimeoutError:
        logger.error("RabbitMQ initialization timed out")
        if hasattr(app.state, 'startup_task'):
            app.state.startup_task.cancel()
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down gateway service...")
    if hasattr(app.state, 'startup_task') and not app.state.startup_task.done():
        app.state.startup_task.cancel()
    
    await rabbitmq.close()
    logger.info("Gateway service shutdown complete")

async def _initialize_rabbitmq(app: FastAPI):
    try:
        await rabbitmq._ensure_connection()
        app.state.rabbitmq_ready.set()
    except Exception as e:
        logger.error(f"Failed to initialize RabbitMQ: {str(e)}")
        if not app.state.rabbitmq_ready.is_set():
            app.state.rabbitmq_ready.set()  # Ensure we don't hang
        raise

app = FastAPI(
    lifespan=lifespan,
    title="Order Gateway Service",
    description="Handles order creation and routing to the order service"
)

@app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_order(order_request: OrderCreateRequest):
    """
    Create a new order by publishing to RabbitMQ.
    Returns immediately with order acceptance confirmation.
    """
    try:
        # Generate a unique order ID (in production, use a proper ID generator)
        order_id = int(asyncio.get_running_loop().time() * 1000)
        
        order_data = {
            "id": order_id,
            "product_id": order_request.product_id,
            "user_id": order_request.user_id,
            "quantity": order_request.quantity,
            "status": "received"
        }
        
        await rabbitmq.publish_message(str(order_data))
        
        return {
            **order_data,
            "message": "Order received and being processed"
        }
    except Exception as e:
        logger.error(f"Failed to create order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to process order at this time"
        )

@app.get("/health")
async def health_check():
    """
    Health check endpoint that verifies RabbitMQ connection
    """
    if not rabbitmq._is_connected.is_set():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RabbitMQ not connected"
        )
    return {
        "status": "healthy",
        "services": {
            "rabbitmq": "connected"
        }
    }

@app.get("/")
async def root():
    return {"message": "Order Gateway Service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5050)),
        log_level="info"
    )