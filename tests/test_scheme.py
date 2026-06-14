import pytest
import os
import sys
import tempfile
import json
import shutil
import sqlite3

TEST_DB_PATH = os.path.join(tempfile.gettempdir(), 'test_purchase_recon_scheme.db')

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
            scheme_name TEXT
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
    
    conn.commit()
    conn.close()
    
    yield
    
    reset_storage_db()

class TestRuleSchemePersistence:
    def test_create_and_retrieve_scheme(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, get_rule_scheme
        
        scheme = RuleScheme(
            name='test_scheme_1',
            business_line='华东区',
            description='测试方案',
            quantity_tolerance=1.5,
            amount_tolerance=100.0,
            date_offset_days=3,
            required_fields=['bill_no', 'item_code'],
            ignored_fields=['unit_price']
        )
        save_rule_scheme(scheme)
        
        retrieved = get_rule_scheme('test_scheme_1')
        assert retrieved is not None
        assert retrieved.name == 'test_scheme_1'
        assert retrieved.business_line == '华东区'
        assert retrieved.description == '测试方案'
        assert retrieved.quantity_tolerance == 1.5
        assert retrieved.amount_tolerance == 100.0
        assert retrieved.date_offset_days == 3
        assert retrieved.required_fields == ['bill_no', 'item_code']
        assert retrieved.ignored_fields == ['unit_price']
    
    def test_update_scheme(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, get_rule_scheme
        
        scheme = RuleScheme(
            name='test_scheme_update',
            quantity_tolerance=1.0,
            amount_tolerance=50.0
        )
        save_rule_scheme(scheme)
        
        scheme.quantity_tolerance = 2.0
        scheme.amount_tolerance = 75.0
        save_rule_scheme(scheme)
        
        retrieved = get_rule_scheme('test_scheme_update')
        assert retrieved.quantity_tolerance == 2.0
        assert retrieved.amount_tolerance == 75.0
    
    def test_get_all_schemes(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, get_all_rule_schemes
        
        scheme1 = RuleScheme(name='scheme_a', quantity_tolerance=1.0)
        scheme2 = RuleScheme(name='scheme_b', quantity_tolerance=2.0)
        save_rule_scheme(scheme1)
        save_rule_scheme(scheme2)
        
        all_schemes = get_all_rule_schemes()
        assert len(all_schemes) >= 2
        names = [s.name for s in all_schemes]
        assert 'scheme_a' in names
        assert 'scheme_b' in names
    
    def test_delete_scheme(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, get_rule_scheme, delete_rule_scheme
        
        scheme = RuleScheme(name='to_delete', quantity_tolerance=1.0)
        save_rule_scheme(scheme)
        
        assert get_rule_scheme('to_delete') is not None
        delete_rule_scheme('to_delete')
        assert get_rule_scheme('to_delete') is None
    
    def test_active_scheme(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, get_active_rule_scheme
        
        scheme1 = RuleScheme(name='inactive_scheme_test', is_active=False)
        scheme2 = RuleScheme(name='active_scheme_test', is_active=True)
        save_rule_scheme(scheme1)
        save_rule_scheme(scheme2)
        
        active = get_active_rule_scheme()
        assert active is not None
        assert active.name == 'active_scheme_test'
    
    def test_switch_active_scheme(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, set_active_rule_scheme, get_active_rule_scheme
        
        scheme1 = RuleScheme(name='scheme_1_test', is_active=True)
        scheme2 = RuleScheme(name='scheme_2_test', is_active=False)
        save_rule_scheme(scheme1)
        save_rule_scheme(scheme2)
        
        set_active_rule_scheme('scheme_2_test')
        
        active = get_active_rule_scheme()
        assert active.name == 'scheme_2_test'


class TestSchemeImportExport:
    def test_export_schemes(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, export_all_rule_schemes
        
        scheme1 = RuleScheme(
            name='export_test_1',
            business_line='华南区',
            quantity_tolerance=0.5,
            amount_tolerance=25.0,
            date_offset_days=1,
            required_fields=['item_code'],
            ignored_fields=['item_name']
        )
        scheme2 = RuleScheme(
            name='export_test_2',
            quantity_tolerance=1.0
        )
        save_rule_scheme(scheme1)
        save_rule_scheme(scheme2)
        
        exported = export_all_rule_schemes()
        assert len(exported) >= 2
        export_names = [e['name'] for e in exported]
        assert 'export_test_1' in export_names
        assert 'export_test_2' in export_names
    
    def test_import_schemes_skip(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, import_rule_schemes, get_rule_scheme
        
        existing = RuleScheme(name='conflict_scheme', quantity_tolerance=1.0)
        save_rule_scheme(existing)
        
        import_data = [
            {
                'name': 'conflict_scheme',
                'quantity_tolerance': 99.0
            },
            {
                'name': 'new_scheme',
                'quantity_tolerance': 2.0
            }
        ]
        
        imported, skipped, overwritten, renamed = import_rule_schemes(import_data, 'skip')
        
        assert imported == 1
        assert skipped == 1
        assert overwritten == 0
        assert renamed == 0
        
        scheme = get_rule_scheme('conflict_scheme')
        assert scheme.quantity_tolerance == 1.0
    
    def test_import_schemes_overwrite(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, import_rule_schemes, get_rule_scheme
        
        existing = RuleScheme(name='overwrite_test', quantity_tolerance=1.0)
        save_rule_scheme(existing)
        
        import_data = [
            {
                'name': 'overwrite_test',
                'quantity_tolerance': 50.0
            }
        ]
        
        imported, skipped, overwritten, renamed = import_rule_schemes(import_data, 'overwrite')
        
        assert imported == 0
        assert skipped == 0
        assert overwritten == 1
        
        scheme = get_rule_scheme('overwrite_test')
        assert scheme.quantity_tolerance == 50.0
    
    def test_import_schemes_rename(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, import_rule_schemes, get_rule_scheme
        
        existing = RuleScheme(name='rename_test', quantity_tolerance=1.0)
        save_rule_scheme(existing)
        
        import_data = [
            {
                'name': 'rename_test',
                'quantity_tolerance': 30.0
            }
        ]
        
        imported, skipped, overwritten, renamed = import_rule_schemes(import_data, 'rename')
        
        assert imported == 0
        assert skipped == 0
        assert overwritten == 0
        assert renamed == 1
        
        scheme = get_rule_scheme('rename_test')
        assert scheme is not None
        assert scheme.quantity_tolerance == 1.0
        
        renamed_scheme = get_rule_scheme('rename_test_imported_1')
        assert renamed_scheme is not None
        assert renamed_scheme.quantity_tolerance == 30.0


class TestToleranceLogic:
    def test_apply_tolerance_strict(self):
        from purchase_reconciliation.commands.diff import apply_tolerance
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff=0.5, amount_diff=10.0,
            quantity_tolerance=0.0, amount_tolerance=0.0
        )
        assert qty_tolerated == False
        assert amt_tolerated == False
    
    def test_apply_tolerance_with_values(self):
        from purchase_reconciliation.commands.diff import apply_tolerance
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff=0.5, amount_diff=10.0,
            quantity_tolerance=1.0, amount_tolerance=20.0
        )
        assert qty_tolerated == True
        assert amt_tolerated == True
    
    def test_apply_tolerance_partial(self):
        from purchase_reconciliation.commands.diff import apply_tolerance
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff=0.5, amount_diff=50.0,
            quantity_tolerance=1.0, amount_tolerance=20.0
        )
        assert qty_tolerated == True
        assert amt_tolerated == False
    
    def test_apply_tolerance_exactly_at_boundary(self):
        from purchase_reconciliation.commands.diff import apply_tolerance
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff=1.0, amount_diff=20.0,
            quantity_tolerance=1.0, amount_tolerance=20.0
        )
        assert qty_tolerated == True
        assert amt_tolerated == True
    
    def test_apply_tolerance_beyond_boundary(self):
        from purchase_reconciliation.commands.diff import apply_tolerance
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff=1.1, amount_diff=20.1,
            quantity_tolerance=1.0, amount_tolerance=20.0
        )
        assert qty_tolerated == False
        assert amt_tolerated == False
    
    def test_apply_tolerance_negative_diff(self):
        from purchase_reconciliation.commands.diff import apply_tolerance
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff=-0.8, amount_diff=-15.0,
            quantity_tolerance=1.0, amount_tolerance=20.0
        )
        assert qty_tolerated == True
        assert amt_tolerated == True


class TestRuleSchemeModel:
    def test_to_dict(self):
        from purchase_reconciliation.models import RuleScheme
        
        scheme = RuleScheme(
            name='model_test',
            business_line='华北区',
            quantity_tolerance=3.0,
            amount_tolerance=200.0,
            date_offset_days=5,
            required_fields=['field1', 'field2'],
            ignored_fields=['field3']
        )
        
        data = scheme.to_dict()
        
        assert data['name'] == 'model_test'
        assert data['business_line'] == '华北区'
        assert data['quantity_tolerance'] == 3.0
        assert data['amount_tolerance'] == 200.0
        assert data['date_offset_days'] == 5
        assert data['required_fields'] == ['field1', 'field2']
        assert data['ignored_fields'] == ['field3']
    
    def test_from_dict(self):
        from purchase_reconciliation.models import RuleScheme
        
        data = {
            'name': 'from_dict_test',
            'business_line': '西南区',
            'description': '测试描述',
            'quantity_tolerance': 2.5,
            'amount_tolerance': 150.0,
            'date_offset_days': -2,
            'required_fields': ['a', 'b'],
            'ignored_fields': ['c']
        }
        
        scheme = RuleScheme.from_dict(data)
        
        assert scheme.name == 'from_dict_test'
        assert scheme.business_line == '西南区'
        assert scheme.description == '测试描述'
        assert scheme.quantity_tolerance == 2.5
        assert scheme.amount_tolerance == 150.0
        assert scheme.date_offset_days == -2
        assert scheme.required_fields == ['a', 'b']
        assert scheme.ignored_fields == ['c']
    
    def test_roundtrip(self):
        from purchase_reconciliation.models import RuleScheme
        
        original = RuleScheme(
            name='roundtrip_test',
            business_line='东北区',
            description='往返测试',
            quantity_tolerance=4.0,
            amount_tolerance=300.0,
            date_offset_days=7,
            required_fields=['x', 'y', 'z'],
            ignored_fields=['w']
        )
        
        data = original.to_dict()
        restored = RuleScheme.from_dict(data)
        
        assert restored.name == original.name
        assert restored.business_line == original.business_line
        assert restored.description == original.description
        assert restored.quantity_tolerance == original.quantity_tolerance
        assert restored.amount_tolerance == original.amount_tolerance
        assert restored.date_offset_days == original.date_offset_days
        assert restored.required_fields == original.required_fields
        assert restored.ignored_fields == original.ignored_fields


class TestCLIHelpExamples:
    def test_scheme_command_available(self):
        from purchase_reconciliation.cli import cli
        commands = [cmd.name for cmd in cli.commands.values()]
        assert 'scheme' in commands
    
    def test_scheme_subcommands(self):
        from purchase_reconciliation.commands import scheme_cmd
        subcommands = [cmd.name for cmd in scheme_cmd.scheme_command.commands.values()]
        assert 'create' in subcommands
        assert 'list' in subcommands
        assert 'show' in subcommands
        assert 'switch' in subcommands
        assert 'delete' in subcommands
        assert 'export' in subcommands
        assert 'import' in subcommands
        assert 'active' in subcommands
        assert 'update' in subcommands
    
    def test_diff_command_scheme_option(self):
        from purchase_reconciliation.commands.diff import check_diff
        param_names = [p.name for p in check_diff.params]
        assert 'scheme' in param_names
        assert 'no_scheme' in param_names
    
    def test_batch_command_scheme_option(self):
        from purchase_reconciliation.commands.batch import create_batch
        param_names = [p.name for p in create_batch.params]
        assert 'scheme' in param_names
        assert 'no_scheme' in param_names


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
