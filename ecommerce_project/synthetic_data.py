from sdv.single_table import GaussianCopulaSynthesizer
import pandas as pd 
import psycopg2
from psycopg2.extras import execute_values
from sdv.metadata import SingleTableMetadata

# Database connection details
DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "myecomm_pass",  # Change to your actual password
    "host": "localhost",
    "port": 5431,
}

# Define schemas for Product and User
product_data = pd.DataFrame({
    "product_id": [1, 2, 3],
    "name": ["Product A", "Product B", "Product C"],
    "description": ["Description A", "Description B", "Description C"]
})

user_data = pd.DataFrame({
    "name": ["John Doe", "Jane Smith", "Alice Johnson"],
    "email": ["john@example.com", "jane@example.com", "alice@example.com"]
})

# Create metadata for SDV models
product_metadata = SingleTableMetadata()
product_metadata.detect_from_dataframe(product_data)

user_metadata = SingleTableMetadata()
user_metadata.detect_from_dataframe(user_data)

# Train SDV models
product_model = GaussianCopulaSynthesizer(product_metadata)
product_model.fit(product_data)

user_model = GaussianCopulaSynthesizer(user_metadata)
user_model.fit(user_data)

# Generate synthetic data
synthetic_products = product_model.sample(100)
synthetic_users = user_model.sample(100)


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
                ON CONFLICT (product_id) DO NOTHING
                """

                # Convert DataFrame to list of tuples
                values = [tuple(row) for row in data.to_numpy()]

                # Use execute_values for batch insertion with a single placeholder
                execute_values(cursor, query, values)
                connection.commit()
        print(f"Data inserted successfully into {table_name}")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error inserting into {table_name}: {error}")

# Create tables first

# Insert synthetic data into the database
insert_data("product", synthetic_products)
insert_data("users", synthetic_users)

