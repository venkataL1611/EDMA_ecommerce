from flask import Flask, jsonify, request
import psycopg2
from psycopg2.extras import RealDictCursor
from flask_cors import CORS,cross_origin
import os

app = Flask(__name__)
CORS(app)



# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "hotel_reservation",
    "user": "postgres",
    "password": "hotels",
    "port": 5432
}

# Connect to the database
def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    return conn

@app.route("/hotels", methods=["GET"])
def get_hotels():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hotels;")
        hotels = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(hotels)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/hotels", methods=["POST"])
def add_hotel():
    data = request.json
    name = data.get("name")
    city = data.get("city")
    price = data.get("price")

    if not name or not city or not price:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO hotels (name, city, price)
            VALUES (%s, %s, %s)
            RETURNING id;
            """,
            (name, city, price),
        )
        hotel_id = cursor.fetchone()["id"]
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"hotel_id": hotel_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/reservations/<int:hotel_id>", methods=["POST"])
@cross_origin()
def create_reservation(hotel_id):
    data = request.json
    guest_name = data.get("guest_name")
    check_in = data.get("check_in")
    check_out = data.get("check_out")
    num_guests = data.get("num_guests")

    if not guest_name or not check_in or not check_out or not num_guests:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO reservations (hotel_id, guest_name, check_in, check_out, num_guests)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (hotel_id, guest_name, check_in, check_out, num_guests),
        )
        reservation_id = cursor.fetchone()["id"]
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"reservation_id": reservation_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/reservations/<int:reservation_id>", methods=["DELETE"])
def delete_reservation(reservation_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM reservations WHERE id = %s RETURNING id;", (reservation_id,)
        )
        deleted_id = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        if deleted_id:
            return jsonify({"message": "Reservation deleted successfully"}), 200
        else:
            return jsonify({"error": "Reservation not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
