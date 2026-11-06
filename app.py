
from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import get_connection, initialize_database
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime
from functools import wraps
import sqlite3

app = Flask(__name__)
app.secret_key = "hospital_devops_secret"


# ---------------- AUTHENTICATION ----------------

def patient_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "patient_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin" not in session:
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ---------------- HOME ----------------

@app.route("/")
def home():
    if "patient_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("login.html")


# ---------------- PATIENT REGISTRATION ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        phone = request.form.get("phone", "").strip()

        if not name or not email or not password:
            flash("All required fields must be completed.")
            return redirect(url_for("register"))

        conn = get_connection()

        try:
            conn.execute("""
                INSERT INTO patients (name, email, password, phone)
                VALUES (?, ?, ?, ?)
            """, (
                name,
                email,
                generate_password_hash(password),
                phone
            ))

            conn.commit()
            flash("Registration successful! Please login.")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Email already registered.")

        finally:
            conn.close()

    return render_template("register.html")


# ---------------- PATIENT LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_connection()

        patient = conn.execute(
            "SELECT * FROM patients WHERE email=?",
            (email,)
        ).fetchone()

        conn.close()

        if patient and check_password_hash(
            patient["password"], password
        ):

            session.clear()
            session["patient_id"] = patient["id"]
            session["patient_name"] = patient["name"]

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


# ---------------- PATIENT DASHBOARD ----------------

@app.route("/dashboard")
@patient_required
def dashboard():

    conn = get_connection()

    total = conn.execute("""
        SELECT COUNT(*) FROM appointments
        WHERE patient_id=?
    """, (session["patient_id"],)).fetchone()[0]

    upcoming = conn.execute("""
        SELECT COUNT(*) FROM appointments
        WHERE patient_id=? AND status='Booked'
        AND appointment_date >= ?
    """, (
        session["patient_id"],
        str(date.today())
    )).fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        name=session["patient_name"],
        total=total,
        upcoming=upcoming
    )


# ---------------- DOCTOR SEARCH ----------------

@app.route("/doctors")
@patient_required
def doctors():

    specialization = request.args.get(
        "specialization", ""
    ).strip()

    conn = get_connection()

    doctor_list = conn.execute("""
        SELECT * FROM doctors
        WHERE specialization LIKE ?
        AND available=1
        ORDER BY name
    """, (f"%{specialization}%",)).fetchall()

    conn.close()

    return render_template(
        "doctors.html",
        doctors=doctor_list,
        specialization=specialization
    )


# ---------------- APPOINTMENT BOOKING ----------------

@app.route("/book/<int:doctor_id>", methods=["GET", "POST"])
@patient_required
def book(doctor_id):

    conn = get_connection()

    doctor = conn.execute("""
        SELECT * FROM doctors
        WHERE id=? AND available=1
    """, (doctor_id,)).fetchone()

    if not doctor:
        conn.close()
        flash("Doctor not found.")
        return redirect(url_for("doctors"))

    if request.method == "POST":

        appointment_date = request.form.get("date", "")
        appointment_time = request.form.get("time", "")

        try:
            selected_date = datetime.strptime(
                appointment_date, "%Y-%m-%d"
            ).date()

            datetime.strptime(appointment_time, "%H:%M")

            if selected_date < date.today():
                flash("Cannot book appointments in the past.")

            else:
                # Lock the database while checking and booking.
                conn.execute("BEGIN IMMEDIATE")

                existing = conn.execute("""
                    SELECT id FROM appointments
                    WHERE doctor_id=?
                    AND appointment_date=?
                    AND appointment_time=?
                    AND status='Booked'
                """, (
                    doctor_id,
                    appointment_date,
                    appointment_time
                )).fetchone()

                if existing:
                    conn.rollback()
                    flash("This appointment slot is already occupied.")

                else:
                    conn.execute("""
                        INSERT INTO appointments
                        (patient_id, doctor_id, appointment_date,
                         appointment_time, status)
                        VALUES (?, ?, ?, ?, 'Booked')
                    """, (
                        session["patient_id"],
                        doctor_id,
                        appointment_date,
                        appointment_time
                    ))

                    conn.commit()
                    conn.close()

                    flash("Appointment booked successfully!")
                    return redirect(url_for("appointments"))

        except ValueError:
            conn.rollback()
            flash("Invalid date or time.")

        except sqlite3.Error:
            conn.rollback()
            flash("Unable to book appointment. Please try again.")

    conn.close()

    return render_template(
        "doctors.html",
        doctors=[doctor],
        specialization="",
        selected_doctor=doctor,
        today=date.today().isoformat()
    )


# ---------------- VIEW APPOINTMENTS ----------------

@app.route("/appointments")
@patient_required
def appointments():

    conn = get_connection()

    records = conn.execute("""
        SELECT appointments.*,
               doctors.name AS doctor_name,
               doctors.specialization
        FROM appointments
        JOIN doctors
        ON appointments.doctor_id=doctors.id
        WHERE appointments.patient_id=?
        ORDER BY appointments.id DESC
    """, (session["patient_id"],)).fetchall()

    conn.close()

    return render_template(
        "appointments.html",
        records=records
    )


# ---------------- CANCEL APPOINTMENT ----------------

@app.route("/cancel/<int:id>", methods=["POST"])
@patient_required
def cancel(id):

    conn = get_connection()

    result = conn.execute("""
        UPDATE appointments
        SET status='Cancelled'
        WHERE id=?
        AND patient_id=?
        AND status='Booked'
    """, (
        id,
        session["patient_id"]
    ))

    conn.commit()
    conn.close()

    if result.rowcount:
        flash("Appointment cancelled successfully!")
    else:
        flash("Appointment could not be cancelled.")

    return redirect(url_for("appointments"))


# ---------------- ADMIN LOGIN ----------------

@app.route("/admin", methods=["GET", "POST"])
def admin_login():

    if "admin" in session:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_connection()

        admin = conn.execute("""
            SELECT * FROM admins WHERE username=?
        """, (username,)).fetchone()

        conn.close()

        if admin and check_password_hash(
            admin["password"], password
        ):

            session.clear()
            session["admin"] = username

            return redirect(url_for("admin_dashboard"))

        flash("Invalid administrator credentials.")

    return render_template(
        "admin.html",
        admin_logged_in=False
    )


# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    conn = get_connection()

    records = conn.execute("""
        SELECT appointments.*,
               patients.name AS patient_name,
               patients.email,
               doctors.name AS doctor_name,
               doctors.specialization
        FROM appointments
        JOIN patients
        ON appointments.patient_id=patients.id
        JOIN doctors
        ON appointments.doctor_id=doctors.id
        ORDER BY appointments.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        admin_logged_in=True,
        records=records
    )


# ---------------- ADMIN CANCEL APPOINTMENT ----------------

@app.route("/admin/cancel/<int:id>", methods=["POST"])
@admin_required
def admin_cancel(id):

    conn = get_connection()

    result = conn.execute("""
        UPDATE appointments
        SET status='Cancelled'
        WHERE id=? AND status='Booked'
    """, (id,))

    conn.commit()
    conn.close()

    if result.rowcount:
        flash("Appointment cancelled by administrator.")
    else:
        flash("Appointment not found or already cancelled.")

    return redirect(url_for("admin_dashboard"))


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()
    return redirect(url_for("login"))


# ---------------- APPLICATION START ----------------

if __name__ == "__main__":

    initialize_database()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )