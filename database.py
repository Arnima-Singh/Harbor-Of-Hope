
import sqlite3

DATABASE = "Harbor_Of_Hope.db"


def create_table():
    connection = sqlite3.connect(DATABASE)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_type TEXT NOT NULL,
            condition TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            contact TEXT
        )
    """)

    connection.commit()
    connection.close()

    

