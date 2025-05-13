import os
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

class Database:
    def __init__(self):
        self.connection_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,  # Adjust based on your expected parallel requests
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            database=os.getenv("POSTGRES_DB"),
        )

    @contextmanager
    def get_connection(self):
        connection = self.connection_pool.getconn()
        try:
            yield connection
        finally:
            self.connection_pool.putconn(connection)

    def execute_query(self, query, params=None):
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                if cursor.description:  # If the query returns data
                    return cursor.fetchall()
                conn.commit()

db = Database()