"""
db.py - Database Connection and Query Abstraction Layer for IST 210 Lab 2
Supports:
  1. Azure SQL Database / SQL Server with ODBC (ODBC Driver 17/18)
  2. Windows Authentication (Trusted_Connection=yes)
  3. SQL Server Authentication (UID / PWD)
  4. Microsoft Entra / Azure AD Interactive
  5. Local SQLite Fallback (with PRAGMA foreign_keys = ON)
Enforces:
  - Strict Query Parameterization
  - Referential Integrity Checking (ON DELETE NO ACTION)
"""

import os
import sys
import sqlite3
from typing import List, Dict, Any, Optional, Tuple

# Try loading python-dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try importing pyodbc if available
try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False


class DatabaseManager:
    def __init__(self):
        self.auth_mode = os.getenv("DB_AUTH_MODE", "windows").lower()
        self.server = os.getenv("DB_SERVER", "thisisalab-ist210.database.windows.net")
        self.database = os.getenv("DB_DATABASE", "ist210-db-dong")
        self.user = os.getenv("DB_USER", "")
        self.password = os.getenv("DB_PASSWORD", "")
        self.driver = os.getenv("DB_DRIVER", "{ODBC Driver 17 for SQL Server}")
        self.timeout = int(os.getenv("DB_TIMEOUT", "15"))
        self.sqlite_file = os.getenv("DB_SQLITE_FILE", "ist210_lab.db")
        
        self.active_engine = "none"
        self.connection_error = None
        self._test_connection()

    def get_odbc_connection_string(self) -> str:
        """Construct the ODBC connection string based on the chosen authentication mode."""
        if self.auth_mode == "windows":
            # Windows Authentication / Trusted Connection
            return (
                f"DRIVER={self.driver};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"Trusted_Connection=yes;"
                f"Integrated Security=True;"
                f"TrustServerCertificate=yes;"
                f"Connection Timeout={self.timeout};"
            )
        elif self.auth_mode == "sql":
            # SQL Server Authentication (Standard for Azure SQL)
            return (
                f"DRIVER={self.driver};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"UID={self.user};"
                f"PWD={self.password};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout={self.timeout};"
            )
        elif self.auth_mode == "azure_ad":
            # Microsoft Entra / Azure AD Interactive Authentication
            return (
                f"DRIVER={self.driver};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"UID={self.user};"
                f"Authentication=ActiveDirectoryInteractive;"
                f"Encrypt=yes;"
                f"Connection Timeout={self.timeout};"
            )
        else:
            return ""

    def _test_connection(self):
        """Attempts connection to the specified database backend, falling back gracefully."""
        if self.auth_mode != "sqlite" and PYODBC_AVAILABLE:
            conn_str = self.get_odbc_connection_string()
            try:
                conn = pyodbc.connect(conn_str, timeout=self.timeout)
                conn.close()
                self.active_engine = f"ODBC ({self.auth_mode})"
                self.connection_error = None
                return
            except Exception as e:
                self.connection_error = str(e)
                # Fall back to SQLite so development and verification can continue seamlessly
                print(f"[DB Warning] Could not connect via ODBC ({self.auth_mode}): {e}")
                print(f"[DB Notice] Activating local SQLite database: {self.sqlite_file}")
                self.active_engine = "SQLite (Local Fallback)"
        elif not PYODBC_AVAILABLE and self.auth_mode != "sqlite":
            self.connection_error = "pyodbc library is not installed in the current Python environment."
            self.active_engine = "SQLite (Local Fallback)"
        else:
            self.active_engine = "SQLite"

    def get_connection(self):
        """Returns an active database connection."""
        if self.active_engine.startswith("ODBC") and PYODBC_AVAILABLE:
            conn_str = self.get_odbc_connection_string()
            return pyodbc.connect(conn_str)
        else:
            conn = sqlite3.connect(self.sqlite_file)
            # Enforce Foreign Key constraints in SQLite
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.row_factory = sqlite3.Row
            return conn

    def query_all(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        Executes a SELECT query with strict parameterization.
        Returns a list of dictionaries mapping column name to value.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            if self.active_engine.startswith("ODBC"):
                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()
                results = [dict(zip(columns, row)) for row in rows]
            else:
                rows = cursor.fetchall()
                results = [dict(row) for row in rows]
            return results
        finally:
            cursor.close()
            conn.close()

    def query_one(self, sql: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        """
        Executes a SELECT query returning a single record with strict parameterization.
        """
        results = self.query_all(sql, params)
        return results[0] if results else None

    def execute(self, sql: str, params: Tuple = ()) -> int:
        """
        Executes an INSERT, UPDATE, or DELETE query with strict parameterization.
        Returns the last row ID (if applicable) or rows affected.
        Raises descriptive exceptions on foreign key constraint violations (ON DELETE NO ACTION).
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            conn.commit()
            if self.active_engine.startswith("ODBC"):
                # For SQL Server
                try:
                    cursor.execute("SELECT SCOPE_IDENTITY();")
                    row = cursor.fetchone()
                    last_id = row[0] if row and row[0] is not None else cursor.rowcount
                except Exception:
                    last_id = cursor.rowcount
            else:
                last_id = cursor.lastrowid or cursor.rowcount
            return last_id
        except Exception as e:
            conn.rollback()
            # Inspect error for Foreign Key constraint violations
            err_msg = str(e)
            if "547" in err_msg or "FOREIGN KEY" in err_msg.upper() or "constraint failed" in err_msg.lower():
                raise ReferentialIntegrityError(
                    "Referential Integrity Violation (ON DELETE NO ACTION): "
                    "This operation was blocked because related child records depend on this entry."
                ) from e
            raise e
        finally:
            cursor.close()
            conn.close()

    # =========================================================================
    # Explicit Referential Integrity Pre-Check Helpers (Security & Safety)
    # =========================================================================

    def can_delete_person(self, person_id: int) -> Tuple[bool, str]:
        """Validates if a Person can be deleted without violating foreign key constraints."""
        child_students = self.query_all(
            "SELECT StudentId, Email FROM Student WHERE PersonId = ?", (person_id,)
        )
        if child_students:
            emails = ", ".join([s["Email"] for s in child_students])
            return (
                False,
                f"Cannot delete Person #{person_id}: Blocked by ON DELETE NO ACTION rule. "
                f"Referenced by Student record(s): {emails}."
            )
        return True, "Safe to delete."

    def can_delete_student(self, student_id: int) -> Tuple[bool, str]:
        """Validates if a Student can be deleted without violating foreign key constraints."""
        child_credits = self.query_all(
            "SELECT CreditId, Grade, Attempt FROM Credit WHERE StudentId = ?", (student_id,)
        )
        if child_credits:
            return (
                False,
                f"Cannot delete Student #{student_id}: Blocked by ON DELETE NO ACTION rule. "
                f"Referenced by {len(child_credits)} academic Credit/enrollment record(s)."
            )
        return True, "Safe to delete."

    def can_delete_course(self, course_id: int) -> Tuple[bool, str]:
        """Validates if a Course can be deleted without violating foreign key constraints."""
        child_credits = self.query_all(
            "SELECT CreditId FROM Credit WHERE CourseId = ?", (course_id,)
        )
        if child_credits:
            return (
                False,
                f"Cannot delete Course #{course_id}: Blocked by ON DELETE NO ACTION rule. "
                f"Referenced by {len(child_credits)} student Credit/enrollment record(s)."
            )
        return True, "Safe to delete."


class ReferentialIntegrityError(Exception):
    """Custom exception raised when an operation breaches database foreign key constraints."""
    pass


# Global database manager instance
db = DatabaseManager()
