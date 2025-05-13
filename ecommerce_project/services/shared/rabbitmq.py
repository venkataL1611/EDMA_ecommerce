import os
import asyncio
from aio_pika import connect_robust, Message, ExchangeType

class RabbitMQ:
    def __init__(self, queue_name):
        self.queue_name = queue_name
        self.connection = None
        self.channel = None

    async def connect(self):
        retries = 5
        for attempt in range(retries):
            try:
                self.connection = await connect_robust(
                    f"amqp://{os.getenv('RABBITMQ_HOST', 'rabbitmq')}:{os.getenv('RABBITMQ_PORT', '5672')}"
                )
                self.channel = await self.connection.channel()
                await self.channel.declare_queue(self.queue_name, durable=True)
                break
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(2)
                else:
                    raise e

    async def publish_message(self, message):
        if not self.channel:
            raise Exception("RabbitMQ channel is not initialized. Call connect() first.")
        await self.channel.default_exchange.publish(
            Message(body=message.encode()),
            routing_key=self.queue_name,
        )

    async def consume_message(self, callback):
        if not self.channel:
            raise Exception("RabbitMQ channel is not initialized. Call connect() first.")
        queue = await self.channel.declare_queue(self.queue_name, durable=True)
        await queue.consume(callback)

    async def close(self):
        if self.connection:
            await self.connection.close()