import os
import asyncio
import logging
from fastapi import FastAPI, HTTPException, status, Security, Depends
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from dotenv import load_dotenv
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional
import json
from jose import jwt, JWTError
from datetime import datetime, timedelta

from shared.rabbitmq import RabbitMQ

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Setup RabbitMQ instance
rabbitmq = RabbitMQ(queue_name="order_queue")

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

SECRET_KEY = os.getenv("JWT_SECRET", "your-strong-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Utility to create JWT token
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(datetime.timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Dependency to validate JWT token
async def get_current_api_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        api_key: str = payload.get("sub")
        if api_key is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return api_key

async def validate_api_key(api_key: str = Security(api_key_header)):
    valid_api_key = os.getenv("VALID_API_KEY", "changeme")
    if api_key != valid_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return api_key

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

@app.post("/token")
async def get_token_from_api_key(api_key: str = Depends(validate_api_key)):
    access_token = create_access_token(data={"sub": api_key})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_order(order_request: OrderCreateRequest, api_key: str = Depends(get_current_api_user)):
    """
    Create a new order by publishing to RabbitMQ.
    Requires valid JWT Bearer token.
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
        
        await rabbitmq.publish_message(json.dumps(order_data))
        
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