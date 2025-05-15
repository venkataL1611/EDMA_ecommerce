import os
import asyncio
import logging
import json
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
from contextlib import asynccontextmanager
from shared.rabbitmq import RabbitMQ
from shared.database import Database

db=Database()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize RabbitMQ connections globally
order_rabbitmq = RabbitMQ(queue_name="order_queue")
inventory_rabbitmq = RabbitMQ(queue_name="inventory_queue")
notification_rabbitmq = RabbitMQ(queue_name="notification_queue")

class Order(BaseModel):
    id: int
    product_id: int
    user_id: int
    quantity: int
    status: str

async def process_order_message(message):
    async with message.process():
        try:
            order_data = message.body.decode()
            
            # First try standard JSON parsing
            try:
                order_dict = json.loads(order_data)
            except json.JSONDecodeError:
                # Fallback for malformed JSON (single quotes)
                try:
                    # Safely evaluate the string as Python literal
                    import ast
                    order_dict = ast.literal_eval(order_data)
                except (ValueError, SyntaxError) as e:
                    logger.error(f"Failed to parse message: {e}\nRaw message: {order_data}")
                    raise
                
            # Validate the order data
            order = Order.model_validate(order_dict)
            
            # Process the order (database operations)
            await process_order_in_db(order)
            
            # Publish to downstream queues
            await publish_downstream_messages(order)
            
        except Exception as e:
            logger.error(f"Failed to process order: {e}")
            raise  # This will cause the message to be requeued

async def publish_downstream_messages(order: Order):
    """Publish messages to inventory and notification queues"""
    # Inventory message
    inventory_msg = json.dumps({
        "product_id": order.product_id,
        "quantity": order.quantity,
        "operation": "deduct"
    })
    await inventory_rabbitmq.publish_message(inventory_msg)
    
    # Notification message
    notification_msg = json.dumps({
        "user_id": order.user_id,
        "order_id": order.id,
        "status": order.status
    })
    await notification_rabbitmq.publish_message(notification_msg)


async def process_order_in_db(order: Order):
    """Handle database operations for the order"""
    try:
        # UPSERT operation
        query = """
        INSERT INTO orders (id, product_id, user_id, quantity, status)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id) DO UPDATE 
        SET product_id = EXCLUDED.product_id,
            user_id = EXCLUDED.user_id,
            quantity = EXCLUDED.quantity,
            status = EXCLUDED.status,
            updated_at = NOW()
        """
        params = (order.id, order.product_id, order.user_id, order.quantity, order.status)
        await db.execute_query(query, params)
        
    except Exception as e:
        logger.error(f"Database operation failed: {e}")
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing order service...")
    
    try:
        # Initialize all RabbitMQ connections
        logger.info("Connecting to RabbitMQ...")
        await asyncio.gather(
            order_rabbitmq._ensure_connection(),
            inventory_rabbitmq._ensure_connection(),
            notification_rabbitmq._ensure_connection()
        )
        
        # Start consuming messages
        logger.info("Starting order queue consumer...")
        await order_rabbitmq.start_consuming(process_order_message)
        
        logger.info("Order service ready")
        yield
        
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise
    finally:
        # Shutdown
        logger.info("Shutting down...")
        await asyncio.gather(
            order_rabbitmq.close(),
            inventory_rabbitmq.close(),
            notification_rabbitmq.close()
        )
        logger.info("Shutdown complete")

app = FastAPI(lifespan=lifespan)

@app.post("/orders")
async def create_order(order: Order):
    """API endpoint to create new orders"""
    try:
        # Publish directly to order queue
        await order_rabbitmq.publish_message(order.model_dump_json())
        return {"message": "Order received for processing", "order_id": order.id}
    except Exception as e:
        logger.error(f"Failed to queue order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ... (other endpoints remain the same) ...

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5001)),
        reload=False  # Disable reload in production
    )