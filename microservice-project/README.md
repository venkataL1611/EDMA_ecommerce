# Microservice Project

This project simulates a microservice architecture using FastAPI and RabbitMQ. It consists of two main services: the User Service and the Email Service.

## Overview

- **User Service**: Responsible for handling user registrations. It accepts new user registrations and publishes a `UserRegistered` event to RabbitMQ.
- **Email Service**: Listens for the `UserRegistered` event and sends a welcome email to the registered user.

## Project Structure

```
microservice-project
├── user-service
│   ├── app
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── routes.py
│   │   └── events.py
│   ├── environment.yml
│   └── README.md
├── email-service
│   ├── app
│   │   ├── main.py
│   │   ├── events.py
│   └── environment.yml
├── docker-compose.yml
└── README.md
```

## Setup Instructions

1. **Clone the repository**:
   ```
   git clone <repository-url>
   cd microservice-project
   ```

2. **Install dependencies using pip**:
   For the User Service:
   ```
   python -m venv user-service-env
   source user-service-env/bin/activate
   pip install -r user-service/requirements.txt
   ```

   For the Email Service:
   ```
   python -m venv email-service-env
   source email-service-env/bin/activate
   pip install -r email-service/requirements.txt
   ```

3. **Run the services**:
   You can use Docker Compose to run both services:
   ```
   docker-compose up
   ```

## Usage

- To register a new user, send a POST request to the User Service endpoint (e.g., `http://localhost:8000/register`) with the user details.
- The Email Service will automatically listen for the `UserRegistered` event and print a welcome message to the console.

## Technologies Used

- FastAPI
- RabbitMQ
- Docker

## License

This project is licensed under the MIT License.