# Main application file for user service
import sys
import os
from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add shared directory to Python path
shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared'))
sys.path.append(shared_path)

from shared.rabbitmq import RabbitMQ

app = FastAPI()

@app.get("/status")
def status():
    return {"status": "User service is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5005)
