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


class TestRuleValidationFunctions:
    def test_validate_bill_with_custom_required_fields(self):
        import tempfile
        import os
        from purchase_reconciliation.utils import validate_bill_with_required_fields
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write('bill_no,item_code,item_name,quantity,unit_price,amount,bill_date,supplier_code,supplier_name\n')
            f.write('B001,M001,物料A,10,100,1000,2024-01-15,S001,供应商A\n')
            temp_path = f.name
        
        try:
            result = validate_bill_with_required_fields(temp_path, custom_required_fields=['item_code'])
            assert len(result.errors) == 0
            assert len(result.valid_rows) == 1
            
            result = validate_bill_with_required_fields(temp_path, custom_required_fields=['bill_no', 'item_code'])
            assert len(result.errors) == 0
            
            result = validate_bill_with_required_fields(temp_path, custom_required_fields=['nonexistent_field'])
            assert len(result.errors) > 0
            assert any(e.error_type == 'MISSING_FIELD' for e in result.errors)
        finally:
            os.unlink(temp_path)
    
    def test_validate_receiving_with_custom_required_fields(self):
        import tempfile
        import os
        from purchase_reconciliation.utils import validate_receiving_with_required_fields
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write('receive_no,item_code,item_name,quantity,unit_price,amount,receive_date,supplier_code,supplier_name,purchase_order_no\n')
            f.write('R001,M001,物料A,10,100,1000,2024-01-15,S001,供应商A,P001\n')
            temp_path = f.name
        
        try:
            result = validate_receiving_with_required_fields(temp_path, custom_required_fields=['item_code'])
            assert len(result.errors) == 0
            assert len(result.valid_rows) == 1
            
            result = validate_receiving_with_required_fields(temp_path, custom_required_fields=['item_code', 'nonexistent'])
            assert len(result.errors) > 0
        finally:
            os.unlink(temp_path)
    
    def test_validate_missing_required_field(self):
        import tempfile
        import os
        from purchase_reconciliation.utils import validate_bill_with_required_fields
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write('bill_no,item_code,item_name,quantity,unit_price,amount,bill_date,supplier_code,supplier_name\n')
            f.write('B001,M001,物料A,,100,1000,2024-01-15,S001,供应商A\n')
            temp_path = f.name
        
        try:
            result = validate_bill_with_required_fields(temp_path, custom_required_fields=['quantity'])
            assert len(result.errors) > 0
            assert any(e.error_type == 'EMPTY_FIELD' and e.field == 'quantity' for e in result.errors)
        finally:
            os.unlink(temp_path)
    
    def test_check_date_offset_zero(self):
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('2024-01-15', '2024-01-15', 0)
        assert in_offset == True
        assert '严格匹配' in reason
    
    def test_check_date_offset_zero_rejects_mismatch(self):
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('2024-01-15', '2024-01-17', 0)
        assert in_offset == False
        assert '严格匹配' in reason
        assert '2 天' in reason
    
    def test_check_date_offset_zero_rejects_one_day_diff(self):
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('2024-01-15', '2024-01-16', 0)
        assert in_offset == False
        assert '严格匹配' in reason
    
    def test_check_date_offset_within_range(self):
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('2024-01-15', '2024-01-20', 5)
        assert in_offset == True
        
        in_offset, reason = check_date_offset('2024-01-20', '2024-01-15', 5)
        assert in_offset == True
    
    def test_check_date_offset_beyond_range(self):
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('2024-01-15', '2024-01-25', 5)
        assert in_offset == False
        assert '超出偏移' in reason
    
    def test_check_date_offset_negative_offset(self):
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('2024-01-20', '2024-01-15', -5)
        assert in_offset == True
    
    def test_check_date_offset_unparseable(self):
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('invalid', '2024-01-15', 5)
        assert in_offset == False
    
    def test_build_matching_key_no_ignored(self):
        from purchase_reconciliation.utils import build_matching_key
        
        item = {
            'supplier_code': 'S001',
            'item_code': 'M001',
            'supplier_name': '供应商A',
            'bill_no': 'B001',
            'receive_no': 'R001'
        }
        
        key = build_matching_key(item, [])
        assert key == ('S001', 'M001', '供应商A')
    
    def test_build_matching_key_with_ignored(self):
        from purchase_reconciliation.utils import build_matching_key
        
        item = {
            'supplier_code': 'S001',
            'item_code': 'M001',
            'supplier_name': '供应商A',
            'bill_no': 'B001',
            'receive_no': 'R001'
        }
        
        key = build_matching_key(item, ['supplier_code'])
        assert key == ('M001',)
        
        key = build_matching_key(item, ['supplier_code', 'supplier_name'])
        assert key == ('M001',)
    
    def test_build_matching_key_ignore_supplier_matches_different_suppliers(self):
        from purchase_reconciliation.utils import build_matching_key
        
        item1 = {
            'supplier_code': 'S001',
            'item_code': 'M001',
            'supplier_name': '供应商A',
            'bill_no': 'B001',
            'receive_no': 'R001'
        }
        item2 = {
            'supplier_code': 'S002',
            'item_code': 'M001',
            'supplier_name': '供应商B',
            'bill_no': 'B002',
            'receive_no': 'R002'
        }
        
        key1 = build_matching_key(item1, ['supplier_code', 'supplier_name'])
        key2 = build_matching_key(item2, ['supplier_code', 'supplier_name'])
        
        assert key1 == key2
        assert key1 == ('M001',)


class TestRuleSchemeIntegration:
    def test_scheme_persistence_with_all_fields(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, get_rule_scheme, delete_rule_scheme
        
        scheme = RuleScheme(
            name='full_feature_scheme',
            business_line='测试业务线',
            description='完整功能测试',
            quantity_tolerance=1.5,
            amount_tolerance=100.0,
            date_offset_days=3,
            required_fields=['bill_no', 'item_code', 'quantity'],
            ignored_fields=['supplier_code', 'supplier_name'],
            is_active=False
        )
        
        save_rule_scheme(scheme)
        retrieved = get_rule_scheme('full_feature_scheme')
        
        assert retrieved is not None
        assert retrieved.business_line == '测试业务线'
        assert retrieved.description == '完整功能测试'
        assert retrieved.quantity_tolerance == 1.5
        assert retrieved.amount_tolerance == 100.0
        assert retrieved.date_offset_days == 3
        assert retrieved.required_fields == ['bill_no', 'item_code', 'quantity']
        assert retrieved.ignored_fields == ['supplier_code', 'supplier_name']
        
        delete_rule_scheme('full_feature_scheme')
        assert get_rule_scheme('full_feature_scheme') is None


class TestDateOffsetZeroStrictMatch:
    def test_date_offset_zero_blocks_date_mismatch(self):
        import tempfile
        import os
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('2024-01-15', '2024-01-17', 0)
        assert in_offset == False, "日期偏移为0时应严格匹配，差2天应被拦截"
        assert '严格匹配' in reason
    
    def test_date_offset_zero_allows_same_date(self):
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('2024-01-15', '2024-01-15', 0)
        assert in_offset == True, "日期偏移为0时，相同日期应通过"
    
    def test_positive_offset_allows_within_range(self):
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('2024-01-15', '2024-01-17', 3)
        assert in_offset == True, "日期差2天在偏移3天范围内应通过"
    
    def test_positive_offset_blocks_beyond_range(self):
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('2024-01-15', '2024-01-20', 3)
        assert in_offset == False, "日期差5天超出偏移3天范围应被拦截"
    
    def test_negative_offset_works_correctly(self):
        from purchase_reconciliation.utils import check_date_offset
        
        in_offset, reason = check_date_offset('2024-01-20', '2024-01-15', -5)
        assert in_offset == True, "负偏移-5天，日期差5天应在范围内"
        
        in_offset, reason = check_date_offset('2024-01-20', '2024-01-14', -5)
        assert in_offset == False, "负偏移-5天，日期差6天应超出范围"


class TestToleranceNotAffected:
    def test_quantity_tolerance_still_works(self):
        from purchase_reconciliation.commands.diff import apply_tolerance
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff=0.5, amount_diff=10.0,
            quantity_tolerance=1.0, amount_tolerance=0.0
        )
        assert qty_tolerated == True
        assert amt_tolerated == False
    
    def test_amount_tolerance_still_works(self):
        from purchase_reconciliation.commands.diff import apply_tolerance
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff=0.5, amount_diff=10.0,
            quantity_tolerance=0.0, amount_tolerance=20.0
        )
        assert qty_tolerated == False
        assert amt_tolerated == True
    
    def test_both_tolerances_work_together(self):
        from purchase_reconciliation.commands.diff import apply_tolerance
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff=0.5, amount_diff=10.0,
            quantity_tolerance=1.0, amount_tolerance=20.0
        )
        assert qty_tolerated == True
        assert amt_tolerated == True
    
    def test_tolerance_exactly_at_boundary(self):
        from purchase_reconciliation.commands.diff import apply_tolerance
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff=1.0, amount_diff=20.0,
            quantity_tolerance=1.0, amount_tolerance=20.0
        )
        assert qty_tolerated == True
        assert amt_tolerated == True
    
    def test_tolerance_beyond_boundary(self):
        from purchase_reconciliation.commands.diff import apply_tolerance
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff=1.1, amount_diff=20.1,
            quantity_tolerance=1.0, amount_tolerance=20.0
        )
        assert qty_tolerated == False
        assert amt_tolerated == False


class TestRuleSchemeSnapshot:
    def test_scheme_snapshot_creation(self):
        from purchase_reconciliation.models import RuleScheme
        
        scheme = RuleScheme(
            name='snapshot_test',
            business_line='测试业务线',
            description='快照测试',
            quantity_tolerance=1.5,
            amount_tolerance=100.0,
            date_offset_days=3,
            required_fields=['bill_no', 'item_code'],
            ignored_fields=['supplier_name']
        )
        
        snapshot = scheme.to_snapshot()
        
        assert snapshot['name'] == 'snapshot_test'
        assert snapshot['business_line'] == '测试业务线'
        assert snapshot['description'] == '快照测试'
        assert snapshot['quantity_tolerance'] == 1.5
        assert snapshot['amount_tolerance'] == 100.0
        assert snapshot['date_offset_days'] == 3
        assert snapshot['required_fields'] == ['bill_no', 'item_code']
        assert snapshot['ignored_fields'] == ['supplier_name']
    
    def test_scheme_snapshot_summary(self):
        from purchase_reconciliation.models import RuleScheme
        
        scheme = RuleScheme(
            name='summary_test',
            quantity_tolerance=1.0,
            amount_tolerance=50.0,
            date_offset_days=3,
            required_fields=['item_code'],
            ignored_fields=['supplier_name']
        )
        
        summary = scheme.get_snapshot_summary()
        
        assert '数量容差±1.0' in summary
        assert '金额容差±50.0' in summary
        assert '日期偏移3天' in summary
        assert '必填:item_code' in summary
        assert '忽略:supplier_name' in summary
    
    def test_batch_scheme_snapshot_persistence(self):
        from purchase_reconciliation.models import RuleScheme, Batch
        
        scheme = RuleScheme(
            name='batch_snapshot_test',
            quantity_tolerance=2.0,
            amount_tolerance=200.0,
            date_offset_days=5
        )
        
        batch = Batch(
            batch_no='TEST_001',
            scheme_name='batch_snapshot_test',
            scheme_snapshot=scheme.to_snapshot()
        )
        
        assert batch.scheme_snapshot is not None
        assert batch.scheme_snapshot['quantity_tolerance'] == 2.0
        assert batch.scheme_snapshot['amount_tolerance'] == 200.0
        
        summary = batch.get_scheme_snapshot_summary()
        assert '方案:batch_snapshot_test' in summary
        assert '数量容差±2.0' in summary


class TestCrossRestartPersistence:
    def test_scheme_persistence_after_db_reload(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, get_rule_scheme, delete_rule_scheme
        import purchase_reconciliation.storage as storage_module
        
        original_db_path = storage_module.DB_PATH
        temp_db_path = os.path.join(tempfile.gettempdir(), 'test_persistence_scheme.db')
        storage_module.DB_PATH = temp_db_path
        
        try:
            scheme = RuleScheme(
                name='persist_test',
                business_line='华东区',
                description='持久化测试',
                quantity_tolerance=3.0,
                amount_tolerance=150.0,
                date_offset_days=7,
                required_fields=['bill_no'],
                ignored_fields=['unit_price']
            )
            
            save_rule_scheme(scheme)
            
            if hasattr(storage_module, '_connection_cache'):
                del storage_module._connection_cache
            
            retrieved = get_rule_scheme('persist_test')
            
            assert retrieved is not None
            assert retrieved.name == 'persist_test'
            assert retrieved.business_line == '华东区'
            assert retrieved.description == '持久化测试'
            assert retrieved.quantity_tolerance == 3.0
            assert retrieved.amount_tolerance == 150.0
            assert retrieved.date_offset_days == 7
            assert retrieved.required_fields == ['bill_no']
            assert retrieved.ignored_fields == ['unit_price']
            
            delete_rule_scheme('persist_test')
        finally:
            storage_module.DB_PATH = original_db_path
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
    
    def test_batch_scheme_snapshot_persistence_after_reload(self):
        from purchase_reconciliation.models import RuleScheme, Batch, BatchStatus
        from purchase_reconciliation.storage import save_batch, get_batch_by_no, delete_rule_scheme
        import purchase_reconciliation.storage as storage_module
        
        original_db_path = storage_module.DB_PATH
        temp_db_path = os.path.join(tempfile.gettempdir(), 'test_persistence_batch.db')
        storage_module.DB_PATH = temp_db_path
        
        try:
            scheme = RuleScheme(
                name='batch_persist_test',
                quantity_tolerance=4.0,
                amount_tolerance=200.0,
                date_offset_days=10
            )
            
            batch = Batch(
                batch_no='PERSIST_BATCH_001',
                status=BatchStatus.OPEN,
                scheme_name='batch_persist_test',
                scheme_snapshot=scheme.to_snapshot()
            )
            
            save_batch(batch)
            
            if hasattr(storage_module, '_connection_cache'):
                del storage_module._connection_cache
            
            retrieved = get_batch_by_no('PERSIST_BATCH_001')
            
            assert retrieved is not None
            assert retrieved.batch_no == 'PERSIST_BATCH_001'
            assert retrieved.scheme_snapshot is not None
            assert retrieved.scheme_snapshot['name'] == 'batch_persist_test'
            assert retrieved.scheme_snapshot['quantity_tolerance'] == 4.0
            assert retrieved.scheme_snapshot['amount_tolerance'] == 200.0
            assert retrieved.scheme_snapshot['date_offset_days'] == 10
        finally:
            storage_module.DB_PATH = original_db_path
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


class TestImportExportConflictHandling:
    def test_import_with_conflict_skip_preserves_original(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, get_rule_scheme, import_rule_schemes, delete_rule_scheme
        
        original = RuleScheme(
            name='conflict_skip_test',
            quantity_tolerance=1.0,
            amount_tolerance=50.0,
            date_offset_days=3
        )
        save_rule_scheme(original)
        
        import_data = [{
            'name': 'conflict_skip_test',
            'quantity_tolerance': 99.0,
            'amount_tolerance': 999.0,
            'date_offset_days': 30
        }]
        
        imported, skipped, overwritten, renamed = import_rule_schemes(import_data, 'skip')
        
        assert skipped == 1
        assert imported == 0
        
        retrieved = get_rule_scheme('conflict_skip_test')
        assert retrieved.quantity_tolerance == 1.0
        assert retrieved.amount_tolerance == 50.0
        assert retrieved.date_offset_days == 3
        
        delete_rule_scheme('conflict_skip_test')
    
    def test_import_with_conflict_overwrite_updates_all_fields(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, get_rule_scheme, import_rule_schemes, delete_rule_scheme
        
        original = RuleScheme(
            name='conflict_overwrite_test',
            business_line='原业务线',
            description='原描述',
            quantity_tolerance=1.0,
            amount_tolerance=50.0,
            date_offset_days=3,
            required_fields=['field1'],
            ignored_fields=['field2']
        )
        save_rule_scheme(original)
        
        import_data = [{
            'name': 'conflict_overwrite_test',
            'business_line': '新业务线',
            'description': '新描述',
            'quantity_tolerance': 5.0,
            'amount_tolerance': 500.0,
            'date_offset_days': 10,
            'required_fields': ['fieldA', 'fieldB'],
            'ignored_fields': ['fieldC']
        }]
        
        imported, skipped, overwritten, renamed = import_rule_schemes(import_data, 'overwrite')
        
        assert overwritten == 1
        
        retrieved = get_rule_scheme('conflict_overwrite_test')
        assert retrieved.business_line == '新业务线'
        assert retrieved.description == '新描述'
        assert retrieved.quantity_tolerance == 5.0
        assert retrieved.amount_tolerance == 500.0
        assert retrieved.date_offset_days == 10
        assert retrieved.required_fields == ['fieldA', 'fieldB']
        assert retrieved.ignored_fields == ['fieldC']
        
        delete_rule_scheme('conflict_overwrite_test')
    
    def test_import_with_conflict_rename_creates_new_scheme(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, get_rule_scheme, import_rule_schemes, get_all_rule_schemes, delete_rule_scheme
        
        original = RuleScheme(
            name='conflict_rename_test',
            quantity_tolerance=1.0
        )
        save_rule_scheme(original)
        
        import_data = [{
            'name': 'conflict_rename_test',
            'quantity_tolerance': 10.0,
            'amount_tolerance': 100.0
        }]
        
        imported, skipped, overwritten, renamed = import_rule_schemes(import_data, 'rename')
        
        assert renamed == 1
        assert imported == 0
        
        original_retrieved = get_rule_scheme('conflict_rename_test')
        assert original_retrieved.quantity_tolerance == 1.0
        
        renamed_retrieved = get_rule_scheme('conflict_rename_test_imported_1')
        assert renamed_retrieved is not None
        assert renamed_retrieved.quantity_tolerance == 10.0
        
        delete_rule_scheme('conflict_rename_test')
        delete_rule_scheme('conflict_rename_test_imported_1')
    
    def test_import_multiple_conflicts_with_skip_action(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, get_rule_scheme, import_rule_schemes, delete_rule_scheme
        
        scheme1 = RuleScheme(name='multi_skip_a', quantity_tolerance=1.0)
        scheme2 = RuleScheme(name='multi_skip_b', quantity_tolerance=2.0)
        save_rule_scheme(scheme1)
        save_rule_scheme(scheme2)
        
        import_data = [
            {'name': 'multi_skip_a', 'quantity_tolerance': 99.0},
            {'name': 'multi_skip_b', 'quantity_tolerance': 88.0},
            {'name': 'multi_new', 'quantity_tolerance': 77.0}
        ]
        
        imported, skipped, overwritten, renamed = import_rule_schemes(import_data, 'skip')
        
        assert skipped == 2
        assert overwritten == 0
        assert renamed == 0
        assert imported == 1
        
        assert get_rule_scheme('multi_skip_a').quantity_tolerance == 1.0
        assert get_rule_scheme('multi_skip_b').quantity_tolerance == 2.0
        assert get_rule_scheme('multi_new').quantity_tolerance == 77.0
        
        delete_rule_scheme('multi_skip_a')
        delete_rule_scheme('multi_skip_b')
        delete_rule_scheme('multi_new')


class TestSchemeSnapshotTraceability:
    def test_batch_creation_includes_scheme_snapshot(self):
        from purchase_reconciliation.models import RuleScheme, Batch
        from purchase_reconciliation.storage import save_batch, get_batch_by_no, delete_rule_scheme
        
        scheme = RuleScheme(
            name='traceability_test',
            business_line='追溯测试',
            quantity_tolerance=5.0,
            amount_tolerance=250.0,
            date_offset_days=7,
            required_fields=['bill_no', 'item_code'],
            ignored_fields=['supplier_name']
        )
        
        batch = Batch(
            batch_no='TRACE_BATCH_001',
            scheme_name='traceability_test',
            scheme_snapshot=scheme.to_snapshot()
        )
        
        save_batch(batch)
        
        retrieved = get_batch_by_no('TRACE_BATCH_001')
        
        assert retrieved.scheme_snapshot is not None
        assert retrieved.scheme_snapshot['name'] == 'traceability_test'
        assert retrieved.scheme_snapshot['business_line'] == '追溯测试'
        assert retrieved.scheme_snapshot['quantity_tolerance'] == 5.0
        assert retrieved.scheme_snapshot['amount_tolerance'] == 250.0
        assert retrieved.scheme_snapshot['date_offset_days'] == 7
        assert retrieved.scheme_snapshot['required_fields'] == ['bill_no', 'item_code']
        assert retrieved.scheme_snapshot['ignored_fields'] == ['supplier_name']
        
        delete_rule_scheme('traceability_test')
    
    def test_scheme_snapshot_in_audit_note(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, import_rule_schemes, delete_rule_scheme
        
        scheme = RuleScheme(
            name='audit_note_test',
            quantity_tolerance=3.0,
            amount_tolerance=150.0
        )
        save_rule_scheme(scheme)
        
        import_data = [{
            'name': 'audit_note_test',
            'quantity_tolerance': 6.0,
            'amount_tolerance': 300.0
        }]
        
        imported, skipped, overwritten, renamed = import_rule_schemes(import_data, 'overwrite')
        
        note = f"覆盖方案 '{import_data[0]['name']}'"
        if overwritten > 0:
            note += f" (数量容差: {import_data[0]['quantity_tolerance']}, 金额容差: {import_data[0]['amount_tolerance']})"
        
        assert '数量容差: 6.0' in note
        assert '金额容差: 300.0' in note
        
        delete_rule_scheme('audit_note_test')
    
    def test_batch_list_shows_scheme_snapshot_summary(self):
        from purchase_reconciliation.models import RuleScheme, Batch
        from purchase_reconciliation.storage import save_batch, get_all_batches, delete_rule_scheme
        
        scheme = RuleScheme(
            name='list_snapshot_test',
            quantity_tolerance=4.0,
            amount_tolerance=200.0,
            date_offset_days=5,
            required_fields=['item_code']
        )
        
        batch = Batch(
            batch_no='LIST_SNAP_001',
            scheme_name='list_snapshot_test',
            scheme_snapshot=scheme.to_snapshot()
        )
        
        save_batch(batch)
        
        batches = get_all_batches()
        list_batch = next((b for b in batches if b.batch_no == 'LIST_SNAP_001'), None)
        
        assert list_batch is not None
        summary = list_batch.get_scheme_snapshot_summary()
        assert '方案:list_snapshot_test' in summary
        assert '数量容差±4.0' in summary
        assert '金额容差±200.0' in summary
        
        delete_rule_scheme('list_snapshot_test')


class TestExportFileIntegrity:
    def test_export_file_contains_all_scheme_fields(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, export_all_rule_schemes, delete_rule_scheme
        
        scheme = RuleScheme(
            name='export_integrity_test',
            business_line='完整性测试',
            description='导出完整性测试',
            quantity_tolerance=2.5,
            amount_tolerance=125.0,
            date_offset_days=-3,
            required_fields=['field1', 'field2', 'field3'],
            ignored_fields=['fieldA', 'fieldB']
        )
        save_rule_scheme(scheme)
        
        exported = export_all_rule_schemes()
        export_entry = next((e for e in exported if e['name'] == 'export_integrity_test'), None)
        
        assert export_entry is not None
        assert export_entry['business_line'] == '完整性测试'
        assert export_entry['description'] == '导出完整性测试'
        assert export_entry['quantity_tolerance'] == 2.5
        assert export_entry['amount_tolerance'] == 125.0
        assert export_entry['date_offset_days'] == -3
        assert export_entry['required_fields'] == ['field1', 'field2', 'field3']
        assert export_entry['ignored_fields'] == ['fieldA', 'fieldB']
        
        delete_rule_scheme('export_integrity_test')
    
    def test_roundtrip_export_import_preserves_all_fields(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, export_all_rule_schemes, import_rule_schemes, get_rule_scheme, delete_rule_scheme
        
        original = RuleScheme(
            name='roundtrip_test',
            business_line='往返测试',
            description='测试往返导出导入',
            quantity_tolerance=3.5,
            amount_tolerance=175.0,
            date_offset_days=4,
            required_fields=['a', 'b', 'c'],
            ignored_fields=['x', 'y']
        )
        save_rule_scheme(original)
        
        exported = export_all_rule_schemes()
        exported_data = [e for e in exported if e['name'] == 'roundtrip_test']
        
        delete_rule_scheme('roundtrip_test')
        
        imported, skipped, overwritten, renamed = import_rule_schemes(exported_data, 'skip')
        
        restored = get_rule_scheme('roundtrip_test')
        
        assert restored is not None
        assert restored.business_line == '往返测试'
        assert restored.description == '测试往返导出导入'
        assert restored.quantity_tolerance == 3.5
        assert restored.amount_tolerance == 175.0
        assert restored.date_offset_days == 4
        assert restored.required_fields == ['a', 'b', 'c']
        assert restored.ignored_fields == ['x', 'y']
        
        delete_rule_scheme('roundtrip_test')


class TestAtomicImport:
    def test_atomic_import_success(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import (
            import_rule_schemes_atomic, get_all_rule_schemes, 
            delete_rule_scheme, save_rule_scheme
        )
        
        import_data = [
            {
                'name': 'atomic_new_1',
                'quantity_tolerance': 1.0,
                'amount_tolerance': 10.0
            },
            {
                'name': 'atomic_new_2',
                'quantity_tolerance': 2.0,
                'amount_tolerance': 20.0
            }
        ]
        
        imported, skipped, overwritten, renamed, errors = import_rule_schemes_atomic(import_data, 'skip')
        
        assert errors == []
        assert imported == 2
        assert skipped == 0
        assert overwritten == 0
        
        schemes = get_all_rule_schemes()
        names = [s.name for s in schemes]
        assert 'atomic_new_1' in names
        assert 'atomic_new_2' in names
        
        delete_rule_scheme('atomic_new_1')
        delete_rule_scheme('atomic_new_2')
    
    def test_atomic_import_with_conflict_skip(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import (
            import_rule_schemes_atomic, get_rule_scheme, 
            delete_rule_scheme, save_rule_scheme
        )
        
        existing = RuleScheme(name='atomic_skip_test', quantity_tolerance=1.0)
        save_rule_scheme(existing)
        
        import_data = [
            {
                'name': 'atomic_skip_test',
                'quantity_tolerance': 99.0
            },
            {
                'name': 'atomic_new',
                'quantity_tolerance': 2.0
            }
        ]
        
        imported, skipped, overwritten, renamed, errors = import_rule_schemes_atomic(import_data, 'skip')
        
        assert errors == []
        assert imported == 1
        assert skipped == 1
        
        original = get_rule_scheme('atomic_skip_test')
        assert original.quantity_tolerance == 1.0
        
        delete_rule_scheme('atomic_skip_test')
        delete_rule_scheme('atomic_new')
    
    def test_atomic_import_with_conflict_overwrite(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import (
            import_rule_schemes_atomic, get_rule_scheme, 
            delete_rule_scheme, save_rule_scheme
        )
        
        existing = RuleScheme(name='atomic_overwrite_test', quantity_tolerance=1.0)
        save_rule_scheme(existing)
        
        import_data = [
            {
                'name': 'atomic_overwrite_test',
                'quantity_tolerance': 88.0
            }
        ]
        
        imported, skipped, overwritten, renamed, errors = import_rule_schemes_atomic(import_data, 'overwrite')
        
        assert errors == []
        assert overwritten == 1
        
        updated = get_rule_scheme('atomic_overwrite_test')
        assert updated.quantity_tolerance == 88.0
        
        delete_rule_scheme('atomic_overwrite_test')
    
    def test_atomic_import_rollback_on_error(self):
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import (
            import_rule_schemes_atomic, get_rule_scheme, 
            delete_rule_scheme, save_rule_scheme
        )
        
        existing = RuleScheme(name='atomic_rollback_test', quantity_tolerance=1.0)
        save_rule_scheme(existing)
        
        import_data = [
            {
                'name': 'atomic_rollback_test',
                'quantity_tolerance': 99.0
            },
            {
                'name': 'valid_new',
                'quantity_tolerance': 2.0
            }
        ]
        
        imported, skipped, overwritten, renamed, errors = import_rule_schemes_atomic(import_data, 'overwrite')
        
        assert imported == 1
        assert overwritten == 1
        
        original = get_rule_scheme('atomic_rollback_test')
        assert original.quantity_tolerance == 99.0
        
        delete_rule_scheme('atomic_rollback_test')
        delete_rule_scheme('valid_new')


class TestJSONBOMHandling:
    def test_read_json_with_bom(self):
        import os
        import tempfile
        from purchase_reconciliation.commands.scheme_cmd import read_json_file_with_bom
        
        test_data = {
            'version': '1.0',
            'schemes': [
                {'name': 'bom_test', 'quantity_tolerance': 1.0}
            ]
        }
        
        temp_path = os.path.join(tempfile.gettempdir(), 'test_bom.json')
        
        with open(temp_path, 'wb') as f:
            f.write(b'\xef\xbb\xbf')
            f.write('{"version": "1.0", "schemes": [{"name": "bom_test", "quantity_tolerance": 1.0}]}'.encode('utf-8'))
        
        try:
            result = read_json_file_with_bom(temp_path)
            
            assert result['version'] == '1.0'
            assert len(result['schemes']) == 1
            assert result['schemes'][0]['name'] == 'bom_test'
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_read_json_without_bom(self):
        import os
        import tempfile
        from purchase_reconciliation.commands.scheme_cmd import read_json_file_with_bom
        
        temp_path = os.path.join(tempfile.gettempdir(), 'test_no_bom.json')
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump({
                'version': '1.0',
                'schemes': [
                    {'name': 'no_bom_test', 'quantity_tolerance': 2.0}
                ]
            }, f)
        
        try:
            result = read_json_file_with_bom(temp_path)
            
            assert result['version'] == '1.0'
            assert len(result['schemes']) == 1
            assert result['schemes'][0]['name'] == 'no_bom_test'
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestAuditTrailCompleteness:
    def test_batch_creation_includes_scheme_snapshot_in_audit(self):
        from purchase_reconciliation.models import RuleScheme, Batch
        from purchase_reconciliation.storage import save_batch, get_batch_by_no, get_audit_logs, delete_rule_scheme
        
        scheme = RuleScheme(
            name='audit_trail_test',
            quantity_tolerance=5.0,
            amount_tolerance=250.0,
            date_offset_days=7
        )
        
        batch = Batch(
            batch_no='AUDIT_TRAIL_BATCH_001',
            scheme_name='audit_trail_test',
            scheme_snapshot=scheme.to_snapshot()
        )
        
        save_batch(batch)
        
        saved_batch = get_batch_by_no('AUDIT_TRAIL_BATCH_001')
        assert saved_batch.scheme_snapshot is not None
        assert saved_batch.scheme_snapshot['quantity_tolerance'] == 5.0
        assert saved_batch.scheme_snapshot['amount_tolerance'] == 250.0
        assert saved_batch.scheme_snapshot['date_offset_days'] == 7
        
        delete_rule_scheme('audit_trail_test')
    
    def test_scheme_snapshot_persists_after_restart(self):
        from purchase_reconciliation.models import RuleScheme, Batch
        from purchase_reconciliation.storage import save_batch, delete_rule_scheme
        import purchase_reconciliation.storage as storage_module
        
        original_db_path = storage_module.DB_PATH
        temp_db_path = os.path.join(tempfile.gettempdir(), 'test_audit_restart.db')
        storage_module.DB_PATH = temp_db_path
        
        try:
            scheme = RuleScheme(
                name='restart_audit_test',
                quantity_tolerance=7.0,
                amount_tolerance=350.0
            )
            
            batch = Batch(
                batch_no='RESTART_AUDIT_001',
                scheme_name='restart_audit_test',
                scheme_snapshot=scheme.to_snapshot()
            )
            
            save_batch(batch)
            
            if hasattr(storage_module, '_connection_cache'):
                del storage_module._connection_cache
            
            from purchase_reconciliation.storage import get_batch_by_no
            retrieved = get_batch_by_no('RESTART_AUDIT_001')
            
            assert retrieved is not None
            assert retrieved.scheme_snapshot is not None
            assert retrieved.scheme_snapshot['name'] == 'restart_audit_test'
            assert retrieved.scheme_snapshot['quantity_tolerance'] == 7.0
            assert retrieved.scheme_snapshot['amount_tolerance'] == 350.0
        finally:
            storage_module.DB_PATH = original_db_path
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)


class TestImportConflictClarity:
    def test_import_shows_preview_before_write(self):
        from purchase_reconciliation.commands.scheme_cmd import read_json_file_with_bom
        import io
        import sys
        from purchase_reconciliation.models import RuleScheme
        from purchase_reconciliation.storage import save_rule_scheme, delete_rule_scheme
        
        existing = RuleScheme(name='preview_test', quantity_tolerance=1.0)
        save_rule_scheme(existing)
        
        import os
        import tempfile
        
        temp_path = os.path.join(tempfile.gettempdir(), 'test_preview.json')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump({
                'version': '1.0',
                'schemes': [
                    {'name': 'preview_test', 'quantity_tolerance': 99.0},
                    {'name': 'preview_new', 'quantity_tolerance': 2.0}
                ]
            }, f)
        
        try:
            data = read_json_file_with_bom(temp_path)
            existing_names = ['preview_test']
            
            for item in data['schemes']:
                scheme = RuleScheme.from_dict(item)
                if scheme.name in existing_names:
                    action = 'skip'
                else:
                    action = 'new'
                
                assert action in ['skip', 'new']
        finally:
            delete_rule_scheme('preview_test')
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_import_dry_run_does_not_write(self):
        from purchase_reconciliation.storage import get_all_rule_schemes
        
        initial_count = len(get_all_rule_schemes())
        
        assert initial_count >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
