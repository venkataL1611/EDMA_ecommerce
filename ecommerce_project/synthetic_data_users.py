import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv
import os
from faker import Faker
import hashlib

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


# Number of synthetic users to generate
NUM_USERS = 100

# Initialize Faker
fake = Faker()

# Generate synthetic user data
user_data = []
for i in range(NUM_USERS):
    username = fake.user_name() + str(i)  # Ensure uniqueness
    email = fake.unique.email()
    password = fake.password(length=12)
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    is_active = fake.boolean(chance_of_getting_true=90)
    created_at = fake.date_time_between(start_date='-2y', end_date='now')
    updated_at = created_at + timedelta(days=random.randint(0, 365))
    user_data.append({
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "is_active": is_active,
        "created_at": created_at,
        "updated_at": updated_at
    })

# Create DataFrame for users
user_df = pd.DataFrame(user_data)


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


# Insert synthetic user data into the database
insert_data("users", user_df)

