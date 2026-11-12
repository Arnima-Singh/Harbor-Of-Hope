
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, current_app, send_from_directory
)
import sqlite3
import os
import uuid

from werkzeug.utils import secure_filename
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
from database import DATABASE

main = Blueprint("main", __name__)

RESCUE_STATUSES = ["Pending", "In Progress", "Resolved"]
ADOPTION_STATUSES = ["Available", "Adopted"]
APPLICATION_STATUSES = ["Pending", "Approved", "Rejected"]
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_uploaded_photo(photo):
    """Save an uploaded photo and return its unique filename."""
    if not photo or not photo.filename:
        return None

    if not allowed_file(photo.filename):
        raise ValueError("Invalid photo format. Use JPG, JPEG, PNG or WEBP.")

    original_filename = secure_filename(photo.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{extension}"

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    photo.save(os.path.join(upload_folder, filename))
    return filename


def team_required():
    return session.get("team_logged_in") is True


# HOME PAGE

@main.route("/")
def home():
    return render_template("index.html")


# DISPLAY UPLOADED PHOTOS

@main.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        filename
    )


# ANIMAL RESCUE REPORT

@main.route("/report", methods=["GET", "POST"])
def report():
    if request.method == "POST":

        animal_type = request.form.get("animal_type", "").strip()
        condition = request.form.get("condition", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        contact = request.form.get("contact", "").strip()

        if not all([animal_type, condition, location, description]):
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("main.report"))

        photo = request.files.get("photo")
        photo_filename = None
        photo_path = None

        try:
            photo_filename = save_uploaded_photo(photo)

            if photo_filename:
                photo_path = os.path.join(
                    current_app.config["UPLOAD_FOLDER"],
                    photo_filename
                )

            connection = sqlite3.connect(DATABASE)
            connection.execute(
                """
                INSERT INTO reports
                (animal_type, condition, location, description, contact, photo)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    animal_type, condition, location,
                    description, contact, photo_filename
                )
            )
            connection.commit()
            connection.close()

        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("main.report"))

        except sqlite3.Error:
            if photo_path and os.path.exists(photo_path):
                os.remove(photo_path)
            flash("Something went wrong while saving your report.", "error")
            return redirect(url_for("main.report"))

        flash("Your animal rescue report has been saved!", "success")
        return redirect(url_for("main.report"))

    return render_template("report.html")


# VOLUNTEER REGISTRATION

@main.route("/volunteer/register", methods=["GET", "POST"])
def volunteer_register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()
        password = request.form.get("password", "")

        if not all([name, email, phone, location, password]):
            flash("Please fill in all fields.", "error")
            return redirect(url_for("main.volunteer_register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("main.volunteer_register"))

        password_hash = generate_password_hash(password)
        connection = sqlite3.connect(DATABASE)

        try:
            connection.execute(
                """
                INSERT INTO volunteers
                (name, email, phone, location, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, email, phone, location, password_hash)
            )
            connection.commit()

        except sqlite3.IntegrityError:
            flash("This email is already registered.", "error")
            return redirect(url_for("main.volunteer_register"))

        except sqlite3.Error:
            flash("Registration could not be completed. Please try again.", "error")
            return redirect(url_for("main.volunteer_register"))

        finally:
            connection.close()

        flash("Volunteer registration successful!", "success")
        return redirect(url_for("main.volunteer_register"))

    return render_template("volunteer_register.html")


# VOLUNTEER LOGIN

@main.route("/volunteer/login", methods=["GET", "POST"])
def volunteer_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = sqlite3.connect(DATABASE)
        connection.row_factory = sqlite3.Row

        try:
            volunteer = connection.execute(
                "SELECT * FROM volunteers WHERE email = ?",
                (email,)
            ).fetchone()
        finally:
            connection.close()

        if volunteer and check_password_hash(
            volunteer["password_hash"], password
        ):
            session["volunteer_id"] = volunteer["id"]
            session["volunteer_name"] = volunteer["name"]

            flash("Login successful!", "success")
            return redirect(url_for("main.volunteer_dashboard"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("main.volunteer_login"))

    return render_template("volunteer_login.html")


# VOLUNTEER DASHBOARD

@main.route("/volunteer/dashboard")
def volunteer_dashboard():

    volunteer_id = session.get("volunteer_id")

    if not volunteer_id:
        flash("Please log in to access your dashboard.", "error")
        return redirect(url_for("main.volunteer_login"))

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    try:
        volunteer = connection.execute(
            """
            SELECT id, name, email, phone, location
            FROM volunteers
            WHERE id = ?
            """,
            (volunteer_id,)
        ).fetchone()

        if not volunteer:
            session.pop("volunteer_id", None)
            session.pop("volunteer_name", None)
            flash("Volunteer account not found. Please log in again.", "error")
            return redirect(url_for("main.volunteer_login"))

        available_tasks = connection.execute(
            """
            SELECT r.*
            FROM reports r
            LEFT JOIN assignments a ON r.id = a.report_id
            WHERE r.status = 'Pending'
            AND a.id IS NULL
            ORDER BY r.id DESC
            """
        ).fetchall()

        my_tasks = connection.execute(
            """
            SELECT
                r.*,
                a.status AS assignment_status,
                a.assigned_at
            FROM assignments a
            JOIN reports r ON a.report_id = r.id
            WHERE a.volunteer_id = ?
            ORDER BY a.assigned_at DESC
            """,
            (volunteer_id,)
        ).fetchall()

    finally:
        connection.close()

    return render_template(
        "volunteer_dashboard.html",
        volunteer=volunteer,
        available_tasks=available_tasks,
        my_tasks=my_tasks
    )


# ACCEPT A RESCUE TASK

@main.route("/volunteer/accept/<int:report_id>", methods=["POST"])
def accept_rescue_task(report_id):

    volunteer_id = session.get("volunteer_id")

    if not volunteer_id:
        flash("Please log in to accept rescue tasks.", "error")
        return redirect(url_for("main.volunteer_login"))

    connection = sqlite3.connect(DATABASE)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        connection.execute("BEGIN IMMEDIATE")

        volunteer = connection.execute(
            "SELECT id FROM volunteers WHERE id = ?",
            (volunteer_id,)
        ).fetchone()

        if not volunteer:
            connection.rollback()
            session.pop("volunteer_id", None)
            session.pop("volunteer_name", None)
            flash("Volunteer account not found. Please log in again.", "error")
            return redirect(url_for("main.volunteer_login"))

        report = connection.execute(
            "SELECT id, status FROM reports WHERE id = ?",
            (report_id,)
        ).fetchone()

        if not report:
            connection.rollback()
            flash("Rescue report not found.", "error")
            return redirect(url_for("main.volunteer_dashboard"))

        if report[1] != "Pending":
            connection.rollback()
            flash("This rescue task is no longer available.", "error")
            return redirect(url_for("main.volunteer_dashboard"))

        existing_assignment = connection.execute(
            "SELECT id FROM assignments WHERE report_id = ?",
            (report_id,)
        ).fetchone()

        if existing_assignment:
            connection.rollback()
            flash("This rescue task has already been accepted.", "error")
            return redirect(url_for("main.volunteer_dashboard"))

        connection.execute(
            """
            INSERT INTO assignments (report_id, volunteer_id, status)
            VALUES (?, ?, 'Accepted')
            """,
            (report_id, volunteer_id)
        )

        connection.execute(
            "UPDATE reports SET status = 'In Progress' WHERE id = ?",
            (report_id,)
        )

        connection.commit()
        flash("Rescue task accepted successfully!", "success")

    except sqlite3.IntegrityError:
        connection.rollback()
        flash("This rescue task has already been assigned.", "error")

    except sqlite3.Error:
        connection.rollback()
        flash("Could not accept this task. Please try again.", "error")

    finally:
        connection.close()

    return redirect(url_for("main.volunteer_dashboard"))


# VOLUNTEER LOGOUT

@main.route("/volunteer/logout")
def volunteer_logout():

    session.pop("volunteer_id", None)
    session.pop("volunteer_name", None)

    flash("You have been logged out.", "success")
    return redirect(url_for("main.volunteer_login"))


# TEAM RESCUE DASHBOARD

@main.route("/team")
def team_reports():

    if not team_required():
        flash("Please log in to access team reports.", "error")
        return redirect(url_for("main.team_login"))

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    try:
        reports = connection.execute(
            """
            SELECT
                r.id, r.animal_type, r.condition, r.location,
                r.description, r.contact, r.status, r.photo,
                v.name AS volunteer_name,
                v.email AS volunteer_email,
                v.phone AS volunteer_phone,
                a.status AS assignment_status,
                a.assigned_at
            FROM reports r
            LEFT JOIN assignments a ON r.id = a.report_id
            LEFT JOIN volunteers v ON a.volunteer_id = v.id
            ORDER BY r.id DESC
            """
        ).fetchall()
    finally:
        connection.close()

    return render_template(
        "team.html",
        reports=reports,
        statuses=RESCUE_STATUSES
    )


# UPDATE RESCUE STATUS

@main.route("/team/report/<int:report_id>/status", methods=["POST"])
def update_report_status(report_id):

    if not team_required():
        flash("Please log in first.", "error")
        return redirect(url_for("main.team_login"))

    new_status = request.form.get("status", "").strip()

    if new_status not in RESCUE_STATUSES:
        flash("Invalid rescue status.", "error")
        return redirect(url_for("main.team_reports"))

    connection = sqlite3.connect(DATABASE)

    try:
        cursor = connection.execute(
            "UPDATE reports SET status = ? WHERE id = ?",
            (new_status, report_id)
        )
        updated = cursor.rowcount > 0
        connection.commit()
    finally:
        connection.close()

    if not updated:
        flash("Report not found.", "error")
    else:
        flash("Rescue status updated successfully!", "success")

    return redirect(url_for("main.team_reports"))


# TEAM LOGIN

@main.route("/team/login", methods=["GET", "POST"])
def team_login():

    if request.method == "POST":

        password = request.form.get("password", "")
        team_password = os.getenv("TEAM_PASSWORD")

        if team_password and password == team_password:
            session["team_logged_in"] = True
            flash("Login successful!", "success")
            return redirect(url_for("main.team_reports"))

        flash("Incorrect password. Please try again.", "error")

    return render_template("team_login.html")


# TEAM LOGOUT

@main.route("/team/logout")
def team_logout():

    session.pop("team_logged_in", None)

    flash("You have been logged out.", "success")
    return redirect(url_for("main.home"))


# ==========================================
# ANIMAL ADOPTION SYSTEM
# ==========================================

# PUBLIC ADOPTION LISTINGS

@main.route("/adopt")
def adoption_list():

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    try:
        animals = connection.execute(
            """
            SELECT *
            FROM adoptions
            WHERE status = 'Available'
            ORDER BY id DESC
            """
        ).fetchall()
    finally:
        connection.close()

    return render_template("adopt.html", animals=animals)


# INDIVIDUAL ANIMAL DETAILS AND APPLICATION

@main.route("/adopt/<int:animal_id>", methods=["GET", "POST"])
def adoption_detail(animal_id):

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    try:
        animal = connection.execute(
            "SELECT * FROM adoptions WHERE id = ?",
            (animal_id,)
        ).fetchone()

        if not animal or animal["status"] != "Available":
            flash("This animal is no longer available for adoption.", "error")
            return redirect(url_for("main.adoption_list"))

        if request.method == "POST":

            applicant_name = request.form.get("applicant_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            address = request.form.get("address", "").strip()
            reason = request.form.get("reason", "").strip()

            if not all([
                applicant_name, email, phone, address, reason
            ]):
                flash("Please complete all application fields.", "error")
                return redirect(
                    url_for("main.adoption_detail", animal_id=animal_id)
                )

            # Check availability again before saving
            current_animal = connection.execute(
                "SELECT status FROM adoptions WHERE id = ?",
                (animal_id,)
            ).fetchone()

            if not current_animal or current_animal["status"] != "Available":
                flash("This animal is no longer available.", "error")
                return redirect(url_for("main.adoption_list"))

            connection.execute(
                """
                INSERT INTO adoption_applications
                (adoption_id, applicant_name, email, phone, address, reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    animal_id, applicant_name, email,
                    phone, address, reason
                )
            )
            connection.commit()

            flash("Your adoption application has been submitted!", "success")
            return redirect(url_for("main.adoption_list"))

    finally:
        connection.close()

    return render_template("adoption_detail.html", animal=animal)


# TEAM ADOPTION MANAGEMENT AND ADD ANIMALS

@main.route("/team/adoptions", methods=["GET", "POST"])
def manage_adoptions():

    if not team_required():
        flash("Please log in to manage adoptions.", "error")
        return redirect(url_for("main.team_login"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        animal_type = request.form.get("animal_type", "").strip()
        breed = request.form.get("breed", "").strip()
        age = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()
        description = request.form.get("description", "").strip()

        if not all([name, animal_type, description]):
            flash("Name, animal type and description are required.", "error")
            return redirect(url_for("main.manage_adoptions"))

        photo_filename = None
        photo_path = None

        try:
            photo_filename = save_uploaded_photo(
                request.files.get("photo")
            )

            if photo_filename:
                photo_path = os.path.join(
                    current_app.config["UPLOAD_FOLDER"],
                    photo_filename
                )

            connection = sqlite3.connect(DATABASE)
            connection.execute(
                """
                INSERT INTO adoptions
                (name, animal_type, breed, age, gender, description, photo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name, animal_type, breed, age,
                    gender, description, photo_filename
                )
            )
            connection.commit()
            connection.close()

        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("main.manage_adoptions"))

        except sqlite3.Error:
            if photo_path and os.path.exists(photo_path):
                os.remove(photo_path)
            flash("Could not add the animal. Please try again.", "error")
            return redirect(url_for("main.manage_adoptions"))

        flash("Animal added to adoption listings successfully!", "success")
        return redirect(url_for("main.manage_adoptions"))

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    try:
        animals = connection.execute(
            "SELECT * FROM adoptions ORDER BY id DESC"
        ).fetchall()

        applications = connection.execute(
            """
            SELECT
                aa.*,
                ad.name AS animal_name,
                ad.animal_type AS animal_type
            FROM adoption_applications aa
            JOIN adoptions ad ON aa.adoption_id = ad.id
            ORDER BY aa.id DESC
            """
        ).fetchall()
    finally:
        connection.close()

    return render_template(
        "team_adoptions.html",
        animals=animals,
        applications=applications,
        application_statuses=APPLICATION_STATUSES,
        adoption_statuses=ADOPTION_STATUSES
    )


# APPROVE OR REJECT AN ADOPTION APPLICATION

@main.route(
    "/team/adoption/application/<int:application_id>/status",
    methods=["POST"]
)
def update_adoption_application(application_id):

    if not team_required():
        flash("Please log in first.", "error")
        return redirect(url_for("main.team_login"))

    new_status = request.form.get("status", "").strip()

    if new_status not in APPLICATION_STATUSES:
        flash("Invalid application status.", "error")
        return redirect(url_for("main.manage_adoptions"))

    connection = sqlite3.connect(DATABASE)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        connection.execute("BEGIN IMMEDIATE")

        application = connection.execute(
            """
            SELECT id, adoption_id, status
            FROM adoption_applications
            WHERE id = ?
            """,
            (application_id,)
        ).fetchone()

        if not application:
            connection.rollback()
            flash("Adoption application not found.", "error")
            return redirect(url_for("main.manage_adoptions"))

        animal_id = application[1]

        if new_status == "Approved":
            animal = connection.execute(
                "SELECT status FROM adoptions WHERE id = ?",
                (animal_id,)
            ).fetchone()

            if not animal or animal[0] != "Available":
                connection.rollback()
                flash("This animal is no longer available.", "error")
                return redirect(url_for("main.manage_adoptions"))

            connection.execute(
                """
                UPDATE adoption_applications
                SET status = 'Rejected'
                WHERE adoption_id = ?
                AND id != ?
                AND status = 'Pending'
                """,
                (animal_id, application_id)
            )

            connection.execute(
                """
                UPDATE adoptions
                SET status = 'Adopted'
                WHERE id = ?
                """,
                (animal_id,)
            )

        connection.execute(
            """
            UPDATE adoption_applications
            SET status = ?
            WHERE id = ?
            """,
            (new_status, application_id)
        )

        connection.commit()
        flash(
            f"Application status updated to {new_status}.",
            "success"
        )

    except sqlite3.Error:
        connection.rollback()
        flash("Could not update the application. Please try again.", "error")

    finally:
        connection.close()

    return redirect(url_for("main.manage_adoptions"))
