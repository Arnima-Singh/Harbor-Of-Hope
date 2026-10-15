
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session
)
import sqlite3

import os 

from database import DATABASE

main = Blueprint("main", __name__)


@main.route("/")
def home():
    return render_template("index.html")


@main.route("/report", methods=["GET", "POST"])
def report():
    if request.method == "POST":
        animal_type = request.form.get("animal_type", "").strip()
        condition = request.form.get("condition", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        contact = request.form.get("contact", "").strip()

        if not animal_type or not condition or not location or not description:
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("main.report"))

        connection = sqlite3.connect(DATABASE)

        connection.execute(
            """
            INSERT INTO reports
            (animal_type, condition, location, description, contact)
            VALUES (?, ?, ?, ?, ?)
            """,
            (animal_type, condition, location, description, contact),
        )

        connection.commit()
        connection.close()

        flash("Your animal rescue report has been saved!", "success")
        return redirect(url_for("main.report"))

    return render_template("report.html")

@main.route("/team")
def team_reports():
    if not session.get("team_logged_in"):
        flash("Please log in to access team reports.", "error")
        return redirect(url_for("main.team_login"))

    connection = sqlite3.connect(DATABASE)

    reports = connection.execute(
        """
        SELECT id, animal_type, condition, location, description, contact
        FROM reports
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return render_template("team.html", reports=reports)


@main.route("/team/login", methods=["GET", "POST"])
def team_login():
    if request.method == "POST":
        password = request.form.get("password", "")

        if password == os.getenv("TEAM_PASSWORD"):
            session["team_logged_in"] = True
            flash("Login successful!", "success")
            return redirect(url_for("main.team_reports"))

        flash("Incorrect password. Please try again.", "error")

    return render_template("team_login.html")


@main.route("/team/logout")
def team_logout():
    session.pop("team_logged_in", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("main.home"))


