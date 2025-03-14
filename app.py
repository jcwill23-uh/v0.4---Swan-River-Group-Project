from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from dotenv import load_dotenv
import os
import logging

from config import Config
from models import db
from routes import auth_bp, user_bp, admin_bp

load_dotenv()

app = Flask(__name__, template_folder='docs', static_folder='docs')
app.config.from_object(Config)
app.secret_key = os.getenv('SECRET_KEY')

# Configure database and session
db.init_app(app)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(admin_bp, url_prefix='/admin')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8000, debug=True)
