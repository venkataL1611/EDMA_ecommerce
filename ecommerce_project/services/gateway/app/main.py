import os
import asyncio
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from dotenv import load_dotenv
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-strong-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Setup RabbitMQ instance
rabbitmq = RabbitMQ(queue_name="order_queue")

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Mock user database (replace with real database in production)
fake_users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("adminpassword"),
        "disabled": False,
    }
}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

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

# Authentication utilities
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

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
            app.state.rabbitmq_ready.set()
        raise

app = FastAPI(
    lifespan=lifespan,
    title="Order Gateway Service",
    description="Handles order creation and routing to the order service"
)

# Authentication endpoints
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(fake_users_db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Protected endpoints
@app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_order(
    order_request: OrderCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new order by publishing to RabbitMQ.
    Requires valid JWT token.
    """
    try:
        # Generate a unique order ID
        order_id = int(asyncio.get_running_loop().time() * 1000)
        
        order_data = {
            "id": order_id,
            "product_id": order_request.product_id,
            "user_id": order_request.user_id,
            "quantity": order_request.quantity,
            "status": "received",
            "created_by": current_user.username
        }
        
        await rabbitmq.publish_message(json.dumps(order_data))
        
        return {
            **order_data,
            "message": f"Order received and being processed by {current_user.username}"
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

@app.get("/status")
async def status(current_user: User = Depends(get_current_active_user)):
    return {
        "status": "Gateway is secure and running",
        "authenticated_user": current_user.username
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