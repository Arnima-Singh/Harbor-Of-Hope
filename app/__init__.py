
import os
from flask import Flask
from dotenv import load_dotenv
from database import create_table

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["UPLOAD_FOLDER"] = os.path.join(
    app.root_path, "uploads"
)
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    if not app.config["SECRET_KEY"]:
        raise RuntimeError(
            "SECRET_KEY is missing. Please check your .env file."
        )

    create_table()

    from app.routes import main
    app.register_blueprint(main)

    return app
