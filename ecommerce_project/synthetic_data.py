from sdv.single_table import GaussianCopulaSynthesizer
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from sdv.metadata import SingleTableMetadata
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Database connection details
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

# Define schema for Products
product_data = pd.DataFrame({
    "id": [1, 2, 3],
    "name": ["Product A", "Product B", "Product C"],
    "stock": [100, 200, 150],
    "updated_at": [
        datetime.now() - timedelta(days=random.randint(1, 30)),
        datetime.now() - timedelta(days=random.randint(1, 30)),
        datetime.now() - timedelta(days=random.randint(1, 30)),
    ]
})

# Create metadata for SDV model
product_metadata = SingleTableMetadata()
product_metadata.detect_from_dataframe(product_data)

# Train SDV model
product_model = GaussianCopulaSynthesizer(product_metadata)
product_model.fit(product_data)

# Generate synthetic data
synthetic_products = product_model.sample(100)


def insert_data(table_name, data):
    """Insert data into the specified table"""
    try:
        with psycopg2.connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                # Convert column names to lowercase to match PostgreSQL convention
                columns = ", ".join([col.lower() for col in data.columns])
                placeholders = ", ".join(["%s"] * len(data.columns))

                # Prepare the insert query with ON CONFLICT clause
                query = f"""
                INSERT INTO {table_name.lower()} ({columns}) 
                VALUES %s 
                ON CONFLICT (id) DO NOTHING
                """

                # Convert DataFrame to list of tuples
                values = [tuple(row) for row in data.to_numpy()]

                # Use execute_values for batch insertion with a single placeholder
                execute_values(cursor, query, values)
                connection.commit()
        print(f"Data inserted successfully into {table_name}")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error inserting into {table_name}: {error}")


# Insert synthetic data into the database
insert_data("products", synthetic_products)

