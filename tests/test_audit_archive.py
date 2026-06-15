import pytest
import os
import sys
import tempfile
import json
import shutil
import sqlite3
from datetime import datetime

TEST_DB_PATH = os.path.join(tempfile.gettempdir(), 'test_audit_archive.db')

def reset_storage_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def get_test_connection():
    if os.path.exists(TEST_DB_PATH):
        return sqlite3.connect(TEST_DB_PATH)
    return None

@pytest.fixture(autouse=True)
def setup_test_db():
    reset_storage_db()
    
    import purchase_reconciliation.storage as storage_module
    storage_module.DB_PATH = TEST_DB_PATH
    
    os.makedirs(os.path.dirname(TEST_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(TEST_DB_PATH)
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
    
    conn.commit()
    conn.close()
    
    yield
    
    reset_storage_db()

class TestSchemeImportConflict:
    def test_import_with_overwrite_conflict(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import (
            save_rule_scheme, get_rule_scheme, import_rule_schemes_atomic,
            save_scheme_import_record, get_all_scheme_import_records
        )
        
        scheme1 = RuleScheme(
            name='test_scheme_conflict',
            quantity_tolerance=1.0,
            amount_tolerance=100.0
        )
        save_rule_scheme(scheme1)
        
        schemes_data = [
            {
                'name': 'test_scheme_conflict',
                'quantity_tolerance': 5.0,
                'amount_tolerance': 500.0,
                'date_offset_days': 3
            }
        ]
        
        imported, skipped, overwritten, renamed, errors = import_rule_schemes_atomic(schemes_data, 'overwrite')
        
        assert errors == []
        assert overwritten == 1
        assert imported == 0
        assert skipped == 0
        assert renamed == 0
        
        updated_scheme = get_rule_scheme('test_scheme_conflict')
        assert updated_scheme.quantity_tolerance == 5.0
        assert updated_scheme.amount_tolerance == 500.0
        
        save_scheme_import_record(
            file_path='/tmp/test.json',
            conflict_action='overwrite',
            imported_count=imported,
            skipped_count=skipped,
            overwritten_count=overwritten,
            renamed_count=renamed,
            error_count=len(errors),
            schemes_snapshot=[],
            operator='test_user',
            operator_role='admin',
            status='success' if not errors else 'failed'
        )
        
        records = get_all_scheme_import_records()
        assert len(records) >= 1
        assert records[0]['status'] == 'success'
    
    def test_import_with_skip_conflict(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import (
            save_rule_scheme, import_rule_schemes_atomic, get_rule_scheme
        )
        
        scheme1 = RuleScheme(
            name='test_scheme_skip',
            quantity_tolerance=1.0,
            amount_tolerance=100.0
        )
        save_rule_scheme(scheme1)
        
        schemes_data = [
            {
                'name': 'test_scheme_skip',
                'quantity_tolerance': 5.0,
                'amount_tolerance': 500.0
            }
        ]
        
        imported, skipped, overwritten, renamed, errors = import_rule_schemes_atomic(schemes_data, 'skip')
        
        assert errors == []
        assert skipped == 1
        assert imported == 0
        assert overwritten == 0
        assert renamed == 0
        
        unchanged_scheme = get_rule_scheme('test_scheme_skip')
        assert unchanged_scheme.quantity_tolerance == 1.0
    
    def test_import_with_rename_conflict(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import (
            save_rule_scheme, import_rule_schemes_atomic, get_rule_scheme
        )
        
        scheme1 = RuleScheme(
            name='test_scheme_rename',
            quantity_tolerance=1.0,
            amount_tolerance=100.0
        )
        save_rule_scheme(scheme1)
        
        schemes_data = [
            {
                'name': 'test_scheme_rename',
                'quantity_tolerance': 5.0,
                'amount_tolerance': 500.0
            }
        ]
        
        imported, skipped, overwritten, renamed, errors = import_rule_schemes_atomic(schemes_data, 'rename')
        
        assert errors == []
        assert renamed == 1
        assert imported == 0
        assert skipped == 0
        assert overwritten == 0
        
        original_unchanged = get_rule_scheme('test_scheme_rename')
        assert original_unchanged.quantity_tolerance == 1.0
        
        renamed_scheme = get_rule_scheme('test_scheme_rename_imported_1')
        assert renamed_scheme is not None
        assert renamed_scheme.quantity_tolerance == 5.0

class TestFailedImportRollback:
    def test_import_rollback_on_error(self):
        from purchase_reconciliation.storage import (
            get_rule_scheme, import_rule_schemes_atomic, delete_rule_scheme
        )
        
        test_scheme_name = 'rollback_test_scheme'
        delete_rule_scheme(test_scheme_name)
        
        schemes_data = [
            {'name': test_scheme_name, 'quantity_tolerance': 1.0},
            {'invalid_field': 'missing_name'}
        ]
        
        imported, skipped, overwritten, renamed, errors = import_rule_schemes_atomic(schemes_data, 'skip')
        
        assert len(errors) > 0
        assert '格式错误' in errors[0] or 'missing_name' in errors[0] or 'name' in errors[0]
        
        delete_rule_scheme(test_scheme_name)

class TestCrossRestartQuery:
    def test_batch_audit_persistence(self):
        from purchase_reconciliation.models import Batch, BatchStatus
        from purchase_reconciliation.storage import (
            save_batch, get_batch_by_no, save_batch_audit_record, get_batch_audit_record
        )
        
        batch = Batch(
            batch_no='CROSS_RESTART_001',
            status=BatchStatus.OPEN,
            scheme_name='test_scheme',
            scheme_snapshot={'quantity_tolerance': 5.0, 'amount_tolerance': 100.0}
        )
        batch_id = save_batch(batch)
        
        save_batch_audit_record(
            batch_id=batch_id,
            batch_no='CROSS_RESTART_001',
            scheme_name='test_scheme',
            scheme_snapshot={'quantity_tolerance': 5.0, 'amount_tolerance': 100.0},
            tolerated_items=3,
            tolerated_rationale='数量容差±5.0, 金额容差±100.0',
            date_failed_items=1,
            date_failed_rationale='日期偏移7天',
            intercepted_items=10,
            operator='张三',
            operator_role='reviewer'
        )
        
        retrieved_audit = get_batch_audit_record(batch_id)
        assert retrieved_audit is not None
        assert retrieved_audit['tolerated_items'] == 3
        assert retrieved_audit['intercepted_items'] == 10
        assert retrieved_audit['operator'] == '张三'
    
    def test_appeal_audit_persistence(self):
        from purchase_reconciliation.storage import (
            save_appeal_audit_record, get_appeal_audit_records_by_batch
        )
        
        batch_id = 1
        batch_no = 'APPEAL_PERSIST_001'
        
        save_appeal_audit_record(
            batch_id=batch_id,
            batch_no=batch_no,
            item_id=1,
            item_code='ITEM001',
            item_name='测试物料',
            quantity_diff=5.0,
            amount_diff=100.0,
            original_status='pending',
            action='APPROVE',
            decision_rationale='证据充分，同意申诉',
            rule_snapshot={'quantity_tolerance': 5.0},
            operator='李四',
            operator_role='approver'
        )
        
        audits = get_appeal_audit_records_by_batch(batch_id)
        assert len(audits) >= 1
        
        latest_audit = audits[0]
        assert latest_audit['item_code'] == 'ITEM001'
        assert latest_audit['action'] == 'APPROVE'
        assert latest_audit['operator'] == '李四'

class TestAuditReexport:
    def test_complete_audit_trail(self):
        from purchase_reconciliation.models import Batch, BatchStatus
        from purchase_reconciliation.storage import (
            save_batch, get_batch_by_no, save_batch_audit_record,
            save_appeal_audit_record, save_rollback_audit_record,
            save_export_audit_record, get_complete_audit_trail
        )
        
        batch = Batch(
            batch_no='TRAIL_TEST_001',
            status=BatchStatus.OPEN,
            scheme_name='trail_scheme',
            scheme_snapshot={'quantity_tolerance': 5.0}
        )
        batch_id = save_batch(batch)
        
        save_batch_audit_record(
            batch_id=batch_id,
            batch_no='TRAIL_TEST_001',
            scheme_name='trail_scheme',
            scheme_snapshot={'quantity_tolerance': 5.0},
            tolerated_items=2,
            tolerated_rationale='容差内',
            date_failed_items=0,
            date_failed_rationale='',
            intercepted_items=5,
            operator='张三',
            operator_role='reviewer'
        )
        
        save_appeal_audit_record(
            batch_id=batch_id,
            batch_no='TRAIL_TEST_001',
            item_id=1,
            item_code='ITEM001',
            item_name='测试物料',
            quantity_diff=5.0,
            amount_diff=100.0,
            original_status='pending',
            action='APPROVE',
            decision_rationale='同意',
            rule_snapshot={'quantity_tolerance': 5.0},
            operator='李四',
            operator_role='approver'
        )
        
        save_rollback_audit_record(
            batch_id=batch_id,
            batch_no='TRAIL_TEST_001',
            item_id=1,
            item_code='ITEM001',
            item_name='测试物料',
            rollback_reason='发现错误',
            previous_status='approved',
            rule_snapshot={'quantity_tolerance': 5.0},
            appeal_audit_id=1,
            operator='王五',
            operator_role='admin'
        )
        
        save_export_audit_record(
            export_type='RESULT_EXPORT',
            batch_no='TRAIL_TEST_001',
            export_file='/tmp/export.csv',
            record_count=5,
            export_format='csv',
            rule_snapshot={'quantity_tolerance': 5.0},
            note='结果导出'
        )
        
        trail = get_complete_audit_trail('TRAIL_TEST_001')
        
        assert trail is not None
        assert trail['batch']['batch_no'] == 'TRAIL_TEST_001'
        assert trail['batch_audit'] is not None
        assert len(trail['appeal_audits']) >= 1
        assert len(trail['rollback_audits']) >= 1
        assert len(trail['export_audits']) >= 1

class TestBOMJSONImport:
    def test_utf8_bom_json_parsing(self):
        from purchase_reconciliation.commands.scheme_cmd import read_json_file_with_bom
        import tempfile
        
        temp_dir = tempfile.gettempdir()
        bom_file = os.path.join(temp_dir, 'test_bom.json')
        
        with open(bom_file, 'wb') as f:
            f.write(b'\xef\xbb\xbf')
            f.write('{"schemes": [{"name": "bom_scheme", "quantity_tolerance": 1.0}]}'.encode('utf-8'))
        
        data = read_json_file_with_bom(bom_file)
        assert 'schemes' in data
        assert len(data['schemes']) == 1
        assert data['schemes'][0]['name'] == 'bom_scheme'
        
        os.remove(bom_file)
    
    def test_regular_json_parsing(self):
        from purchase_reconciliation.commands.scheme_cmd import read_json_file_with_bom
        import tempfile
        
        temp_dir = tempfile.gettempdir()
        regular_file = os.path.join(temp_dir, 'test_regular.json')
        
        with open(regular_file, 'w', encoding='utf-8') as f:
            json.dump({'schemes': [{'name': 'regular_scheme', 'quantity_tolerance': 2.0}]}, f)
        
        data = read_json_file_with_bom(regular_file)
        assert 'schemes' in data
        assert len(data['schemes']) == 1
        assert data['schemes'][0]['name'] == 'regular_scheme'
        
        os.remove(regular_file)

class TestExportReimport:
    def test_exported_scheme_can_be_reimported(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import (
            save_rule_scheme, export_all_rule_schemes, import_rule_schemes_atomic,
            delete_rule_scheme
        )
        import tempfile
        
        scheme = RuleScheme(
            name='reimport_test',
            business_line='华东区',
            description='测试导出后重新导入',
            quantity_tolerance=3.0,
            amount_tolerance=150.0,
            date_offset_days=5,
            required_fields=['bill_no'],
            ignored_fields=['unit_price']
        )
        save_rule_scheme(scheme)
        
        exported = export_all_rule_schemes()
        assert len(exported) >= 1
        
        scheme_data = next((s for s in exported if s['name'] == 'reimport_test'), None)
        assert scheme_data is not None
        assert scheme_data['quantity_tolerance'] == 3.0
        assert scheme_data['business_line'] == '华东区'
        
        delete_rule_scheme('reimport_test')
        
        imported, skipped, overwritten, renamed, errors = import_rule_schemes_atomic([scheme_data], 'skip')
        
        assert errors == []
        assert imported == 1
        
        reimported = export_all_rule_schemes()
        reimported_scheme = next((s for s in reimported if s['name'] == 'reimport_test'), None)
        assert reimported_scheme is not None
        assert reimported_scheme['quantity_tolerance'] == 3.0
        
        delete_rule_scheme('reimport_test')

class TestAuditArchiveQueries:
    def test_query_import_records(self):
        from purchase_reconciliation.storage import (
            save_scheme_import_record, get_all_scheme_import_records
        )
        
        save_scheme_import_record(
            file_path='/tmp/test1.json',
            conflict_action='skip',
            imported_count=2,
            skipped_count=1,
            overwritten_count=0,
            renamed_count=0,
            error_count=0,
            schemes_snapshot=[],
            operator='user1',
            operator_role='admin',
            status='success'
        )
        
        save_scheme_import_record(
            file_path='/tmp/test2.json',
            conflict_action='overwrite',
            imported_count=0,
            skipped_count=0,
            overwritten_count=1,
            renamed_count=0,
            error_count=0,
            schemes_snapshot=[],
            operator='user2',
            operator_role='admin',
            status='success'
        )
        
        records = get_all_scheme_import_records()
        assert len(records) >= 2
        
        skip_record = next((r for r in records if r['conflict_action'] == 'skip'), None)
        assert skip_record is not None
        assert skip_record['imported_count'] == 2
    
    def test_query_export_records(self):
        from purchase_reconciliation.storage import (
            save_export_audit_record, get_all_export_audit_records
        )
        
        save_export_audit_record(
            export_type='RESULT_EXPORT',
            batch_no='BATCH001',
            export_file='/tmp/result.csv',
            record_count=10,
            export_format='csv',
            operator='user1',
            rule_snapshot={'quantity_tolerance': 5.0}
        )
        
        records = get_all_export_audit_records()
        assert len(records) >= 1
        
        result_export = next((r for r in records if r['export_type'] == 'RESULT_EXPORT'), None)
        assert result_export is not None
        assert result_export['record_count'] == 10
