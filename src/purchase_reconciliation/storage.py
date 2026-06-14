import sqlite3
import os
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from .models import (
    DiffItem, AppealStatus, Batch, BatchStatus, AuditLog, Config, RuleScheme
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
            lock_time TEXT,
            scheme_name TEXT,
            scheme_snapshot TEXT
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rule_schemes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            business_line TEXT DEFAULT '',
            description TEXT DEFAULT '',
            quantity_tolerance REAL DEFAULT 0.0,
            amount_tolerance REAL DEFAULT 0.0,
            date_offset_days INTEGER DEFAULT 0,
            required_fields TEXT DEFAULT '[]',
            ignored_fields TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
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
    
    cursor.execute("PRAGMA table_info(batches)")
    batch_cols = [col[1] for col in cursor.fetchall()]
    if 'scheme_name' not in batch_cols:
        cursor.execute("ALTER TABLE batches ADD COLUMN scheme_name TEXT DEFAULT ''")
    if 'scheme_snapshot' not in batch_cols:
        cursor.execute("ALTER TABLE batches ADD COLUMN scheme_snapshot TEXT DEFAULT ''")
    
    conn.commit()
    conn.close()

def get_connection():
    init_db()
    return sqlite3.connect(DB_PATH)

def save_batch(batch: Batch) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    scheme_snapshot_json = json.dumps(batch.scheme_snapshot) if batch.scheme_snapshot else ''
    
    if batch.id is None:
        cursor.execute('''
            INSERT INTO batches (batch_no, status, created_at, updated_at, locked_by, lock_time, scheme_name, scheme_snapshot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (batch.batch_no, batch.status.value, now, now, batch.locked_by, 
              batch.lock_time.isoformat() if batch.lock_time else None,
              batch.scheme_name, scheme_snapshot_json))
        batch.id = cursor.lastrowid
    else:
        cursor.execute('''
            UPDATE batches SET status=?, updated_at=?, locked_by=?, lock_time=?, scheme_name=?, scheme_snapshot=?
            WHERE id=?
        ''', (batch.status.value, now, batch.locked_by, 
              batch.lock_time.isoformat() if batch.lock_time else None,
              batch.scheme_name, scheme_snapshot_json, batch.id))
    
    conn.commit()
    conn.close()
    return batch.id

def get_batch_by_no(batch_no: str) -> Optional[Batch]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_no, status, created_at, updated_at, locked_by, lock_time, scheme_name, scheme_snapshot
        FROM batches WHERE batch_no = ?
    ''', (batch_no,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        scheme_snapshot = None
        if len(row) > 8 and row[8]:
            try:
                scheme_snapshot = json.loads(row[8])
            except:
                pass
        return Batch(
            batch_no=row[1],
            id=row[0],
            status=BatchStatus(row[2]),
            created_at=datetime.fromisoformat(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
            locked_by=row[5],
            lock_time=datetime.fromisoformat(row[6]) if row[6] else None,
            scheme_name=row[7] if len(row) > 7 else None,
            scheme_snapshot=scheme_snapshot
        )
    return None

def get_all_batches() -> List[Batch]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_no, status, created_at, updated_at, locked_by, lock_time, scheme_name, scheme_snapshot
        FROM batches ORDER BY created_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        scheme_snapshot = None
        if len(row) > 8 and row[8]:
            try:
                scheme_snapshot = json.loads(row[8])
            except:
                pass
        result.append(Batch(
            batch_no=row[1],
            id=row[0],
            status=BatchStatus(row[2]),
            created_at=datetime.fromisoformat(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
            locked_by=row[5],
            lock_time=datetime.fromisoformat(row[6]) if row[6] else None,
            scheme_name=row[7] if len(row) > 7 else None,
            scheme_snapshot=scheme_snapshot
        ))
    return result

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

def save_rule_scheme(scheme: RuleScheme) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    if scheme.id is None:
        cursor.execute('''
            INSERT INTO rule_schemes (
                name, business_line, description, quantity_tolerance, amount_tolerance,
                date_offset_days, required_fields, ignored_fields, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            scheme.name, scheme.business_line, scheme.description,
            scheme.quantity_tolerance, scheme.amount_tolerance,
            scheme.date_offset_days,
            json.dumps(scheme.required_fields),
            json.dumps(scheme.ignored_fields),
            1 if scheme.is_active else 0,
            now, now
        ))
        scheme.id = cursor.lastrowid
    else:
        cursor.execute('''
            UPDATE rule_schemes SET 
                name=?, business_line=?, description=?,
                quantity_tolerance=?, amount_tolerance=?, date_offset_days=?,
                required_fields=?, ignored_fields=?, is_active=?, updated_at=?
            WHERE id=?
        ''', (
            scheme.name, scheme.business_line, scheme.description,
            scheme.quantity_tolerance, scheme.amount_tolerance, scheme.date_offset_days,
            json.dumps(scheme.required_fields), json.dumps(scheme.ignored_fields),
            1 if scheme.is_active else 0, now, scheme.id
        ))
    
    conn.commit()
    conn.close()
    return scheme.id

def get_rule_scheme(name: str) -> Optional[RuleScheme]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, business_line, description, quantity_tolerance, amount_tolerance,
               date_offset_days, required_fields, ignored_fields, is_active, created_at, updated_at
        FROM rule_schemes WHERE name = ?
    ''', (name,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return RuleScheme(
            id=row[0],
            name=row[1],
            business_line=row[2] or '',
            description=row[3] or '',
            quantity_tolerance=row[4],
            amount_tolerance=row[5],
            date_offset_days=row[6],
            required_fields=json.loads(row[7]) if row[7] else [],
            ignored_fields=json.loads(row[8]) if row[8] else [],
            is_active=bool(row[9]),
            created_at=datetime.fromisoformat(row[10]) if row[10] else None,
            updated_at=datetime.fromisoformat(row[11]) if row[11] else None
        )
    return None

def get_rule_scheme_by_id(scheme_id: int) -> Optional[RuleScheme]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, business_line, description, quantity_tolerance, amount_tolerance,
               date_offset_days, required_fields, ignored_fields, is_active, created_at, updated_at
        FROM rule_schemes WHERE id = ?
    ''', (scheme_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return RuleScheme(
            id=row[0],
            name=row[1],
            business_line=row[2] or '',
            description=row[3] or '',
            quantity_tolerance=row[4],
            amount_tolerance=row[5],
            date_offset_days=row[6],
            required_fields=json.loads(row[7]) if row[7] else [],
            ignored_fields=json.loads(row[8]) if row[8] else [],
            is_active=bool(row[9]),
            created_at=datetime.fromisoformat(row[10]) if row[10] else None,
            updated_at=datetime.fromisoformat(row[11]) if row[11] else None
        )
    return None

def get_all_rule_schemes() -> List[RuleScheme]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, business_line, description, quantity_tolerance, amount_tolerance,
               date_offset_days, required_fields, ignored_fields, is_active, created_at, updated_at
        FROM rule_schemes ORDER BY name
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        RuleScheme(
            id=row[0],
            name=row[1],
            business_line=row[2] or '',
            description=row[3] or '',
            quantity_tolerance=row[4],
            amount_tolerance=row[5],
            date_offset_days=row[6],
            required_fields=json.loads(row[7]) if row[7] else [],
            ignored_fields=json.loads(row[8]) if row[8] else [],
            is_active=bool(row[9]),
            created_at=datetime.fromisoformat(row[10]) if row[10] else None,
            updated_at=datetime.fromisoformat(row[11]) if row[11] else None
        ) for row in rows
    ]

def get_active_rule_scheme() -> Optional[RuleScheme]:
    schemes = get_all_rule_schemes()
    for scheme in schemes:
        if scheme.is_active:
            return scheme
    return None

def set_active_rule_scheme(name: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute('SELECT id FROM rule_schemes WHERE name = ?', (name,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    
    cursor.execute('UPDATE rule_schemes SET is_active = 0, updated_at = ?', (now,))
    cursor.execute('UPDATE rule_schemes SET is_active = 1, updated_at = ? WHERE name = ?', (now, name))
    
    conn.commit()
    conn.close()
    return True

def delete_rule_scheme(name: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM rule_schemes WHERE name = ?', (name,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    return deleted

def export_all_rule_schemes() -> List[Dict[str, Any]]:
    schemes = get_all_rule_schemes()
    return [scheme.to_dict() for scheme in schemes]

def import_rule_schemes(schemes_data: List[Dict[str, Any]], 
                        conflict_action: str = 'skip') -> tuple:
    imported = 0
    skipped = 0
    overwritten = 0
    renamed = 0
    
    for data in schemes_data:
        scheme = RuleScheme.from_dict(data)
        existing = get_rule_scheme(scheme.name)
        
        if existing:
            if conflict_action == 'overwrite':
                scheme.id = existing.id
                scheme.is_active = existing.is_active
                save_rule_scheme(scheme)
                overwritten += 1
            elif conflict_action == 'rename':
                base_name = scheme.name
                counter = 1
                while get_rule_scheme(scheme.name):
                    scheme.name = f"{base_name}_imported_{counter}"
                    counter += 1
                scheme.is_active = False
                save_rule_scheme(scheme)
                renamed += 1
            else:
                skipped += 1
        else:
            scheme.is_active = False
            save_rule_scheme(scheme)
            imported += 1
    
    return imported, skipped, overwritten, renamed