"""
standalone_server.py - Zero-Dependency Runner for IST 210 Lab 2
If Flask is installed: launches the full Flask web application (app.py).
If Flask is NOT yet installed: automatically runs a built-in lightweight HTTP server
using Python's standard library (http.server + sqlite3) so you can test all CRUD operations
immediately without needing pip install!
"""

import sys
import os

# Check if flask is available
try:
    import flask
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

if FLASK_AVAILABLE:
    print("[Launcher] Flask is installed. Starting standard production application...")
    from app import app
    port = int(os.getenv("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=True)
else:
    print("[Launcher] Flask not detected in environment.")
    print("[Launcher] Starting Zero-Dependency Standard Library Web Server...")
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import parse_qs, urlparse
    import sqlite3

    DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ist210_lab.db")

    # Initialize SQLite database if needed
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS Person (
            PersonId INTEGER PRIMARY KEY AUTOINCREMENT,
            FirstName TEXT NOT NULL,
            MiddleInitial TEXT,
            LastName TEXT NOT NULL,
            DateOfBirth TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS Student (
            StudentId INTEGER PRIMARY KEY AUTOINCREMENT,
            PersonId INTEGER NOT NULL,
            Email TEXT NOT NULL,
            FOREIGN KEY (PersonId) REFERENCES Person(PersonId) ON DELETE NO ACTION ON UPDATE CASCADE
        );
        CREATE TABLE IF NOT EXISTS Course (
            CourseId INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL,
            Teacher TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS Credit (
            CreditId INTEGER PRIMARY KEY AUTOINCREMENT,
            StudentId INTEGER NOT NULL,
            CourseId INTEGER NOT NULL,
            Grade REAL CHECK (Grade >= 0.00 AND Grade <= 100.00),
            Attempt INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (StudentId) REFERENCES Student(StudentId) ON DELETE NO ACTION ON UPDATE CASCADE,
            FOREIGN KEY (CourseId) REFERENCES Course(CourseId) ON DELETE NO ACTION ON UPDATE CASCADE,
            UNIQUE (StudentId, CourseId, Attempt)
        );
        CREATE TABLE IF NOT EXISTS VerificationTable (
            VerificationId INTEGER PRIMARY KEY AUTOINCREMENT,
            StudentName TEXT NOT NULL,
            ActionType TEXT NOT NULL,
            Details TEXT,
            VerificationCode TEXT NOT NULL,
            Timestamp TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)
    conn.commit()

    # Seed if empty
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM Person")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO Person (FirstName, MiddleInitial, LastName, DateOfBirth) VALUES (?, ?, ?, ?)", [
            ("Dong", "M", "Miller", "2002-04-15"),
            ("Sarah", "J", "Connor", "2001-11-20"),
            ("Alex", "T", "Mercer", "2003-01-10"),
            ("Emily", "R", "Watson", "2002-09-05")
        ])
        cur.executemany("INSERT INTO Student (PersonId, Email) VALUES (?, ?)", [
            (1, "dong.miller@psu.edu"),
            (2, "sarah.connor@psu.edu"),
            (3, "alex.mercer@psu.edu"),
            (4, "emily.watson@psu.edu")
        ])
        cur.executemany("INSERT INTO Course (Name, Teacher) VALUES (?, ?)", [
            ("IST 210: Organization of Data", "Prof. Dong"),
            ("IST 140: Introduction to App Development", "Dr. Alan Turing"),
            ("IST 220: Networking and Telecommunications", "Prof. Ada Lovelace")
        ])
        cur.executemany("INSERT INTO Credit (StudentId, CourseId, Grade, Attempt) VALUES (?, ?, ?, ?)", [
            (1, 1, 95.5, 1),
            (2, 1, 91.0, 1),
            (3, 2, 88.5, 1),
            (4, 3, 97.0, 1)
        ])
        cur.execute("INSERT INTO VerificationTable (StudentName, ActionType, Details, VerificationCode) VALUES (?, ?, ?, ?)",
            ("System Init", "DATABASE_INITIALIZED", "Seeded Lab 1 tables", "VERIF-INIT-SUCCESS-2026")
        )
        conn.commit()
    conn.close()

    class StandaloneHandler(BaseHTTPRequestHandler):
        def get_db(self):
            c = sqlite3.connect(DB_FILE)
            c.execute("PRAGMA foreign_keys = ON;")
            c.row_factory = sqlite3.Row
            return c

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            if path in ["/", "/dashboard"]:
                self.render_dashboard(params.get("q", [""])[0])
            elif path == "/persons":
                self.render_persons(params.get("edit", [None])[0])
            elif path == "/students":
                self.render_students(params.get("edit", [None])[0])
            elif path == "/courses":
                self.render_courses(params.get("edit", [None])[0])
            elif path == "/credits":
                self.render_credits(params.get("edit", [None])[0])
            elif path == "/verifications":
                self.render_verifications()
            else:
                self.send_response(302)
                self.send_header("Location", "/dashboard")
                self.end_headers()

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = {k: v[0] for k, v in parse_qs(body).items()}

            conn = self.get_db()
            cur = conn.cursor()

            try:
                if path == "/persons/create":
                    cur.execute("INSERT INTO Person (FirstName, MiddleInitial, LastName, DateOfBirth) VALUES (?, ?, ?, ?)",
                                (data.get("first_name", ""), data.get("middle_initial", "") or None, data.get("last_name", ""), data.get("dob", "")))
                    conn.commit()
                    self.redirect("/persons")
                elif path == "/persons/update":
                    cur.execute("UPDATE Person SET FirstName = ?, MiddleInitial = ?, LastName = ?, DateOfBirth = ? WHERE PersonId = ?",
                                (data.get("first_name", ""), data.get("middle_initial", "") or None, data.get("last_name", ""), data.get("dob", ""), int(data.get("person_id"))))
                    conn.commit()
                    self.redirect("/persons")
                elif path == "/persons/delete":
                    pid = int(data.get("person_id"))
                    # Enforce ON DELETE NO ACTION
                    cur.execute("SELECT COUNT(*) FROM Student WHERE PersonId = ?", (pid,))
                    if cur.fetchone()[0] > 0:
                        self.render_error(f"Referential Integrity Rule (ON DELETE NO ACTION): Cannot delete Person #{pid} because an active Student references it!")
                        return
                    cur.execute("DELETE FROM Person WHERE PersonId = ?", (pid,))
                    conn.commit()
                    self.redirect("/persons")
                elif path == "/students/create":
                    cur.execute("INSERT INTO Student (PersonId, Email) VALUES (?, ?)", (int(data.get("person_id")), data.get("email", "")))
                    conn.commit()
                    self.redirect("/students")
                elif path == "/students/update":
                    cur.execute("UPDATE Student SET PersonId = ?, Email = ? WHERE StudentId = ?",
                                (int(data.get("person_id")), data.get("email", ""), int(data.get("student_id"))))
                    conn.commit()
                    self.redirect("/students")
                elif path == "/students/delete":
                    sid = int(data.get("student_id"))
                    cur.execute("SELECT COUNT(*) FROM Credit WHERE StudentId = ?", (sid,))
                    if cur.fetchone()[0] > 0:
                        self.render_error(f"Referential Integrity Rule (ON DELETE NO ACTION): Cannot delete Student #{sid} because active Credit records reference this student!")
                        return
                    cur.execute("DELETE FROM Student WHERE StudentId = ?", (sid,))
                    conn.commit()
                    self.redirect("/students")
                elif path == "/courses/create":
                    cur.execute("INSERT INTO Course (Name, Teacher) VALUES (?, ?)", (data.get("name", ""), data.get("teacher", "")))
                    conn.commit()
                    self.redirect("/courses")
                elif path == "/courses/update":
                    cur.execute("UPDATE Course SET Name = ?, Teacher = ? WHERE CourseId = ?",
                                (data.get("name", ""), data.get("teacher", ""), int(data.get("course_id"))))
                    conn.commit()
                    self.redirect("/courses")
                elif path == "/courses/delete":
                    cid = int(data.get("course_id"))
                    cur.execute("SELECT COUNT(*) FROM Credit WHERE CourseId = ?", (cid,))
                    if cur.fetchone()[0] > 0:
                        self.render_error(f"Referential Integrity Rule (ON DELETE NO ACTION): Cannot delete Course #{cid} because active Credit records reference this course!")
                        return
                    cur.execute("DELETE FROM Course WHERE CourseId = ?", (cid,))
                    conn.commit()
                    self.redirect("/courses")
                elif path == "/credits/create":
                    cur.execute("INSERT INTO Credit (StudentId, CourseId, Grade, Attempt) VALUES (?, ?, ?, ?)",
                                (int(data.get("student_id")), int(data.get("course_id")), float(data.get("grade", 0)), int(data.get("attempt", 1))))
                    conn.commit()
                    self.redirect("/credits")
                elif path == "/credits/update":
                    cur.execute("UPDATE Credit SET StudentId = ?, CourseId = ?, Grade = ?, Attempt = ? WHERE CreditId = ?",
                                (int(data.get("student_id")), int(data.get("course_id")), float(data.get("grade", 0)), int(data.get("attempt", 1)), int(data.get("credit_id"))))
                    conn.commit()
                    self.redirect("/credits")
                elif path == "/credits/delete":
                    crid = int(data.get("credit_id"))
                    cur.execute("DELETE FROM Credit WHERE CreditId = ?", (crid,))
                    conn.commit()
                    self.redirect("/credits")
                elif path == "/verifications/create":
                    cur.execute("INSERT INTO VerificationTable (StudentName, ActionType, Details, VerificationCode) VALUES (?, ?, ?, ?)",
                                (data.get("student_name", "Student"), data.get("action_type", "LAB2_VERIFIED"), data.get("details", ""), "VERIF-LAB2-STANDALONE"))
                    conn.commit()
                    self.redirect("/verifications")
            except Exception as e:
                self.render_error(f"Database Exception: {e}")
            finally:
                conn.close()

        def redirect(self, location):
            self.send_response(303)
            self.send_header("Location", location)
            self.end_headers()

        def render_error(self, message):
            html = f"""<!DOCTYPE html><html><head><title>Integrity Constraint Blocked</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            </head><body class="p-5 bg-light"><div class="container"><div class="alert alert-danger shadow border-start border-4 border-danger">
            <h4><i class="bi bi-shield-x"></i> Referential Integrity Alert (ON DELETE NO ACTION)</h4>
            <p>{message}</p><a href="javascript:history.back()" class="btn btn-outline-danger">Go Back</a>
            </div></div></body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def render_dashboard(self, q=""):
            conn = self.get_db()
            cur = conn.cursor()
            if q:
                sql = """SELECT s.StudentId, p.FirstName, p.LastName, s.Email, c.Name as CourseName, c.Teacher, cr.CreditId, cr.Grade, cr.Attempt
                         FROM Student s JOIN Person p ON s.PersonId = p.PersonId
                         LEFT JOIN Credit cr ON s.StudentId = cr.StudentId
                         LEFT JOIN Course c ON cr.CourseId = c.CourseId
                         WHERE p.FirstName LIKE ? OR p.LastName LIKE ? OR c.Name LIKE ? ORDER BY p.LastName"""
                p = f"%{q}%"
                cur.execute(sql, (p, p, p))
            else:
                sql = """SELECT s.StudentId, p.FirstName, p.LastName, s.Email, c.Name as CourseName, c.Teacher, cr.CreditId, cr.Grade, cr.Attempt
                         FROM Student s JOIN Person p ON s.PersonId = p.PersonId
                         LEFT JOIN Credit cr ON s.StudentId = cr.StudentId
                         LEFT JOIN Course c ON cr.CourseId = c.CourseId ORDER BY p.LastName"""
                cur.execute(sql)
            rows = cur.fetchall()

            rows_html = "".join([f"""<tr>
                <td class="fw-bold text-primary">#{r['StudentId']}</td>
                <td>{r['FirstName']} {r['LastName']}</td>
                <td>{r['Email']}</td>
                <td><span class="badge bg-light text-dark border">{r['CourseName'] or 'No course'}</span></td>
                <td>{r['Teacher'] or '&mdash;'}</td>
                <td><span class="badge bg-success-subtle text-success">{r['Grade'] or 'N/A'}%</span></td>
                <td>Attempt #{r['Attempt'] or 1}</td>
                <td>{"<a href='/credits?edit=" + str(r['CreditId']) + "' class='btn btn-sm btn-primary fw-semibold'>✏️ Edit</a>" if r['CreditId'] else ""}</td>
            </tr>""" for r in rows])

            html = self.wrap_layout(f"""
                <div class="row g-3 mb-4">
                    <div class="col-md-3"><div class="card p-3 shadow-sm border-start border-4 border-primary"><h6>Students</h6><h3>{len(rows)}</h3></div></div>
                    <div class="col-md-3"><div class="card p-3 shadow-sm border-start border-4 border-success"><h6>Relational Mode</h6><h3>Multi-JOIN</h3></div></div>
                    <div class="col-md-3"><div class="card p-3 shadow-sm border-start border-4 border-info"><h6>Parameterization</h6><h3>100% Enforced</h3></div></div>
                    <div class="col-md-3"><div class="card p-3 shadow-sm border-start border-4 border-warning"><h6>Integrity</h6><h3>NO ACTION</h3></div></div>
                </div>
                <div class="card shadow-sm mb-4">
                    <div class="card-header bg-white d-flex justify-content-between align-items-center py-3">
                        <h5 class="mb-0 fw-bold">Academic Performance Dashboard (Multi-Table JOIN)</h5>
                        <form method="GET" action="/dashboard" class="d-flex"><input type="text" name="q" class="form-control form-control-sm me-2" placeholder="Search..." value="{q}"><button class="btn btn-sm btn-primary">Search</button></form>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0">
                            <thead class="table-light"><tr><th>ID</th><th>Student</th><th>Email</th><th>Course</th><th>Instructor</th><th>Grade</th><th>Attempt</th><th>Action</th></tr></thead>
                            <tbody>{rows_html}</tbody>
                        </table>
                    </div>
                </div>
            """)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def render_persons(self, edit_id=None):
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM Person ORDER BY LastName")
            rows = cur.fetchall()

            edit_record = None
            if edit_id:
                cur.execute("SELECT * FROM Person WHERE PersonId = ?", (int(edit_id),))
                edit_record = cur.fetchone()

            rows_html = "".join([f"""<tr>
                <td>#{r['PersonId']}</td><td>{r['FirstName']} {r['LastName']}</td><td>{r['DateOfBirth']}</td>
                <td class="d-flex gap-1">
                    <a href="/persons?edit={r['PersonId']}" class="btn btn-sm btn-primary fw-semibold">✏️ Edit</a>
                    <form method="POST" action="/persons/delete" onsubmit="return confirm('Delete Person #{r['PersonId']}?');">
                    <input type="hidden" name="person_id" value="{r['PersonId']}"><button class="btn btn-sm btn-outline-danger">🗑️ Delete</button></form>
                </td>
            </tr>""" for r in rows])

            if edit_record:
                form_title = f"Edit Person #{edit_record['PersonId']}"
                form_action = "/persons/update"
                btn_text = "Update Person"
                fn_val = edit_record['FirstName']
                ln_val = edit_record['LastName']
                dob_val = edit_record['DateOfBirth']
                extra_hidden = f'<input type="hidden" name="person_id" value="{edit_record["PersonId"]}">'
                cancel_link = '<a href="/persons" class="btn btn-sm btn-outline-secondary w-100 mt-2">Cancel</a>'
            else:
                form_title = "Create New Person"
                form_action = "/persons/create"
                btn_text = "Save Person"
                fn_val = ""
                ln_val = ""
                dob_val = ""
                extra_hidden = ""
                cancel_link = ""

            content = f"""
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4>Person Master Records</h4>
            </div>
            <div class="row g-4">
                <div class="col-md-4">
                    <div class="card shadow-sm p-3">
                        <h6 class="fw-bold">{form_title}</h6>
                        <form method="POST" action="{form_action}">
                            {extra_hidden}
                            <div class="mb-2"><label class="small">First Name</label><input type="text" name="first_name" class="form-control form-control-sm" value="{fn_val}" required></div>
                            <div class="mb-2"><label class="small">Last Name</label><input type="text" name="last_name" class="form-control form-control-sm" value="{ln_val}" required></div>
                            <div class="mb-2"><label class="small">Date of Birth</label><input type="date" name="dob" class="form-control form-control-sm" value="{dob_val}" required></div>
                            <button class="btn btn-sm btn-primary w-100">{btn_text}</button>
                            {cancel_link}
                        </form>
                    </div>
                </div>
                <div class="col-md-8">
                    <div class="card shadow-sm">
                        <table class="table table-hover mb-0">
                            <thead class="table-light"><tr><th>ID</th><th>Name</th><th>DOB</th><th>Actions</th></tr></thead>
                            <tbody>{rows_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>"""
            html = self.wrap_layout(content)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def render_students(self, edit_id=None):
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("SELECT s.StudentId, s.PersonId, s.Email, p.FirstName, p.LastName FROM Student s JOIN Person p ON s.PersonId = p.PersonId")
            rows = cur.fetchall()
            cur.execute("SELECT PersonId, FirstName, LastName FROM Person ORDER BY LastName")
            persons = cur.fetchall()

            edit_record = None
            if edit_id:
                cur.execute("SELECT * FROM Student WHERE StudentId = ?", (int(edit_id),))
                edit_record = cur.fetchone()

            p_opts = "".join([f"<option value='{p['PersonId']}' {'selected' if edit_record and edit_record['PersonId'] == p['PersonId'] else ''}>#{p['PersonId']} - {p['LastName']}, {p['FirstName']}</option>" for p in persons])

            rows_html = "".join([f"""<tr>
                <td>#{r['StudentId']}</td><td>{r['FirstName']} {r['LastName']}</td><td>{r['Email']}</td>
                <td class="d-flex gap-1">
                    <a href="/students?edit={r['StudentId']}" class="btn btn-sm btn-primary fw-semibold">✏️ Edit</a>
                    <form method="POST" action="/students/delete" onsubmit="return confirm('Delete Student #{r['StudentId']}?');">
                    <input type="hidden" name="student_id" value="{r['StudentId']}"><button class="btn btn-sm btn-outline-danger">🗑️ Delete</button></form>
                </td>
            </tr>""" for r in rows])

            if edit_record:
                form_title = f"Edit Student #{edit_record['StudentId']}"
                form_action = "/students/update"
                btn_text = "Update Student"
                email_val = edit_record['Email']
                extra_hidden = f'<input type="hidden" name="student_id" value="{edit_record["StudentId"]}">'
                cancel_link = '<a href="/students" class="btn btn-sm btn-outline-secondary w-100 mt-2">Cancel</a>'
            else:
                form_title = "Register Student"
                form_action = "/students/create"
                btn_text = "Register"
                email_val = ""
                extra_hidden = ""
                cancel_link = ""

            content = f"""
            <div class="row g-4">
                <div class="col-md-4">
                    <div class="card shadow-sm p-3">
                        <h6 class="fw-bold">{form_title}</h6>
                        <form method="POST" action="{form_action}">
                            {extra_hidden}
                            <div class="mb-2"><label class="small">Person</label><select name="person_id" class="form-select form-select-sm" required>{p_opts}</select></div>
                            <div class="mb-2"><label class="small">Email</label><input type="email" name="email" class="form-control form-control-sm" value="{email_val}" required></div>
                            <button class="btn btn-sm btn-primary w-100">{btn_text}</button>
                            {cancel_link}
                        </form>
                    </div>
                </div>
                <div class="col-md-8">
                    <div class="card shadow-sm">
                        <table class="table table-hover mb-0">
                            <thead class="table-light"><tr><th>ID</th><th>Student</th><th>Email</th><th>Actions</th></tr></thead>
                            <tbody>{rows_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>"""
            html = self.wrap_layout(content)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def render_courses(self, edit_id=None):
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM Course ORDER BY Name")
            rows = cur.fetchall()

            edit_record = None
            if edit_id:
                cur.execute("SELECT * FROM Course WHERE CourseId = ?", (int(edit_id),))
                edit_record = cur.fetchone()

            rows_html = "".join([f"""<tr>
                <td>#{r['CourseId']}</td><td>{r['Name']}</td><td>{r['Teacher']}</td>
                <td class="d-flex gap-1">
                    <a href="/courses?edit={r['CourseId']}" class="btn btn-sm btn-primary fw-semibold">✏️ Edit</a>
                    <form method="POST" action="/courses/delete" onsubmit="return confirm('Delete Course #{r['CourseId']}?');">
                    <input type="hidden" name="course_id" value="{r['CourseId']}"><button class="btn btn-sm btn-outline-danger">🗑️ Delete</button></form>
                </td>
            </tr>""" for r in rows])

            if edit_record:
                form_title = f"Edit Course #{edit_record['CourseId']}"
                form_action = "/courses/update"
                btn_text = "Update Course"
                name_val = edit_record['Name']
                teacher_val = edit_record['Teacher']
                extra_hidden = f'<input type="hidden" name="course_id" value="{edit_record["CourseId"]}">'
                cancel_link = '<a href="/courses" class="btn btn-sm btn-outline-secondary w-100 mt-2">Cancel</a>'
            else:
                form_title = "Create Course"
                form_action = "/courses/create"
                btn_text = "Save Course"
                name_val = ""
                teacher_val = ""
                extra_hidden = ""
                cancel_link = ""

            content = f"""
            <div class="row g-4">
                <div class="col-md-4">
                    <div class="card shadow-sm p-3">
                        <h6 class="fw-bold">{form_title}</h6>
                        <form method="POST" action="{form_action}">
                            {extra_hidden}
                            <div class="mb-2"><label class="small">Course Name</label><input type="text" name="name" class="form-control form-control-sm" value="{name_val}" required></div>
                            <div class="mb-2"><label class="small">Teacher</label><input type="text" name="teacher" class="form-control form-control-sm" value="{teacher_val}" required></div>
                            <button class="btn btn-sm btn-primary w-100">{btn_text}</button>
                            {cancel_link}
                        </form>
                    </div>
                </div>
                <div class="col-md-8">
                    <div class="card shadow-sm">
                        <table class="table table-hover mb-0">
                            <thead class="table-light"><tr><th>ID</th><th>Course</th><th>Teacher</th><th>Actions</th></tr></thead>
                            <tbody>{rows_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>"""
            html = self.wrap_layout(content)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def render_credits(self, edit_id=None):
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("SELECT cr.CreditId, cr.Grade, cr.Attempt, p.FirstName, p.LastName, c.Name as CourseName FROM Credit cr JOIN Student s ON cr.StudentId = s.StudentId JOIN Person p ON s.PersonId = p.PersonId JOIN Course c ON cr.CourseId = c.CourseId")
            rows = cur.fetchall()

            edit_record = None
            if edit_id:
                cur.execute("SELECT * FROM Credit WHERE CreditId = ?", (int(edit_id),))
                edit_record = cur.fetchone()

            cur.execute("SELECT s.StudentId, p.FirstName, p.LastName FROM Student s JOIN Person p ON s.PersonId = p.PersonId")
            students = cur.fetchall()
            s_opts = "".join([f"<option value='{s['StudentId']}' {'selected' if edit_record and edit_record['StudentId'] == s['StudentId'] else ''}>#{s['StudentId']} - {s['LastName']}, {s['FirstName']}</option>" for s in students])

            cur.execute("SELECT CourseId, Name FROM Course")
            courses = cur.fetchall()
            c_opts = "".join([f"<option value='{c['CourseId']}' {'selected' if edit_record and edit_record['CourseId'] == c['CourseId'] else ''}>#{c['CourseId']} - {c['Name']}</option>" for c in courses])

            rows_html = "".join([f"""<tr>
                <td>#{r['CreditId']}</td><td>{r['FirstName']} {r['LastName']}</td><td>{r['CourseName']}</td><td>{r['Grade']}%</td><td>Attempt #{r['Attempt']}</td>
                <td class="d-flex gap-1">
                    <a href="/credits?edit={r['CreditId']}" class="btn btn-sm btn-primary fw-semibold">✏️ Edit</a>
                    <form method="POST" action="/credits/delete" onsubmit="return confirm('Delete Credit #{r['CreditId']}?');">
                    <input type="hidden" name="credit_id" value="{r['CreditId']}"><button class="btn btn-sm btn-outline-danger">🗑️ Delete</button></form>
                </td>
            </tr>""" for r in rows])

            if edit_record:
                form_title = f"Edit Credit #{edit_record['CreditId']}"
                form_action = "/credits/update"
                btn_text = "Update Credit"
                grade_val = edit_record['Grade']
                attempt_val = edit_record['Attempt']
                extra_hidden = f'<input type="hidden" name="credit_id" value="{edit_record["CreditId"]}">'
                cancel_link = '<a href="/credits" class="btn btn-sm btn-outline-secondary w-100 mt-2">Cancel</a>'
            else:
                form_title = "Record Course Credit"
                form_action = "/credits/create"
                btn_text = "Save Credit"
                grade_val = ""
                attempt_val = 1
                extra_hidden = ""
                cancel_link = ""

            content = f"""
            <div class="row g-4">
                <div class="col-md-4">
                    <div class="card shadow-sm p-3">
                        <h6 class="fw-bold">{form_title}</h6>
                        <form method="POST" action="{form_action}">
                            {extra_hidden}
                            <div class="mb-2"><label class="small">Student</label><select name="student_id" class="form-select form-select-sm" required>{s_opts}</select></div>
                            <div class="mb-2"><label class="small">Course</label><select name="course_id" class="form-select form-select-sm" required>{c_opts}</select></div>
                            <div class="mb-2"><label class="small">Grade %</label><input type="number" step="0.01" min="0" max="100" name="grade" class="form-control form-control-sm" value="{grade_val}" required></div>
                            <div class="mb-2"><label class="small">Attempt</label><input type="number" min="1" max="10" name="attempt" value="{attempt_val}" class="form-control form-control-sm" required></div>
                            <button class="btn btn-sm btn-primary w-100">{btn_text}</button>
                            {cancel_link}
                        </form>
                    </div>
                </div>
                <div class="col-md-8">
                    <div class="card shadow-sm">
                        <table class="table table-hover mb-0">
                            <thead class="table-light"><tr><th>ID</th><th>Student</th><th>Course</th><th>Grade</th><th>Attempt</th><th>Actions</th></tr></thead>
                            <tbody>{rows_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>"""
            html = self.wrap_layout(content)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def render_verifications(self):
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM VerificationTable ORDER BY VerificationId DESC")
            rows = cur.fetchall()
            rows_html = "".join([f"""<tr>
                <td>#{r['VerificationId']}</td><td>{r['StudentName']}</td><td><span class="badge bg-primary-subtle text-primary">{r['ActionType']}</span></td><td>{r['Details']}</td><td><code>{r['VerificationCode']}</code></td><td>{r['Timestamp']}</td>
            </tr>""" for r in rows])

            content = f"""
            <div class="card shadow-sm p-3 mb-4">
                <h6 class="fw-bold">Log Verification Checkpoint</h6>
                <form method="POST" action="/verifications/create" class="row g-2">
                    <div class="col-md-3"><input type="text" name="student_name" class="form-control form-control-sm" placeholder="Student Name" required></div>
                    <div class="col-md-3"><input type="text" name="action_type" class="form-control form-control-sm" value="LAB2_CRUD_VERIFIED"></div>
                    <div class="col-md-4"><input type="text" name="details" class="form-control form-control-sm" placeholder="Details"></div>
                    <div class="col-md-2"><button class="btn btn-sm btn-success w-100">Log Checkpoint</button></div>
                </form>
            </div>
            <div class="card shadow-sm">
                <table class="table table-hover mb-0">
                    <thead class="table-light"><tr><th>ID</th><th>Student</th><th>Action</th><th>Details</th><th>Code</th><th>Timestamp</th></tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>"""
            html = self.wrap_layout(content)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def wrap_layout(self, content):
            return f"""<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>IST 210 Lab 2 CRUD Web Application</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            </head>
            <body class="bg-light">
                <nav class="navbar navbar-expand-lg navbar-dark bg-primary mb-4 px-4 shadow-sm">
                    <a class="navbar-brand fw-bold" href="/dashboard">IST 210 Lab 2 CRUD</a>
                    <div class="navbar-nav me-auto">
                        <a class="nav-link" href="/dashboard">Dashboard (JOIN)</a>
                        <a class="nav-link" href="/persons">Persons</a>
                        <a class="nav-link" href="/students">Students</a>
                        <a class="nav-link" href="/courses">Courses</a>
                        <a class="nav-link" href="/credits">Credits</a>
                        <a class="nav-link" href="/verifications">Verifications</a>
                    </div>
                    <span class="badge bg-light text-dark">Zero-Dependency Mode (SQLite Fallback)</span>
                </nav>
                <div class="container-fluid px-4">{content}</div>
            </body>
            </html>"""

    import webbrowser
    import threading

    # Try binding to port 5000, or fall back to alternative ports if occupied
    ports_to_try = [5000, 5050, 8080, 8000]
    server = None
    selected_port = None

    for p in ports_to_try:
        try:
            # Bind to "" (0.0.0.0) so both localhost (IPv4/IPv6) and 127.0.0.1 work
            server = HTTPServer(("", p), StandaloneHandler)
            selected_port = p
            break
        except OSError:
            continue

    if server is None:
        print("[ERROR] Could not bind to any available port (tried 5000, 5050, 8080, 8000).")
        sys.exit(1)

    url = f"http://localhost:{selected_port}"
    print("=" * 65)
    print(f"IST 210 Lab 2 Web Server running at: {url}")
    print(f"Also accessible via: http://127.0.0.1:{selected_port}")
    print("Opening web browser automatically...")
    print("Press Ctrl+C in this window to stop the server.")
    print("=" * 65)

    # Automatically launch default browser after 1 second
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    server.serve_forever()
