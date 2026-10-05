"""
Database layer for the Finance System (SQLite).
Manages SQLite connection, table creation, record insertion, querying, and database reset.
"""

import sqlite3
import os
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance.db")

def get_connection():
    """Get a SQLite database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database table and sequence start if not existing."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                vendor TEXT NOT NULL,
                amount REAL NOT NULL,
                due_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Ensure sequence entry exists starting sequence at 1000
        cursor.execute("SELECT COUNT(*) FROM invoices")
        if cursor.fetchone()[0] == 0:
            try:
                cursor.execute("INSERT OR IGNORE INTO sqlite_sequence (name, seq) VALUES ('invoices', 1000)")
            except sqlite3.OperationalError:
                pass
        conn.commit()

# Ensure table is initialized on module load
init_db()

def insert_invoice(invoice_number: str, vendor: str, amount: float, due_date: str) -> str:
    """
    Insert a new invoice record into SQLite.
    Returns formatted Record ID (e.g. 'FIN-1001').
    Raises sqlite3.IntegrityError if invoice_number already exists.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO invoices (invoice_number, vendor, amount, due_date) VALUES (?, ?, ?, ?)",
            (invoice_number.strip(), vendor.strip(), amount, due_date.strip())
        )
        conn.commit()
        row_id = cursor.lastrowid
        return f"FIN-{row_id}"

def get_all_records() -> List[Dict]:
    """Retrieve all recorded invoices sorted by ID descending."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, invoice_number, vendor, amount, due_date, created_at FROM invoices ORDER BY id DESC")
        rows = cursor.fetchall()
        return [
            {
                "record_id": f"FIN-{row['id']}",
                "invoice_number": row["invoice_number"],
                "vendor": row["vendor"],
                "amount": row["amount"],
                "due_date": row["due_date"],
                "created_at": str(row["created_at"])
            }
            for row in rows
        ]

def get_record_by_invoice_number(invoice_number: str) -> Optional[Dict]:
    """Fetch record by exact invoice number for API verifier."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, invoice_number, vendor, amount, due_date, created_at FROM invoices WHERE UPPER(invoice_number) = UPPER(?)",
            (invoice_number.strip(),)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "record_id": f"FIN-{row['id']}",
            "invoice_number": row["invoice_number"],
            "vendor": row["vendor"],
            "amount": row["amount"],
            "due_date": row["due_date"],
            "created_at": str(row["created_at"])
        }

def reset_db():
    """Wipe all invoice records and reset AUTOINCREMENT sequence to 1000."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM invoices")
        try:
            cursor.execute("UPDATE sqlite_sequence SET seq = 1000 WHERE name = 'invoices'")
        except sqlite3.OperationalError:
            pass
        conn.commit()
