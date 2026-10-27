"""
init_db.py - Database Initialization and Seed Script for IST 210 Lab 2
Creates tables for Person, Student, Course, Credit, and VerificationTable.
Populates standard mock/tutorial records for development, testing, and grading.
"""

import sys
import os

# Ensure current directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import db, PYODBC_AVAILABLE


SQL_SERVER_SCHEMA = """
-- 1. Person Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Person' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.Person (
        PersonId INT IDENTITY(1,1) PRIMARY KEY,
        FirstName NVARCHAR(128) NOT NULL,
        MiddleInitial NVARCHAR(10) NULL,
        LastName NVARCHAR(128) NOT NULL,
        DateOfBirth DATE NOT NULL
    );
END;

-- 2. Student Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Student' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.Student (
        StudentId INT IDENTITY(1,1) PRIMARY KEY,
        PersonId INT NOT NULL,
        Email NVARCHAR(256) NOT NULL,
        CONSTRAINT FK_Student_Person FOREIGN KEY (PersonId) 
            REFERENCES dbo.Person(PersonId)
            ON DELETE NO ACTION
            ON UPDATE CASCADE
    );
END;

-- 3. Course Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Course' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.Course (
        CourseId INT IDENTITY(1,1) PRIMARY KEY,
        Name NVARCHAR(50) NOT NULL,
        Teacher NVARCHAR(256) NOT NULL
    );
END;

-- 4. Credit Table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Credit' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.Credit (
        CreditId INT IDENTITY(1,1) PRIMARY KEY,
        StudentId INT NOT NULL,
        CourseId INT NOT NULL,
        Grade DECIMAL(5, 2) NULL CHECK (Grade >= 0.00 AND Grade <= 100.00),
        Attempt TINYINT NOT NULL DEFAULT 1,
        CONSTRAINT FK_Credit_Student FOREIGN KEY (StudentId) 
            REFERENCES dbo.Student(StudentId)
            ON DELETE NO ACTION
            ON UPDATE CASCADE,
        CONSTRAINT FK_Credit_Course FOREIGN KEY (CourseId) 
            REFERENCES dbo.Course(CourseId)
            ON DELETE NO ACTION
            ON UPDATE CASCADE,
        CONSTRAINT UQ_Student_Course_Attempt UNIQUE (StudentId, CourseId, Attempt)
    );
END;

-- 5. VerificationTable
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'VerificationTable' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.VerificationTable (
        VerificationId INT IDENTITY(1,1) PRIMARY KEY,
        StudentName NVARCHAR(128) NOT NULL,
        ActionType NVARCHAR(64) NOT NULL,
        Details NVARCHAR(512) NULL,
        VerificationCode NVARCHAR(64) NOT NULL,
        Timestamp DATETIME2 DEFAULT SYSDATETIME()
    );
END;
"""

SQLITE_SCHEMA = """
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
"""


def init_database():
    print("=" * 65)
    print("IST 210 Lab 2 - Database Initialization")
    print(f"Active Backend: {db.active_engine}")
    print(f"Auth Mode: {db.auth_mode}")
    print("=" * 65)

    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        if db.active_engine.startswith("ODBC"):
            print("Applying SQL Server schema via ODBC...")
            # Execute statement by statement
            statements = [s.strip() for s in SQL_SERVER_SCHEMA.split("END;") if s.strip()]
            for stmt in statements:
                full_stmt = stmt + " END;"
                cursor.execute(full_stmt)
            conn.commit()
        else:
            print("Applying SQLite schema...")
            conn.executescript(SQLITE_SCHEMA)
            conn.commit()

        print("[OK] Schema verified and created successfully.")

        # Seed sample data if empty
        existing_persons = db.query_all("SELECT COUNT(*) AS cnt FROM Person")[0]["cnt"]
        if existing_persons == 0:
            print("Seeding sample Microsoft Learn tutorial records...")

            # 1. Seed Person
            persons_data = [
                ("Dong", "M", "Miller", "2002-04-15"),
                ("Sarah", "J", "Connor", "2001-11-20"),
                ("Alex", "T", "Mercer", "2003-01-10"),
                ("Emily", "R", "Watson", "2002-09-05"),
                ("Marcus", "L", "Fenix", "2000-06-30"),
            ]
            for p in persons_data:
                db.execute(
                    "INSERT INTO Person (FirstName, MiddleInitial, LastName, DateOfBirth) VALUES (?, ?, ?, ?)",
                    p
                )

            # 2. Seed Student (linked to Persons)
            students_data = [
                (1, "dong.miller@psu.edu"),
                (2, "sarah.connor@psu.edu"),
                (3, "alex.mercer@psu.edu"),
                (4, "emily.watson@psu.edu"),
            ]
            for s in students_data:
                db.execute("INSERT INTO Student (PersonId, Email) VALUES (?, ?)", s)

            # 3. Seed Course
            courses_data = [
                ("IST 210: Organization of Data", "Prof. Dong"),
                ("IST 140: Introduction to App Development", "Dr. Alan Turing"),
                ("IST 220: Networking and Telecommunications", "Prof. Ada Lovelace"),
                ("IST 256: Programming for the Web", "Dr. Grace Hopper"),
            ]
            for c in courses_data:
                db.execute("INSERT INTO Course (Name, Teacher) VALUES (?, ?)", c)

            # 4. Seed Credit (Junction records)
            credits_data = [
                (1, 1, 95.50, 1),
                (1, 2, 88.00, 1),
                (2, 1, 91.00, 1),
                (2, 3, 84.50, 1),
                (3, 1, 78.00, 1),
                (3, 4, 92.00, 1),
                (4, 2, 97.50, 1),
            ]
            for cr in credits_data:
                db.execute("INSERT INTO Credit (StudentId, CourseId, Grade, Attempt) VALUES (?, ?, ?, ?)", cr)

            # 5. Seed VerificationTable
            db.execute(
                "INSERT INTO VerificationTable (StudentName, ActionType, Details, VerificationCode) VALUES (?, ?, ?, ?)",
                ("System Init", "DATABASE_INITIALIZED", "Seeded Lab 1 tables with default records", "VERIF-INIT-SUCCESS-2026")
            )

            print("[OK] Seeded 5 Persons, 4 Students, 4 Courses, 7 Credit records, and 1 Verification record.")
        else:
            print(f"[Info] Database already contains {existing_persons} Person records. Skipping seed.")

    finally:
        cursor.close()
        conn.close()

    print("=" * 65)
    print("Database is ready for live CRUD web application operations!")
    print("=" * 65)


if __name__ == "__main__":
    init_database()
