
import os
from flask import Flask
from dotenv import load_dotenv
from database import create_table


# Load settings from the project's .env file
load_dotenv()


def create_app():
    app = Flask(__name__)

    # Read the secret key from .env
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    if not app.config["SECRET_KEY"]:
        raise RuntimeError(
            "SECRET_KEY is missing. Please check your .env file."
        )

    create_table()

    from app.routes import main
    app.register_blueprint(main)

    return app
