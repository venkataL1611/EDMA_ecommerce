import os
import asyncio
from aio_pika import connect_robust, Message, DeliveryMode
import logging

logger = logging.getLogger(__name__)

class RabbitMQ:
    def __init__(self, queue_name):
        self.queue_name = queue_name
        self.connection = None
        self.channel = None
        self.queue = None
        self._is_connected = asyncio.Event()

    async def _ensure_connection(self):
        if self._is_connected.is_set() and not self.connection.is_closed:
            return

        retries = 0
        max_retries = 10
        base_delay = 2
        
        while retries < max_retries:
            try:
                self.connection = await connect_robust(
                    f"amqp://{os.getenv('RABBITMQ_USER', 'guest')}:{os.getenv('RABBITMQ_PASSWORD', 'guest')}@{os.getenv('RABBITMQ_HOST', 'rabbitmq')}/",
                    timeout=10
                )
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=10)
                self.queue = await self.channel.declare_queue(
                    self.queue_name,
                    durable=True
                )
                self._is_connected.set()
                logger.info("Successfully connected to RabbitMQ")
                return
            except Exception as e:
                retries += 1
                delay = min(base_delay * (2 ** (retries - 1)), 30)
                logger.warning(
                    f"Connection attempt {retries}/{max_retries} failed. "
                    f"Retrying in {delay} seconds. Error: {str(e)}"
                )
                await asyncio.sleep(delay)
        
        raise ConnectionError("Failed to connect to RabbitMQ after multiple attempts")

    async def publish_message(self, message):
        await self._ensure_connection()
        await self.channel.default_exchange.publish(
            Message(
                body=message.encode(),
                delivery_mode=DeliveryMode.PERSISTENT
            ),
            routing_key=self.queue_name,
        )

    async def start_consuming(self, callback):
        await self._ensure_connection()
        await self.queue.consume(callback)
        logger.info(f"Started consuming messages from {self.queue_name}")

    async def close(self):
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            self._is_connected.clear()
            logger.info("Closed RabbitMQ connection")