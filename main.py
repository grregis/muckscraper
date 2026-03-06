# main.py
from app import app  # Import the Flask app instance
from app import create_db  # Import the create_db function

if __name__ == "__main__":
    create_db()  # Initialize the database
    app.run(host="0.0.0.0", port=5000, debug=True)  # Run the Flask application
