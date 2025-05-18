import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv
import os
from faker import Faker

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

# Number of synthetic products to generate
NUM_PRODUCTS = 100

# Initialize Faker
fake = Faker()

# Generate synthetic product data
product_data = []
for _ in range(NUM_PRODUCTS):
    name = fake.unique.word().capitalize() + " " + fake.unique.word().capitalize()
    stock = random.randint(0, 1000)
    updated_at = datetime.now() - timedelta(days=random.randint(0, 60))
    product_data.append({
        "name": name,
        "stock": stock,
        "updated_at": updated_at
    })

# Create DataFrame for products
product_df = pd.DataFrame(product_data)

# Insert synthetic product data into the database
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
insert_data("products", product_df)

