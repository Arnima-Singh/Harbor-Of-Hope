
import sqlite3

DATABASE = "Harbor_Of_Hope.db"


def create_table():
    connection = sqlite3.connect(DATABASE)
    connection.execute("PRAGMA foreign_keys = ON")

    # Rescue reports
    connection.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_type TEXT NOT NULL,
            condition TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            contact TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            photo TEXT
        )
    """)

    # Add missing columns to older databases
    columns = connection.execute(
        "PRAGMA table_info(reports)"
    ).fetchall()

    column_names = [column[1] for column in columns]

    if "status" not in column_names:
        connection.execute("""
            ALTER TABLE reports
            ADD COLUMN status TEXT NOT NULL DEFAULT 'Pending'
        """)

    if "photo" not in column_names:
        connection.execute("""
            ALTER TABLE reports
            ADD COLUMN photo TEXT
        """)

    # Volunteers
    connection.execute("""
        CREATE TABLE IF NOT EXISTS volunteers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            phone TEXT NOT NULL,
            location TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Rescue task assignments
    connection.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL UNIQUE,
            volunteer_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Accepted',
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES reports(id),
            FOREIGN KEY (volunteer_id) REFERENCES volunteers(id)
        )
    """)

    # Animals available for adoption
    connection.execute("""
        CREATE TABLE IF NOT EXISTS adoptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            animal_type TEXT NOT NULL,
            breed TEXT,
            age TEXT,
            gender TEXT,
            description TEXT NOT NULL,
            photo TEXT,
            status TEXT NOT NULL DEFAULT 'Available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Adoption applications
    connection.execute("""
        CREATE TABLE IF NOT EXISTS adoption_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            adoption_id INTEGER NOT NULL,
            applicant_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (adoption_id)
                REFERENCES adoptions(id)
        )
    """)

    connection.commit()
    connection.close()
