# Main application file for order service
import sys
import os
import asyncio
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel
from shared.database import db
from shared.rabbitmq import RabbitMQ

# Load environment variables
load_dotenv()

# Add shared directory to Python path
shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared'))
sys.path.append(shared_path)

app = FastAPI()

# RabbitMQ setup
rabbitmq = RabbitMQ(queue_name="order_queue")

# Order model
class Order(BaseModel):
    id: int
    product_id: int
    user_id: int
    quantity: int
    status: str

# CRUD operations
@app.post("/orders")
async def create_order(order: dict):
    query = "INSERT INTO orders (id, product_id, user_id, quantity, status) VALUES (%s, %s, %s, %s, %s)"
    params = (order['id'], order['product_id'], order['user_id'], order['quantity'], 'processed')
    db.execute_query(query, params)

    # Publish events to RabbitMQ
    inventory_rabbitmq = RabbitMQ(queue_name="inventory_queue")
    notification_rabbitmq = RabbitMQ(queue_name="notification_queue")

    await inventory_rabbitmq.connect()
    await notification_rabbitmq.connect()

    await inventory_rabbitmq.publish_message(f"Update inventory for product {order['product_id']} with quantity {order['quantity']}")
    await notification_rabbitmq.publish_message(f"Send email to user {order['user_id']} for order {order['id']}")

    await inventory_rabbitmq.close()
    await notification_rabbitmq.close()

    return {"message": "Order created and events published."}

@app.get("/orders/{order_id}")
def get_order(order_id: int):
    query = "SELECT * FROM orders WHERE id = %s"
    result = db.execute_query(query, (order_id,))
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return result[0]

@app.put("/orders/{order_id}")
def update_order(order_id: int, order: Order):
    query = "UPDATE orders SET product_id = %s, user_id = %s, quantity = %s, status = %s WHERE id = %s"
    params = (order.product_id, order.user_id, order.quantity, order.status, order_id)
    db.execute_query(query, params)
    return {"message": "Order updated."}

@app.delete("/orders/{order_id}")
def delete_order(order_id: int):
    query = "DELETE FROM orders WHERE id = %s"
    db.execute_query(query, (order_id,))
    return {"message": "Order deleted."}

# RabbitMQ consumer for processing orders
@rabbitmq.consume_message
def process_order(ch, method, properties, body):
    order = body  # Deserialize the order message
    # Process the order (e.g., check product availability, update inventory, etc.)
    print(f"Processing order: {order}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

@app.on_event("startup")
async def startup_event():
    await rabbitmq.connect()

    async def process_order_message(message):
        with message.process():
            order_data = message.body.decode()
            print(f"Processing order: {order_data}")
            # Add logic to process the order

    await rabbitmq.consume_message(process_order_message)

@app.get("/status")
def status():
    return {"status": "Order service is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
