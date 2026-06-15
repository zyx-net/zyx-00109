import sqlite3
import os
import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheme_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_batch_no TEXT NOT NULL,
            file_path TEXT NOT NULL,
            conflict_action TEXT NOT NULL,
            imported_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            overwritten_count INTEGER DEFAULT 0,
            renamed_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            schemes_snapshot TEXT DEFAULT '[]',
            operator TEXT DEFAULT '',
            operator_role TEXT DEFAULT '',
            status TEXT DEFAULT 'success',
            error_message TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheme_import_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            final_name TEXT NOT NULL,
            action TEXT NOT NULL,
            scheme_snapshot TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (import_id) REFERENCES scheme_imports(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batch_audit_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            batch_no TEXT NOT NULL,
            scheme_name TEXT,
            scheme_snapshot TEXT NOT NULL,
            tolerated_items INTEGER DEFAULT 0,
            tolerated_rationale TEXT DEFAULT '',
            date_failed_items INTEGER DEFAULT 0,
            date_failed_rationale TEXT DEFAULT '',
            intercepted_items INTEGER DEFAULT 0,
            operator TEXT NOT NULL,
            operator_role TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (batch_id) REFERENCES batches(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appeal_audit_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            batch_no TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            item_code TEXT NOT NULL,
            item_name TEXT NOT NULL,
            quantity_diff REAL NOT NULL,
            amount_diff REAL NOT NULL,
            original_status TEXT NOT NULL,
            action TEXT NOT NULL,
            decision_rationale TEXT DEFAULT '',
            rule_snapshot TEXT,
            operator TEXT NOT NULL,
            operator_role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (batch_id) REFERENCES batches(id),
            FOREIGN KEY (item_id) REFERENCES diff_items(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rollback_audit_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            batch_no TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            item_code TEXT NOT NULL,
            item_name TEXT NOT NULL,
            rollback_reason TEXT DEFAULT '',
            previous_status TEXT NOT NULL,
            rule_snapshot TEXT,
            appeal_audit_id INTEGER,
            operator TEXT NOT NULL,
            operator_role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (batch_id) REFERENCES batches(id),
            FOREIGN KEY (item_id) REFERENCES diff_items(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS export_audit_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_type TEXT NOT NULL,
            batch_no TEXT,
            export_file TEXT NOT NULL,
            record_count INTEGER DEFAULT 0,
            export_format TEXT DEFAULT 'csv',
            operator TEXT DEFAULT '',
            operator_role TEXT DEFAULT '',
            rule_snapshot TEXT,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
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

def _save_rule_scheme_with_conn(scheme: RuleScheme, conn, cursor) -> int:
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
    
    return scheme.id

def import_rule_schemes_atomic(schemes_data: List[Dict[str, Any]], 
                               conflict_action: str = 'skip',
                               file_path: str = '',
                               operator: str = '',
                               operator_role: str = '') -> tuple:
    conn = get_connection()
    cursor = conn.cursor()
    imported = 0
    skipped = 0
    overwritten = 0
    renamed = 0
    errors = []
    final_results = []
    import_batch_no = generate_import_batch_no()
    now = datetime.now().isoformat()
    
    try:
        cursor.execute('BEGIN TRANSACTION')
        
        for data in schemes_data:
            try:
                scheme = RuleScheme.from_dict(data)
                original_name = scheme.name
                
                cursor.execute('SELECT id, is_active FROM rule_schemes WHERE name = ?', (scheme.name,))
                row = cursor.fetchone()
                existing = row is not None
                
                action = 'new'
                final_name = scheme.name
                
                if existing:
                    existing_id, existing_active = row
                    if conflict_action == 'overwrite':
                        scheme.id = existing_id
                        scheme.is_active = bool(existing_active)
                        _save_rule_scheme_with_conn(scheme, conn, cursor)
                        overwritten += 1
                        action = 'overwrite'
                    elif conflict_action == 'rename':
                        base_name = scheme.name
                        counter = 1
                        while True:
                            new_name = f"{base_name}_imported_{counter}"
                            cursor.execute('SELECT id FROM rule_schemes WHERE name = ?', (new_name,))
                            if cursor.fetchone() is None:
                                scheme.name = new_name
                                break
                            counter += 1
                        scheme.is_active = False
                        _save_rule_scheme_with_conn(scheme, conn, cursor)
                        renamed += 1
                        action = 'rename'
                        final_name = scheme.name
                    else:
                        skipped += 1
                        action = 'skip'
                else:
                    scheme.is_active = False
                    _save_rule_scheme_with_conn(scheme, conn, cursor)
                    imported += 1
                    action = 'new'
                
                final_results.append({
                    'original_name': original_name,
                    'final_name': final_name,
                    'action': action,
                    'name': final_name,
                    'business_line': scheme.business_line,
                    'description': scheme.description,
                    'quantity_tolerance': scheme.quantity_tolerance,
                    'amount_tolerance': scheme.amount_tolerance,
                    'date_offset_days': scheme.date_offset_days,
                    'required_fields': scheme.required_fields,
                    'ignored_fields': scheme.ignored_fields
                })
            except Exception as e:
                errors.append(f"处理方案 '{data.get('name', '未知')}' 时出错: {str(e)}")
        
        if errors:
            cursor.execute('ROLLBACK')
            conn.close()
            return imported, skipped, overwritten, renamed, errors, final_results, import_batch_no
        
        cursor.execute('''
            INSERT INTO scheme_imports (
                import_batch_no, file_path, conflict_action,
                imported_count, skipped_count, overwritten_count, renamed_count, error_count,
                schemes_snapshot, operator, operator_role, status, error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            import_batch_no, file_path, conflict_action,
            imported, skipped, overwritten, renamed, len(errors),
            json.dumps(final_results, ensure_ascii=False),
            operator, operator_role, 'success', '', now
        ))
        import_id = cursor.lastrowid
        
        for scheme_data in final_results:
            cursor.execute('''
                INSERT INTO scheme_import_details (
                    import_id, original_name, final_name, action, scheme_snapshot, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                import_id,
                scheme_data.get('original_name', scheme_data.get('name', '')),
                scheme_data.get('final_name', scheme_data.get('name', '')),
                scheme_data.get('action', 'new'),
                json.dumps(scheme_data, ensure_ascii=False),
                now
            ))
        
        cursor.execute('COMMIT')
        conn.close()
        return imported, skipped, overwritten, renamed, errors, final_results, import_batch_no
        
    except Exception as e:
        cursor.execute('ROLLBACK')
        conn.close()
        errors.append(f"事务执行失败: {str(e)}")
        return imported, skipped, overwritten, renamed, errors, final_results, import_batch_no

def import_rule_schemes(schemes_data: List[Dict[str, Any]], 
                        conflict_action: str = 'skip') -> tuple:
    conn = get_connection()
    cursor = conn.cursor()
    imported = 0
    skipped = 0
    overwritten = 0
    renamed = 0
    
    try:
        cursor.execute('BEGIN TRANSACTION')
        
        for data in schemes_data:
            scheme = RuleScheme.from_dict(data)
            
            cursor.execute('SELECT id, is_active FROM rule_schemes WHERE name = ?', (scheme.name,))
            row = cursor.fetchone()
            existing = row is not None
            
            if existing:
                existing_id, existing_active = row
                if conflict_action == 'overwrite':
                    scheme.id = existing_id
                    scheme.is_active = bool(existing_active)
                    _save_rule_scheme_with_conn(scheme, conn, cursor)
                    overwritten += 1
                elif conflict_action == 'rename':
                    base_name = scheme.name
                    counter = 1
                    while True:
                        new_name = f"{base_name}_imported_{counter}"
                        cursor.execute('SELECT id FROM rule_schemes WHERE name = ?', (new_name,))
                        if cursor.fetchone() is None:
                            scheme.name = new_name
                            break
                        counter += 1
                    scheme.is_active = False
                    _save_rule_scheme_with_conn(scheme, conn, cursor)
                    renamed += 1
                else:
                    skipped += 1
            else:
                scheme.is_active = False
                _save_rule_scheme_with_conn(scheme, conn, cursor)
                imported += 1
        
        cursor.execute('COMMIT')
    except Exception as e:
        cursor.execute('ROLLBACK')
        raise
    finally:
        conn.close()
    
    return imported, skipped, overwritten, renamed

def generate_import_batch_no() -> str:
    now = datetime.now()
    return f"IMPORT_{now.strftime('%Y%m%d_%H%M%S')}"

def save_scheme_import_record(
    file_path: str,
    conflict_action: str,
    imported_count: int,
    skipped_count: int,
    overwritten_count: int,
    renamed_count: int,
    error_count: int,
    schemes_snapshot: List[Dict[str, Any]],
    operator: str = '',
    operator_role: str = '',
    status: str = 'success',
    error_message: str = ''
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    import_batch_no = generate_import_batch_no()
    
    cursor.execute('''
        INSERT INTO scheme_imports (
            import_batch_no, file_path, conflict_action,
            imported_count, skipped_count, overwritten_count, renamed_count, error_count,
            schemes_snapshot, operator, operator_role, status, error_message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        import_batch_no, file_path, conflict_action,
        imported_count, skipped_count, overwritten_count, renamed_count, error_count,
        json.dumps(schemes_snapshot, ensure_ascii=False),
        operator, operator_role, status, error_message, now
    ))
    
    import_id = cursor.lastrowid
    
    for scheme_data in schemes_snapshot:
        cursor.execute('''
            INSERT INTO scheme_import_details (
                import_id, original_name, final_name, action, scheme_snapshot, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            import_id,
            scheme_data.get('original_name', scheme_data.get('name', '')),
            scheme_data.get('final_name', scheme_data.get('name', '')),
            scheme_data.get('action', 'new'),
            json.dumps(scheme_data, ensure_ascii=False),
            now
        ))
    
    conn.commit()
    conn.close()
    return import_id

def get_scheme_import_record(import_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, import_batch_no, file_path, conflict_action,
               imported_count, skipped_count, overwritten_count, renamed_count, error_count,
               schemes_snapshot, operator, operator_role, status, error_message, created_at
        FROM scheme_imports WHERE id = ?
    ''', (import_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'import_batch_no': row[1],
            'file_path': row[2],
            'conflict_action': row[3],
            'imported_count': row[4],
            'skipped_count': row[5],
            'overwritten_count': row[6],
            'renamed_count': row[7],
            'error_count': row[8],
            'schemes_snapshot': json.loads(row[9]) if row[9] else [],
            'operator': row[10],
            'operator_role': row[11],
            'status': row[12],
            'error_message': row[13],
            'created_at': datetime.fromisoformat(row[14]) if row[14] else None
        }
    return None

def get_all_scheme_import_records() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, import_batch_no, file_path, conflict_action,
               imported_count, skipped_count, overwritten_count, renamed_count, error_count,
               schemes_snapshot, operator, operator_role, status, error_message, created_at
        FROM scheme_imports ORDER BY created_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'id': row[0],
        'import_batch_no': row[1],
        'file_path': row[2],
        'conflict_action': row[3],
        'imported_count': row[4],
        'skipped_count': row[5],
        'overwritten_count': row[6],
        'renamed_count': row[7],
        'error_count': row[8],
        'schemes_snapshot': json.loads(row[9]) if row[9] else [],
        'operator': row[10],
        'operator_role': row[11],
        'status': row[12],
        'error_message': row[13],
        'created_at': datetime.fromisoformat(row[14]) if row[14] else None
    } for row in rows]

def get_scheme_import_details(import_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, import_id, original_name, final_name, action, scheme_snapshot, created_at
        FROM scheme_import_details WHERE import_id = ?
    ''', (import_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'id': row[0],
        'import_id': row[1],
        'original_name': row[2],
        'final_name': row[3],
        'action': row[4],
        'scheme_snapshot': json.loads(row[5]) if row[5] else {},
        'created_at': datetime.fromisoformat(row[6]) if row[6] else None
    } for row in rows]

def save_batch_audit_record(
    batch_id: int,
    batch_no: str,
    scheme_name: Optional[str],
    scheme_snapshot: Dict[str, Any],
    tolerated_items: int,
    tolerated_rationale: str,
    date_failed_items: int,
    date_failed_rationale: str,
    intercepted_items: int,
    operator: str,
    operator_role: str = ''
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT INTO batch_audit_records (
            batch_id, batch_no, scheme_name, scheme_snapshot,
            tolerated_items, tolerated_rationale,
            date_failed_items, date_failed_rationale,
            intercepted_items, operator, operator_role, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        batch_id, batch_no, scheme_name,
        json.dumps(scheme_snapshot, ensure_ascii=False),
        tolerated_items, tolerated_rationale,
        date_failed_items, date_failed_rationale,
        intercepted_items, operator, operator_role, now
    ))
    
    audit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return audit_id

def get_batch_audit_record(batch_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_id, batch_no, scheme_name, scheme_snapshot,
               tolerated_items, tolerated_rationale,
               date_failed_items, date_failed_rationale,
               intercepted_items, operator, operator_role, created_at
        FROM batch_audit_records WHERE batch_id = ?
    ''', (batch_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'batch_id': row[1],
            'batch_no': row[2],
            'scheme_name': row[3],
            'scheme_snapshot': json.loads(row[4]) if row[4] else {},
            'tolerated_items': row[5],
            'tolerated_rationale': row[6],
            'date_failed_items': row[7],
            'date_failed_rationale': row[8],
            'intercepted_items': row[9],
            'operator': row[10],
            'operator_role': row[11],
            'created_at': datetime.fromisoformat(row[12]) if row[12] else None
        }
    return None

def get_all_batch_audit_records() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_id, batch_no, scheme_name, scheme_snapshot,
               tolerated_items, tolerated_rationale,
               date_failed_items, date_failed_rationale,
               intercepted_items, operator, operator_role, created_at
        FROM batch_audit_records ORDER BY created_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'id': row[0],
        'batch_id': row[1],
        'batch_no': row[2],
        'scheme_name': row[3],
        'scheme_snapshot': json.loads(row[4]) if row[4] else {},
        'tolerated_items': row[5],
        'tolerated_rationale': row[6],
        'date_failed_items': row[7],
        'date_failed_rationale': row[8],
        'intercepted_items': row[9],
        'operator': row[10],
        'operator_role': row[11],
        'created_at': datetime.fromisoformat(row[12]) if row[12] else None
    } for row in rows]

def save_appeal_audit_record(
    batch_id: int,
    batch_no: str,
    item_id: int,
    item_code: str,
    item_name: str,
    quantity_diff: float,
    amount_diff: float,
    original_status: str,
    action: str,
    decision_rationale: str,
    rule_snapshot: Optional[Dict[str, Any]],
    operator: str,
    operator_role: str
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT INTO appeal_audit_records (
            batch_id, batch_no, item_id, item_code, item_name,
            quantity_diff, amount_diff, original_status, action,
            decision_rationale, rule_snapshot, operator, operator_role, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        batch_id, batch_no, item_id, item_code, item_name,
        quantity_diff, amount_diff, original_status, action,
        decision_rationale,
        json.dumps(rule_snapshot, ensure_ascii=False) if rule_snapshot else None,
        operator, operator_role, now
    ))
    
    audit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return audit_id

def get_appeal_audit_records_by_batch(batch_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_id, batch_no, item_id, item_code, item_name,
               quantity_diff, amount_diff, original_status, action,
               decision_rationale, rule_snapshot, operator, operator_role, created_at
        FROM appeal_audit_records WHERE batch_id = ? ORDER BY created_at DESC
    ''', (batch_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'id': row[0],
        'batch_id': row[1],
        'batch_no': row[2],
        'item_id': row[3],
        'item_code': row[4],
        'item_name': row[5],
        'quantity_diff': row[6],
        'amount_diff': row[7],
        'original_status': row[8],
        'action': row[9],
        'decision_rationale': row[10],
        'rule_snapshot': json.loads(row[11]) if row[11] else None,
        'operator': row[12],
        'operator_role': row[13],
        'created_at': datetime.fromisoformat(row[14]) if row[14] else None
    } for row in rows]

def get_all_appeal_audit_records() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_id, batch_no, item_id, item_code, item_name,
               quantity_diff, amount_diff, original_status, action,
               decision_rationale, rule_snapshot, operator, operator_role, created_at
        FROM appeal_audit_records ORDER BY created_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'id': row[0],
        'batch_id': row[1],
        'batch_no': row[2],
        'item_id': row[3],
        'item_code': row[4],
        'item_name': row[5],
        'quantity_diff': row[6],
        'amount_diff': row[7],
        'original_status': row[8],
        'action': row[9],
        'decision_rationale': row[10],
        'rule_snapshot': json.loads(row[11]) if row[11] else None,
        'operator': row[12],
        'operator_role': row[13],
        'created_at': datetime.fromisoformat(row[14]) if row[14] else None
    } for row in rows]

def save_rollback_audit_record(
    batch_id: int,
    batch_no: str,
    item_id: int,
    item_code: str,
    item_name: str,
    rollback_reason: str,
    previous_status: str,
    rule_snapshot: Optional[Dict[str, Any]],
    appeal_audit_id: Optional[int],
    operator: str,
    operator_role: str
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT INTO rollback_audit_records (
            batch_id, batch_no, item_id, item_code, item_name,
            rollback_reason, previous_status, rule_snapshot,
            appeal_audit_id, operator, operator_role, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        batch_id, batch_no, item_id, item_code, item_name,
        rollback_reason, previous_status,
        json.dumps(rule_snapshot, ensure_ascii=False) if rule_snapshot else None,
        appeal_audit_id, operator, operator_role, now
    ))
    
    audit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return audit_id

def get_rollback_audit_records_by_batch(batch_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_id, batch_no, item_id, item_code, item_name,
               rollback_reason, previous_status, rule_snapshot,
               appeal_audit_id, operator, operator_role, created_at
        FROM rollback_audit_records WHERE batch_id = ? ORDER BY created_at DESC
    ''', (batch_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'id': row[0],
        'batch_id': row[1],
        'batch_no': row[2],
        'item_id': row[3],
        'item_code': row[4],
        'item_name': row[5],
        'rollback_reason': row[6],
        'previous_status': row[7],
        'rule_snapshot': json.loads(row[8]) if row[8] else None,
        'appeal_audit_id': row[9],
        'operator': row[10],
        'operator_role': row[11],
        'created_at': datetime.fromisoformat(row[12]) if row[12] else None
    } for row in rows]

def get_all_rollback_audit_records() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, batch_id, batch_no, item_id, item_code, item_name,
               rollback_reason, previous_status, rule_snapshot,
               appeal_audit_id, operator, operator_role, created_at
        FROM rollback_audit_records ORDER BY created_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'id': row[0],
        'batch_id': row[1],
        'batch_no': row[2],
        'item_id': row[3],
        'item_code': row[4],
        'item_name': row[5],
        'rollback_reason': row[6],
        'previous_status': row[7],
        'rule_snapshot': json.loads(row[8]) if row[8] else None,
        'appeal_audit_id': row[9],
        'operator': row[10],
        'operator_role': row[11],
        'created_at': datetime.fromisoformat(row[12]) if row[12] else None
    } for row in rows]

def save_export_audit_record(
    export_type: str,
    batch_no: Optional[str],
    export_file: str,
    record_count: int,
    export_format: str = 'csv',
    operator: str = '',
    operator_role: str = '',
    rule_snapshot: Optional[Dict[str, Any]] = None,
    note: str = ''
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT INTO export_audit_records (
            export_type, batch_no, export_file, record_count,
            export_format, operator, operator_role, rule_snapshot, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        export_type, batch_no, export_file, record_count,
        export_format, operator, operator_role,
        json.dumps(rule_snapshot, ensure_ascii=False) if rule_snapshot else None,
        note, now
    ))
    
    audit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return audit_id

def get_export_audit_records_by_batch(batch_no: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, export_type, batch_no, export_file, record_count,
               export_format, operator, operator_role, rule_snapshot, note, created_at
        FROM export_audit_records WHERE batch_no = ? ORDER BY created_at DESC
    ''', (batch_no,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'id': row[0],
        'export_type': row[1],
        'batch_no': row[2],
        'export_file': row[3],
        'record_count': row[4],
        'export_format': row[5],
        'operator': row[6],
        'operator_role': row[7],
        'rule_snapshot': json.loads(row[8]) if row[8] else None,
        'note': row[9],
        'created_at': datetime.fromisoformat(row[10]) if row[10] else None
    } for row in rows]

def get_all_export_audit_records() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, export_type, batch_no, export_file, record_count,
               export_format, operator, operator_role, rule_snapshot, note, created_at
        FROM export_audit_records ORDER BY created_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'id': row[0],
        'export_type': row[1],
        'batch_no': row[2],
        'export_file': row[3],
        'record_count': row[4],
        'export_format': row[5],
        'operator': row[6],
        'operator_role': row[7],
        'rule_snapshot': json.loads(row[8]) if row[8] else None,
        'note': row[9],
        'created_at': datetime.fromisoformat(row[10]) if row[10] else None
    } for row in rows]

def get_complete_audit_trail(batch_no: str) -> Dict[str, Any]:
    batch = get_batch_by_no(batch_no)
    if not batch:
        return {}
    
    batch_audit = get_batch_audit_record(batch.id)
    appeal_audits = get_appeal_audit_records_by_batch(batch.id)
    rollback_audits = get_rollback_audit_records_by_batch(batch.id)
    export_audits = get_export_audit_records_by_batch(batch_no)
    audit_logs = get_audit_logs(batch.id)
    
    return {
        'batch': {
            'batch_no': batch.batch_no,
            'status': batch.status.value,
            'scheme_name': batch.scheme_name,
            'scheme_snapshot': batch.scheme_snapshot,
            'created_at': batch.created_at.isoformat() if batch.created_at else None
        },
        'batch_audit': batch_audit,
        'appeal_audits': appeal_audits,
        'rollback_audits': rollback_audits,
        'export_audits': export_audits,
        'audit_logs': [
            {
                'id': log.id,
                'operation': log.operation,
                'operator': log.operator,
                'operator_role': log.operator_role,
                'target_item_id': log.target_item_id,
                'note': log.note,
                'created_at': log.created_at.isoformat() if log.created_at else None
            } for log in audit_logs
        ]
    }