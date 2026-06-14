import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from .models import (
    DiffItem, AppealStatus, Batch, BatchStatus, AuditLog, Config
)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "purchase_recon.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_no TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            locked_by TEXT,
            lock_time TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS diff_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            bill_no TEXT NOT NULL,
            receive_no TEXT NOT NULL,
            item_code TEXT NOT NULL,
            item_name TEXT NOT NULL,
            bill_quantity REAL NOT NULL,
            receive_quantity REAL NOT NULL,
            quantity_diff REAL NOT NULL,
            bill_amount REAL NOT NULL,
            receive_amount REAL NOT NULL,
            amount_diff REAL NOT NULL,
            supplier_code TEXT NOT NULL,
            supplier_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            appeal_note TEXT DEFAULT '',
            operator TEXT DEFAULT '',
            operator_role TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (batch_id) REFERENCES batches(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            batch_no TEXT NOT NULL,
            operation TEXT NOT NULL,
            operator TEXT NOT NULL,
            operator_role TEXT DEFAULT '',
            target_item_id INTEGER,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (batch_id) REFERENCES batches(id),
            FOREIGN KEY (target_item_id) REFERENCES diff_items(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            description TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute("PRAGMA table_info(diff_items)")
    diff_cols = [col[1] for col in cursor.fetchall()]
    if 'operator_role' not in diff_cols:
        cursor.execute("ALTER TABLE diff_items ADD COLUMN operator_role TEXT DEFAULT ''")
    
    cursor.execute("PRAGMA table_info(audit_logs)")
    audit_cols = [col[1] for col in cursor.fetchall()]
    if 'operator_role' not in audit_cols:
        cursor.execute("ALTER TABLE audit_logs ADD COLUMN operator_role TEXT DEFAULT ''")
    
    conn.commit()
    conn.close()

def get_connection():
    init_db()
    return sqlite3.connect(DB_PATH)

def save_batch(batch: Batch) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    if batch.id is None:
        cursor.execute('''
            INSERT INTO batches (batch_no, status, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (batch.batch_no, batch.status.value, now, now))
        batch.id = cursor.lastrowid
    else:
        cursor.execute('''
            UPDATE batches SET status=?, updated_at=?, locked_by=?, lock_time=?
            WHERE id=?
        ''', (batch.status.value, now, batch.locked_by, 
              batch.lock_time.isoformat() if batch.lock_time else None, batch.id))
    
    conn.commit()
    conn.close()
    return batch.id

def get_batch_by_no(batch_no: str) -> Optional[Batch]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_no, status, created_at, updated_at, locked_by, lock_time
        FROM batches WHERE batch_no = ?
    ''', (batch_no,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return Batch(
            batch_no=row[1],
            id=row[0],
            status=BatchStatus(row[2]),
            created_at=datetime.fromisoformat(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
            locked_by=row[5],
            lock_time=datetime.fromisoformat(row[6]) if row[6] else None
        )
    return None

def get_all_batches() -> List[Batch]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_no, status, created_at, updated_at, locked_by, lock_time
        FROM batches ORDER BY created_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        Batch(
            batch_no=row[1],
            id=row[0],
            status=BatchStatus(row[2]),
            created_at=datetime.fromisoformat(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
            locked_by=row[5],
            lock_time=datetime.fromisoformat(row[6]) if row[6] else None
        ) for row in rows
    ]

def save_diff_items(items: List[DiffItem], batch_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    for item in items:
        cursor.execute('''
            INSERT INTO diff_items (
                batch_id, bill_no, receive_no, item_code, item_name,
                bill_quantity, receive_quantity, quantity_diff,
                bill_amount, receive_amount, amount_diff,
                supplier_code, supplier_name, status, appeal_note, operator, operator_role,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            batch_id, item.bill_no, item.receive_no, item.item_code, item.item_name,
            item.bill_quantity, item.receive_quantity, item.quantity_diff,
            item.bill_amount, item.receive_amount, item.amount_diff,
            item.supplier_code, item.supplier_name, item.status.value,
            item.appeal_note, item.operator, item.operator_role, now, now
        ))
        item.id = cursor.lastrowid
    
    conn.commit()
    conn.close()

def get_diff_items_by_batch(batch_id: int) -> List[DiffItem]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_id, bill_no, receive_no, item_code, item_name,
               bill_quantity, receive_quantity, quantity_diff,
               bill_amount, receive_amount, amount_diff,
               supplier_code, supplier_name, status, appeal_note, operator, operator_role,
               created_at, updated_at
        FROM diff_items WHERE batch_id = ? ORDER BY item_code
    ''', (batch_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        DiffItem(
            bill_no=row[2],
            receive_no=row[3],
            item_code=row[4],
            item_name=row[5],
            bill_quantity=row[6],
            receive_quantity=row[7],
            quantity_diff=row[8],
            bill_amount=row[9],
            receive_amount=row[10],
            amount_diff=row[11],
            supplier_code=row[12],
            supplier_name=row[13],
            id=row[0],
            batch_id=row[1],
            status=AppealStatus(row[14]),
            appeal_note=row[15],
            operator=row[16],
            operator_role=row[17] if len(row) > 17 else "",
            created_at=datetime.fromisoformat(row[18]) if len(row) > 18 else None,
            updated_at=datetime.fromisoformat(row[19]) if len(row) > 19 else None
        ) for row in rows
    ]

def update_diff_item_status(item_id: int, status: AppealStatus, operator: str, 
                            operator_role: str = "", note: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute('''
        UPDATE diff_items SET status=?, operator=?, operator_role=?, appeal_note=?, updated_at=?
        WHERE id=?
    ''', (status.value, operator, operator_role, note, now, item_id))
    
    conn.commit()
    conn.close()

def get_diff_item(item_id: int) -> Optional[DiffItem]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_id, bill_no, receive_no, item_code, item_name,
               bill_quantity, receive_quantity, quantity_diff,
               bill_amount, receive_amount, amount_diff,
               supplier_code, supplier_name, status, appeal_note, operator, operator_role,
               created_at, updated_at
        FROM diff_items WHERE id = ?
    ''', (item_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return DiffItem(
            bill_no=row[2],
            receive_no=row[3],
            item_code=row[4],
            item_name=row[5],
            bill_quantity=row[6],
            receive_quantity=row[7],
            quantity_diff=row[8],
            bill_amount=row[9],
            receive_amount=row[10],
            amount_diff=row[11],
            supplier_code=row[12],
            supplier_name=row[13],
            id=row[0],
            batch_id=row[1],
            status=AppealStatus(row[14]),
            appeal_note=row[15],
            operator=row[16],
            operator_role=row[17] if len(row) > 17 else "",
            created_at=datetime.fromisoformat(row[18]) if len(row) > 18 else None,
            updated_at=datetime.fromisoformat(row[19]) if len(row) > 19 else None
        )
    return None

def add_audit_log(batch_id: int, batch_no: str, operation: str, 
                  operator: str, operator_role: str = "",
                  target_item_id: Optional[int] = None, note: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT INTO audit_logs (
            batch_id, batch_no, operation, operator, operator_role, target_item_id, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (batch_id, batch_no, operation, operator, operator_role, target_item_id, note, now))
    
    conn.commit()
    conn.close()

def get_audit_logs(batch_id: Optional[int] = None) -> List[AuditLog]:
    conn = get_connection()
    cursor = conn.cursor()
    
    if batch_id:
        cursor.execute('''
            SELECT id, batch_id, batch_no, operation, operator, operator_role, target_item_id, note, created_at
            FROM audit_logs WHERE batch_id = ? ORDER BY created_at DESC
        ''', (batch_id,))
    else:
        cursor.execute('''
            SELECT id, batch_id, batch_no, operation, operator, operator_role, target_item_id, note, created_at
            FROM audit_logs ORDER BY created_at DESC
        ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        AuditLog(
            batch_id=row[1],
            batch_no=row[2],
            operation=row[3],
            operator=row[4],
            id=row[0],
            operator_role=row[5] if len(row) > 5 else "",
            target_item_id=row[6] if len(row) > 6 else None,
            note=row[7] if len(row) > 7 else "",
            created_at=datetime.fromisoformat(row[8]) if len(row) > 8 else None
        ) for row in rows
    ]

def save_config(key: str, value: str, description: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT OR REPLACE INTO configs (key, value, description, updated_at)
        VALUES (?, ?, ?, ?)
    ''', (key, value, description, now))
    
    conn.commit()
    conn.close()

def get_config(key: str) -> Optional[str]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT value FROM configs WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    
    return row[0] if row else None

def get_all_configs() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT key, value, description FROM configs')
    rows = cursor.fetchall()
    conn.close()
    
    return {row[0]: {"value": row[1], "description": row[2]} for row in rows}

def is_batch_rollback_conflict(batch_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) FROM diff_items 
        WHERE batch_id = ? AND status = ?
    ''', (batch_id, AppealStatus.ROLLED_BACK.value))
    
    row = cursor.fetchone()
    conn.close()
    
    return row[0] > 0 if row else False

def has_pending_items(batch_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) FROM diff_items 
        WHERE batch_id = ? AND status = ?
    ''', (batch_id, AppealStatus.PENDING.value))
    
    row = cursor.fetchone()
    conn.close()
    
    return row[0] > 0 if row else False