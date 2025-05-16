import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from asyncpg import create_pool, Pool
from asyncpg.exceptions import PostgresError

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool: Optional[Pool] = None
        self._is_connected = asyncio.Event()

    async def _ensure_connection(self, retries: int = 5, delay: float = 3.0):
        """Establish connection with exponential backoff"""
        if self._is_connected.is_set() and self.pool:
            return

        for attempt in range(retries):
            try:
                self.pool = await create_pool(
                    min_size=1,
                    max_size=10,
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT"),
                    database=os.getenv("DB_NAME"),
                    timeout=10
                )
                # Test the connection
                async with self.pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                self._is_connected.set()
                logger.info("Successfully connected to database")
                return
            except (PostgresError, ConnectionError) as e:
                wait_time = min(delay * (2 ** attempt), 30)  # Cap at 30 seconds
                logger.warning(
                    f"Database connection failed (attempt {attempt + 1}/{retries}). "
                    f"Retrying in {wait_time} seconds. Error: {str(e)}"
                )
                await asyncio.sleep(wait_time)
        
        raise ConnectionError("Could not connect to database after multiple retries")

    @asynccontextmanager
    async def get_connection(self):
        """Async context manager for database connections"""
        if not self.pool or self.pool._closed:
            await self._ensure_connection()
        
        conn = await self.pool.acquire()
        try:
            yield conn
        finally:
            await self.pool.release(conn)

    async def execute_query(
        self,
        query: str,
        params: Optional[list] = None,
        fetch: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a query with optional parameters
        :param query: SQL query string
        :param params: List of parameters for the query
        :param fetch: Whether to fetch results
        :return: List of dictionaries (rows) if fetch=True, else None
        """
        try:
            async with self.get_connection() as conn:
                if fetch:
                    return await conn.fetch(query, *(params or []))
                else:
                    await conn.execute(query, *(params or []))
        except PostgresError as e:
            logger.error(f"Database error executing query: {query}. Error: {str(e)}")
            raise

    async def close(self):
        """Close all connections in the pool"""
        if self.pool and not self.pool._closed:
            await self.pool.close()
            self._is_connected.clear()
            logger.info("Closed database connection pool")

# Global database instance
db = Database()