from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
import os
import urllib.parse

# Initialize SQLAlchemy
db = SQLAlchemy()

# Configure Azure SQL Database connection
params = urllib.parse.quote_plus(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=tcp:swan-river-user-information.database.windows.net,1433;"
    "DATABASE=UserDatabase;"
    "UID=jcwill23@cougarnet.uh.edu@swan-river-user-information;"
    "PWD=H1ghLander;"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30"
)

# Database URL for Flask-SQLAlchemy
DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={params}"

def init_db(app):
    """Initialize the database with the Flask app context."""
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()

