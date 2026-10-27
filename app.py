"""
app.py - IST 210 Lab 2 CRUD Web Application
Implements Create, Read, Update, Delete for:
  - Person (Parent entity)
  - Student (Child of Person)
  - Course (Master operational entity)
  - Credit (Junction entity linking Student and Course)
  - VerificationTable (Lab verification audit log)

Enforces:
  - Security by Design: 100% Parameterized SQL statements
  - Referential Integrity Enforcement: Foreign key validation with ON DELETE NO ACTION
  - Cloud Database Integration: Supports Azure SQL, Windows Auth, and Local SQLite fallback
"""

import os
import sys
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify
)

# Ensure local imports work cleanly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import db, ReferentialIntegrityError

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "ist210-lab2-secret-key-super-secure")


# =============================================================================
# Context Processor (makes DB status available to all templates)
# =============================================================================
@app.context_processor
def inject_db_status():
    return {
        "db_engine": db.active_engine,
        "db_auth_mode": db.auth_mode,
        "db_server": db.server,
        "db_database": db.database,
        "db_error": db.connection_error,
        "current_year": datetime.now().year,
    }


# =============================================================================
# Dashboard Route (Read: Multi-Table SQL JOIN)
# =============================================================================
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    """
    Core Objective - READ:
    Executes a multi-table SQL JOIN operation across Person, Student, Course, and Credit.
    Supports real-time search filtering.
    """
    search_query = request.args.get("q", "").strip()

    # Multi-Table SQL JOIN Query with strict parameterization
    if search_query:
        sql = """
            SELECT 
                s.StudentId,
                p.PersonId,
                p.FirstName,
                p.MiddleInitial,
                p.LastName,
                p.DateOfBirth,
                s.Email,
                c.CourseId,
                c.Name AS CourseName,
                c.Teacher,
                cr.CreditId,
                cr.Grade,
                cr.Attempt
            FROM Student s
            INNER JOIN Person p ON s.PersonId = p.PersonId
            LEFT JOIN Credit cr ON s.StudentId = cr.StudentId
            LEFT JOIN Course c ON cr.CourseId = c.CourseId
            WHERE p.FirstName LIKE ? 
               OR p.LastName LIKE ? 
               OR s.Email LIKE ? 
               OR c.Name LIKE ? 
               OR c.Teacher LIKE ?
            ORDER BY p.LastName ASC, p.FirstName ASC, c.Name ASC
        """
        param = f"%{search_query}%"
        records = db.query_all(sql, (param, param, param, param, param))
    else:
        sql = """
            SELECT 
                s.StudentId,
                p.PersonId,
                p.FirstName,
                p.MiddleInitial,
                p.LastName,
                p.DateOfBirth,
                s.Email,
                c.CourseId,
                c.Name AS CourseName,
                c.Teacher,
                cr.CreditId,
                cr.Grade,
                cr.Attempt
            FROM Student s
            INNER JOIN Person p ON s.PersonId = p.PersonId
            LEFT JOIN Credit cr ON s.StudentId = cr.StudentId
            LEFT JOIN Course c ON cr.CourseId = c.CourseId
            ORDER BY p.LastName ASC, p.FirstName ASC, c.Name ASC
        """
        records = db.query_all(sql)

    # Calculate summary metrics using parameterized aggregation
    stats = {
        "total_students": db.query_one("SELECT COUNT(*) AS total FROM Student")["total"],
        "total_courses": db.query_one("SELECT COUNT(*) AS total FROM Course")["total"],
        "total_credits": db.query_one("SELECT COUNT(*) AS total FROM Credit")["total"],
        "total_persons": db.query_one("SELECT COUNT(*) AS total FROM Person")["total"],
    }

    avg_row = db.query_one("SELECT AVG(Grade) AS avg_grade FROM Credit WHERE Grade IS NOT NULL")
    stats["avg_grade"] = round(avg_row["avg_grade"], 1) if avg_row and avg_row["avg_grade"] is not None else 0.0

    return render_template(
        "dashboard.html",
        records=records,
        stats=stats,
        search_query=search_query
    )


# =============================================================================
# Person Routes (CRUD: Parent Entity)
# =============================================================================
@app.route("/persons")
def person_list():
    """Read: List all Person records alongside their Student registration status."""
    sql = """
        SELECT 
            p.PersonId,
            p.FirstName,
            p.MiddleInitial,
            p.LastName,
            p.DateOfBirth,
            s.StudentId,
            s.Email AS StudentEmail
        FROM Person p
        LEFT JOIN Student s ON p.PersonId = s.PersonId
        ORDER BY p.LastName ASC, p.FirstName ASC
    """
    persons = db.query_all(sql)
    return render_template("person_list.html", persons=persons)


@app.route("/persons/create", methods=["GET", "POST"])
def person_create():
    """Create: Form to insert new records into the Person parent table."""
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        middle_initial = request.form.get("middle_initial", "").strip() or None
        last_name = request.form.get("last_name", "").strip()
        dob = request.form.get("dob", "").strip()

        # Validation
        if not first_name or not last_name or not dob:
            flash("First Name, Last Name, and Date of Birth are mandatory fields.", "danger")
            return render_template("person_form.html", action="Create", person=request.form)

        # Parameterized INSERT
        sql = """
            INSERT INTO Person (FirstName, MiddleInitial, LastName, DateOfBirth)
            VALUES (?, ?, ?, ?)
        """
        try:
            new_id = db.execute(sql, (first_name, middle_initial, last_name, dob))
            
            # Audit in VerificationTable
            db.execute(
                "INSERT INTO VerificationTable (StudentName, ActionType, Details, VerificationCode) VALUES (?, ?, ?, ?)",
                (f"{first_name} {last_name}", "PERSON_CREATED", f"Inserted Person #{new_id}", f"VERIF-P-NEW-{new_id}")
            )
            flash(f"Successfully created Person #{new_id}: {first_name} {last_name}!", "success")
            return redirect(url_for("person_list"))
        except Exception as e:
            flash(f"Database error during insertion: {e}", "danger")

    return render_template("person_form.html", action="Create", person={})


@app.route("/persons/edit/<int:person_id>", methods=["GET", "POST"])
def person_edit(person_id):
    """Update: Form to modify existing Person records."""
    person = db.query_one("SELECT * FROM Person WHERE PersonId = ?", (person_id,))
    if not person:
        flash(f"Person with ID #{person_id} not found.", "warning")
        return redirect(url_for("person_list"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        middle_initial = request.form.get("middle_initial", "").strip() or None
        last_name = request.form.get("last_name", "").strip()
        dob = request.form.get("dob", "").strip()

        if not first_name or not last_name or not dob:
            flash("First Name, Last Name, and Date of Birth are mandatory.", "danger")
            return render_template("person_form.html", action="Edit", person=request.form)

        sql = """
            UPDATE Person 
            SET FirstName = ?, MiddleInitial = ?, LastName = ?, DateOfBirth = ?
            WHERE PersonId = ?
        """
        try:
            db.execute(sql, (first_name, middle_initial, last_name, dob, person_id))
            flash(f"Person #{person_id} successfully updated!", "success")
            return redirect(url_for("person_list"))
        except Exception as e:
            flash(f"Update failed: {e}", "danger")

    return render_template("person_form.html", action="Edit", person=person)


@app.route("/persons/delete/<int:person_id>", methods=["POST"])
def person_delete(person_id):
    """
    Delete: Safe removal adhering to foreign key referential action rules (ON DELETE NO ACTION).
    Prevents deletion if child Student record exists.
    """
    can_delete, reason = db.can_delete_person(person_id)
    if not can_delete:
        flash(reason, "danger")
        return redirect(url_for("person_list"))

    try:
        db.execute("DELETE FROM Person WHERE PersonId = ?", (person_id,))
        flash(f"Person #{person_id} was safely deleted.", "success")
    except ReferentialIntegrityError as rie:
        flash(str(rie), "danger")
    except Exception as e:
        flash(f"Deletion failed: {e}", "danger")

    return redirect(url_for("person_list"))


# =============================================================================
# Student Routes (CRUD: Child of Person, Parent of Credit)
# =============================================================================
@app.route("/students")
def student_list():
    """Read: List students with linked Person information and credit count."""
    sql = """
        SELECT 
            s.StudentId,
            s.PersonId,
            s.Email,
            p.FirstName,
            p.LastName,
            p.DateOfBirth,
            COUNT(cr.CreditId) AS CourseCount
        FROM Student s
        JOIN Person p ON s.PersonId = p.PersonId
        LEFT JOIN Credit cr ON s.StudentId = cr.StudentId
        GROUP BY s.StudentId, s.PersonId, s.Email, p.FirstName, p.LastName, p.DateOfBirth
        ORDER BY s.StudentId ASC
    """
    students = db.query_all(sql)
    return render_template("student_list.html", students=students)


@app.route("/students/create", methods=["GET", "POST"])
def student_create():
    """Create: Link an existing Person to create a new Student record."""
    available_persons = db.query_all("""
        SELECT PersonId, FirstName, LastName 
        FROM Person 
        ORDER BY LastName, FirstName
    """)

    if request.method == "POST":
        person_id = request.form.get("person_id", "").strip()
        email = request.form.get("email", "").strip()

        if not person_id or not email:
            flash("Please select a Person and provide a valid Email address.", "danger")
            return render_template("student_form.html", action="Create", student=request.form, persons=available_persons)

        # Check foreign key target exists
        target_person = db.query_one("SELECT PersonId FROM Person WHERE PersonId = ?", (person_id,))
        if not target_person:
            flash(f"Referential Integrity Error: Person #{person_id} does not exist in master records.", "danger")
            return render_template("student_form.html", action="Create", student=request.form, persons=available_persons)

        try:
            new_id = db.execute("INSERT INTO Student (PersonId, Email) VALUES (?, ?)", (person_id, email))
            db.execute(
                "INSERT INTO VerificationTable (StudentName, ActionType, Details, VerificationCode) VALUES (?, ?, ?, ?)",
                (email, "STUDENT_ENROLLED", f"Student #{new_id} linked to Person #{person_id}", f"VERIF-S-NEW-{new_id}")
            )
            flash(f"Student #{new_id} successfully registered!", "success")
            return redirect(url_for("student_list"))
        except Exception as e:
            flash(f"Registration failed: {e}", "danger")

    return render_template("student_form.html", action="Create", student={}, persons=available_persons)


@app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
def student_edit(student_id):
    """Update: Modify Student operational parameters."""
    student = db.query_one("SELECT * FROM Student WHERE StudentId = ?", (student_id,))
    if not student:
        flash(f"Student #{student_id} not found.", "warning")
        return redirect(url_for("student_list"))

    available_persons = db.query_all("SELECT PersonId, FirstName, LastName FROM Person ORDER BY LastName, FirstName")

    if request.method == "POST":
        person_id = request.form.get("person_id", "").strip()
        email = request.form.get("email", "").strip()

        if not person_id or not email:
            flash("Person and Email are required.", "danger")
            return render_template("student_form.html", action="Edit", student=request.form, persons=available_persons)

        try:
            db.execute(
                "UPDATE Student SET PersonId = ?, Email = ? WHERE StudentId = ?",
                (person_id, email, student_id)
            )
            flash(f"Student #{student_id} updated successfully!", "success")
            return redirect(url_for("student_list"))
        except Exception as e:
            flash(f"Update failed: {e}", "danger")

    return render_template("student_form.html", action="Edit", student=student, persons=available_persons)


@app.route("/students/delete/<int:student_id>", methods=["POST"])
def student_delete(student_id):
    """
    Delete: Safe removal adhering to foreign key referential action rules (ON DELETE NO ACTION).
    Checks whether child Credit/enrollment records reference this Student.
    """
    can_delete, reason = db.can_delete_student(student_id)
    if not can_delete:
        flash(reason, "danger")
        return redirect(url_for("student_list"))

    try:
        db.execute("DELETE FROM Student WHERE StudentId = ?", (student_id,))
        flash(f"Student #{student_id} safely removed.", "success")
    except ReferentialIntegrityError as rie:
        flash(str(rie), "danger")
    except Exception as e:
        flash(f"Deletion failed: {e}", "danger")

    return redirect(url_for("student_list"))


# =============================================================================
# Course Routes (CRUD: Master Operational Entity)
# =============================================================================
@app.route("/courses")
def course_list():
    """Read: List all courses and active enrollment counts."""
    sql = """
        SELECT 
            c.CourseId,
            c.Name,
            c.Teacher,
            COUNT(cr.CreditId) AS EnrolledCount
        FROM Course c
        LEFT JOIN Credit cr ON c.CourseId = cr.CourseId
        GROUP BY c.CourseId, c.Name, c.Teacher
        ORDER BY c.Name ASC
    """
    courses = db.query_all(sql)
    return render_template("course_list.html", courses=courses)


@app.route("/courses/create", methods=["GET", "POST"])
def course_create():
    """Create: Form to insert a new Course."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        teacher = request.form.get("teacher", "").strip()

        if not name or not teacher:
            flash("Course Name and Teacher/Instructor are mandatory.", "danger")
            return render_template("course_form.html", action="Create", course=request.form)

        try:
            new_id = db.execute("INSERT INTO Course (Name, Teacher) VALUES (?, ?)", (name, teacher))
            flash(f"Course #{new_id} ({name}) created successfully!", "success")
            return redirect(url_for("course_list"))
        except Exception as e:
            flash(f"Failed to create course: {e}", "danger")

    return render_template("course_form.html", action="Create", course={})


@app.route("/courses/edit/<int:course_id>", methods=["GET", "POST"])
def course_edit(course_id):
    """Update: Modify Course attributes."""
    course = db.query_one("SELECT * FROM Course WHERE CourseId = ?", (course_id,))
    if not course:
        flash(f"Course #{course_id} not found.", "warning")
        return redirect(url_for("course_list"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        teacher = request.form.get("teacher", "").strip()

        if not name or not teacher:
            flash("Course Name and Teacher are required.", "danger")
            return render_template("course_form.html", action="Edit", course=request.form)

        try:
            db.execute("UPDATE Course SET Name = ?, Teacher = ? WHERE CourseId = ?", (name, teacher, course_id))
            flash(f"Course #{course_id} updated successfully!", "success")
            return redirect(url_for("course_list"))
        except Exception as e:
            flash(f"Course update failed: {e}", "danger")

    return render_template("course_form.html", action="Edit", course=course)


@app.route("/courses/delete/<int:course_id>", methods=["POST"])
def course_delete(course_id):
    """
    Delete: Safe removal adhering to foreign key referential action rules (ON DELETE NO ACTION).
    Checks if student Credit records reference this Course.
    """
    can_delete, reason = db.can_delete_course(course_id)
    if not can_delete:
        flash(reason, "danger")
        return redirect(url_for("course_list"))

    try:
        db.execute("DELETE FROM Course WHERE CourseId = ?", (course_id,))
        flash(f"Course #{course_id} safely removed.", "success")
    except ReferentialIntegrityError as rie:
        flash(str(rie), "danger")
    except Exception as e:
        flash(f"Deletion failed: {e}", "danger")

    return redirect(url_for("course_list"))


# =============================================================================
# Credit Routes (CRUD: Junction Entity linking Student and Course)
# =============================================================================
@app.route("/credits")
def credit_list():
    """Read: List all academic enrollment credit records with student & course details."""
    sql = """
        SELECT 
            cr.CreditId,
            cr.StudentId,
            cr.CourseId,
            cr.Grade,
            cr.Attempt,
            s.Email AS StudentEmail,
            p.FirstName,
            p.LastName,
            c.Name AS CourseName,
            c.Teacher
        FROM Credit cr
        JOIN Student s ON cr.StudentId = s.StudentId
        JOIN Person p ON s.PersonId = p.PersonId
        JOIN Course c ON cr.CourseId = c.CourseId
        ORDER BY cr.CreditId DESC
    """
    credits = db.query_all(sql)
    return render_template("credit_list.html", credits=credits)


@app.route("/credits/create", methods=["GET", "POST"])
def credit_create():
    """Create: Form to enroll a student in a course with grade and attempt."""
    students = db.query_all("""
        SELECT s.StudentId, s.Email, p.FirstName, p.LastName 
        FROM Student s
        JOIN Person p ON s.PersonId = p.PersonId
        ORDER BY p.LastName, p.FirstName
    """)
    courses = db.query_all("SELECT CourseId, Name, Teacher FROM Course ORDER BY Name")

    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        course_id = request.form.get("course_id", "").strip()
        grade_str = request.form.get("grade", "").strip()
        attempt_str = request.form.get("attempt", "1").strip()

        grade = float(grade_str) if grade_str else None
        attempt = int(attempt_str) if attempt_str else 1

        if not student_id or not course_id:
            flash("Please choose both a Student and a Course.", "danger")
            return render_template("credit_form.html", action="Create", credit=request.form, students=students, courses=courses)

        # Validate Grade constraint (Grade <= 100.00 and Grade >= 0.00)
        if grade is not None and (grade < 0.0 or grade > 100.0):
            flash("Grade must be between 0.00 and 100.00 according to schema check constraints.", "danger")
            return render_template("credit_form.html", action="Create", credit=request.form, students=students, courses=courses)

        try:
            new_id = db.execute(
                "INSERT INTO Credit (StudentId, CourseId, Grade, Attempt) VALUES (?, ?, ?, ?)",
                (student_id, course_id, grade, attempt)
            )
            # Log in VerificationTable
            db.execute(
                "INSERT INTO VerificationTable (StudentName, ActionType, Details, VerificationCode) VALUES (?, ?, ?, ?)",
                (f"Student #{student_id}", "CREDIT_AWARDED", f"Course #{course_id}, Grade: {grade}", f"VERIF-CR-NEW-{new_id}")
            )
            flash(f"Credit record #{new_id} recorded successfully!", "success")
            return redirect(url_for("credit_list"))
        except Exception as e:
            err = str(e)
            if "UNIQUE" in err.upper() or "UQ_Student_Course" in err:
                flash(f"Duplicate Enrollment: Student #{student_id} already has a record for Course #{course_id} on Attempt {attempt}.", "warning")
            else:
                flash(f"Enrollment insertion error: {e}", "danger")

    return render_template("credit_form.html", action="Create", credit={}, students=students, courses=courses)


@app.route("/credits/edit/<int:credit_id>", methods=["GET", "POST"])
def credit_edit(credit_id):
    """Update: Modify grade and attempt parameters for an existing credit."""
    credit = db.query_one("SELECT * FROM Credit WHERE CreditId = ?", (credit_id,))
    if not credit:
        flash(f"Credit record #{credit_id} not found.", "warning")
        return redirect(url_for("credit_list"))

    students = db.query_all("""
        SELECT s.StudentId, s.Email, p.FirstName, p.LastName 
        FROM Student s
        JOIN Person p ON s.PersonId = p.PersonId
        ORDER BY p.LastName, p.FirstName
    """)
    courses = db.query_all("SELECT CourseId, Name, Teacher FROM Course ORDER BY Name")

    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        course_id = request.form.get("course_id", "").strip()
        grade_str = request.form.get("grade", "").strip()
        attempt_str = request.form.get("attempt", "1").strip()

        grade = float(grade_str) if grade_str else None
        attempt = int(attempt_str) if attempt_str else 1

        if grade is not None and (grade < 0.0 or grade > 100.0):
            flash("Grade must be between 0.00 and 100.00.", "danger")
            return render_template("credit_form.html", action="Edit", credit=request.form, students=students, courses=courses)

        try:
            db.execute(
                "UPDATE Credit SET StudentId = ?, CourseId = ?, Grade = ?, Attempt = ? WHERE CreditId = ?",
                (student_id, course_id, grade, attempt, credit_id)
            )
            flash(f"Credit record #{credit_id} updated successfully!", "success")
            return redirect(url_for("credit_list"))
        except Exception as e:
            flash(f"Update failed: {e}", "danger")

    return render_template("credit_form.html", action="Edit", credit=credit, students=students, courses=courses)


@app.route("/credits/delete/<int:credit_id>", methods=["POST"])
def credit_delete(credit_id):
    """
    Delete: Removes a credit record.
    Credits are child leaf nodes, so removal is safe and does not violate parent constraints.
    """
    try:
        db.execute("DELETE FROM Credit WHERE CreditId = ?", (credit_id,))
        flash(f"Credit record #{credit_id} removed.", "success")
    except Exception as e:
        flash(f"Deletion failed: {e}", "danger")

    return redirect(url_for("credit_list"))


# =============================================================================
# VerificationTable Routes (Lab Audit Log & Verification)
# =============================================================================
@app.route("/verifications")
def verification_list():
    """Read: Displays all audit records from dbo.VerificationTable."""
    records = db.query_all("SELECT * FROM VerificationTable ORDER BY VerificationId DESC")
    return render_template("verification_list.html", records=records)


@app.route("/verifications/create", methods=["POST"])
def verification_create():
    """Create: Log an explicit verification checkpoint for Lab 2 demonstration."""
    student_name = request.form.get("student_name", "").strip() or "IST210 Student"
    action_type = request.form.get("action_type", "LAB2_CHECKPOINT").strip()
    details = request.form.get("details", "").strip() or "Interactive CRUD operation completed"
    code = f"VERIF-LAB2-{int(datetime.now().timestamp())}"

    try:
        new_id = db.execute(
            "INSERT INTO VerificationTable (StudentName, ActionType, Details, VerificationCode) VALUES (?, ?, ?, ?)",
            (student_name, action_type, details, code)
        )
        flash(f"Verification checkpoint logged with Code: {code}", "success")
    except Exception as e:
        flash(f"Failed to log verification: {e}", "danger")

    return redirect(url_for("verification_list"))


# =============================================================================
# Health / API Status Endpoint
# =============================================================================
@app.route("/api/status")
def api_status():
    """Returns application and database connectivity status as JSON."""
    return jsonify({
        "status": "online",
        "active_backend": db.active_engine,
        "auth_mode": db.auth_mode,
        "server": db.server,
        "database": db.database,
        "connection_error": db.connection_error,
        "table_counts": {
            "Person": db.query_one("SELECT COUNT(*) AS c FROM Person")["c"],
            "Student": db.query_one("SELECT COUNT(*) AS c FROM Student")["c"],
            "Course": db.query_one("SELECT COUNT(*) AS c FROM Course")["c"],
            "Credit": db.query_one("SELECT COUNT(*) AS c FROM Credit")["c"],
            "VerificationTable": db.query_one("SELECT COUNT(*) AS c FROM VerificationTable")["c"],
        }
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Starting IST 210 Lab 2 Web Application on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
