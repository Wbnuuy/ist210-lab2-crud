-- IST 210 Lab 1 & Lab 2 Database Schema
-- Microsoft Learn Tutorial: Design a Relational Database in Azure SQL Database
-- Tables: Person, Student, Course, Credit, VerificationTable

-- 1. Create Person Table (Parent Table)
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

-- 2. Create Student Table (Child Table of Person, Parent Table of Credit)
-- Referential Action: ON DELETE NO ACTION enforces that a Person cannot be deleted
-- if referenced by a Student.
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

-- 3. Create Course Table (Master Data, Parent Table of Credit)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Course' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.Course (
        CourseId INT IDENTITY(1,1) PRIMARY KEY,
        Name NVARCHAR(50) NOT NULL,
        Teacher NVARCHAR(256) NOT NULL
    );
END;

-- 4. Create Credit Table (Associative/Junction Table linking Student and Course)
-- Referential Action: ON DELETE NO ACTION enforces that Student or Course cannot be deleted
-- if there are active Credit/enrollment records referencing them.
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

-- 5. Create VerificationTable (Lab Verification Tracking)
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
