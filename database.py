import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = "hospital.db"


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    # Patients table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT
        )
    """)

    # Doctors table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            available INTEGER DEFAULT 1
        )
    """)

    # Appointments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            status TEXT DEFAULT 'Booked',
            FOREIGN KEY(patient_id) REFERENCES patients(id),
            FOREIGN KEY(doctor_id) REFERENCES doctors(id)
        )
    """)

    # Admin table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Default admin
    admin = cursor.execute(
        "SELECT * FROM admins WHERE username='admin'"
    ).fetchone()

    if not admin:
        cursor.execute(
            "INSERT INTO admins (username,password) VALUES (?,?)",
            ("admin", generate_password_hash("admin123"))
        )

    # Sample doctors
    doctors = [
        ("Dr. Arun Kumar", "Cardiology"),
        ("Dr. Priya Sharma", "Dermatology"),
        ("Dr. Rahul Verma", "Neurology"),
        ("Dr. Sneha Reddy", "Pediatrics"),
        ("Dr. Karthik Rao", "Orthopedics"),
        ("Dr. Ananya Das", "General Medicine")
    ]

    count = cursor.execute(
        "SELECT COUNT(*) FROM doctors"
    ).fetchone()[0]

    if count == 0:
        cursor.executemany(
            "INSERT INTO doctors (name,specialization) VALUES (?,?)",
            doctors
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    initialize_database()
    print("Hospital database initialized successfully!")