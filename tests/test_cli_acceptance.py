import pytest
import subprocess
import os
import sys
import tempfile
import json
import sqlite3
import time

TEST_DB_PATH = os.path.join(tempfile.gettempdir(), 'test_cli_acceptance.db')
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_cli_command(cmd_args, timeout=60):
    """运行CLI命令并返回结果"""
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.join(PROJECT_ROOT, 'src') + os.pathsep + env.get('PYTHONPATH', '')
    
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'purchase_reconciliation.cli'] + cmd_args,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        return result
    except subprocess.TimeoutExpired:
        return None

def reset_test_database():
    """重置测试数据库"""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

@pytest.fixture(autouse=True)
def setup_test_env():
    """设置测试环境"""
    reset_test_database()
    
    os.environ['PURCHASE_RECON_DB_PATH'] = TEST_DB_PATH
    
    yield
    
    reset_test_database()
    if 'PURCHASE_RECON_DB_PATH' in os.environ:
        del os.environ['PURCHASE_RECON_DB_PATH']

class TestCLISmokeTest:
    """CLI入口冒烟测试 - 验证安装后入口可用"""
    
    def test_cli_help_command(self):
        """测试 purchase-recon --help 能正常输出"""
        result = run_cli_command(['--help'])
        assert result is not None, "CLI命令超时"
        assert result.returncode == 0, f"CLI帮助命令失败: {result.stderr}"
        assert 'Usage:' in result.stdout, "帮助输出格式不正确"
        assert 'Commands:' in result.stdout, "帮助输出应包含命令列表"
    
    def test_cli_version_command(self):
        """测试 purchase-recon --version 能正常输出"""
        result = run_cli_command(['--version'])
        assert result is not None, "CLI版本命令超时"
        assert result.returncode == 0, f"CLI版本命令失败: {result.stderr}"
        assert '1.0.0' in result.stdout, "版本号不正确"
    
    def test_cli_module_import(self):
        """测试模块入口能被Python导入"""
        try:
            import purchase_reconciliation
            import purchase_reconciliation.cli
            assert hasattr(purchase_reconciliation.cli, 'cli'), "cli对象不存在"
        except ImportError as e:
            pytest.fail(f"模块导入失败: {e}")
    
    def test_all_top_level_commands_available(self):
        """测试所有顶层命令都可用"""
        result = run_cli_command(['--help'])
        assert result.returncode == 0
        
        expected_commands = ['import', 'diff', 'scheme', 'config', 'batch', 
                           'appeal', 'rollback', 'export', 'status', 'audit']
        
        for cmd in expected_commands:
            assert cmd in result.stdout, f"命令 {cmd} 不在帮助输出中"
    
    def test_scheme_command_help(self):
        """测试 scheme 命令帮助"""
        result = run_cli_command(['scheme', '--help'])
        assert result.returncode == 0, f"scheme命令失败: {result.stderr}"
        assert 'create' in result.stdout
        assert 'list' in result.stdout
        assert 'import' in result.stdout
        assert 'export' in result.stdout
    
    def test_diff_command_help(self):
        """测试 diff 命令帮助"""
        result = run_cli_command(['diff', '--help'])
        assert result.returncode == 0, f"diff命令失败: {result.stderr}"
        assert 'check' in result.stdout
    
    def test_batch_command_help(self):
        """测试 batch 命令帮助"""
        result = run_cli_command(['batch', '--help'])
        assert result.returncode == 0, f"batch命令失败: {result.stderr}"
        assert 'create' in result.stdout
        assert 'list' in result.stdout

class TestFailedImportRollback:
    """失败导入回滚测试 - 确保导入失败时数据库状态不变"""
    
    def test_import_failed_due_to_invalid_json(self):
        """测试导入格式错误的JSON文件应回滚"""
        temp_file = os.path.join(tempfile.gettempdir(), 'invalid_scheme.json')
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write('{invalid json}')
        
        result = run_cli_command(['scheme', 'import', '-f', temp_file, '-c', 'skip'])
        
        assert '错误' in result.stdout, "无效JSON导入应该输出错误信息"
        assert 'Expecting property name' in result.stdout, "应该显示JSON解析错误"
        
        os.remove(temp_file)
    
    def test_import_failed_due_to_missing_name(self):
        """测试导入缺少name字段的方案应回滚"""
        temp_file = os.path.join(tempfile.gettempdir(), 'missing_name.json')
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump({
                'schemes': [
                    {'quantity_tolerance': 1.0}
                ]
            }, f)
        
        result = run_cli_command(['scheme', 'import', '-f', temp_file, '-c', 'skip'])
        
        assert '错误' in result.stdout, "缺少name字段的导入应该输出错误信息"
        assert "缺少 'name' 字段" in result.stdout
        
        os.remove(temp_file)
    
    def test_atomic_import_all_or_nothing(self):
        """测试原子导入 - 部分失败则全部回滚"""
        temp_file = os.path.join(tempfile.gettempdir(), 'mixed_schemes.json')
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump({
                'schemes': [
                    {'name': 'valid_scheme_1', 'quantity_tolerance': 1.0},
                    {'invalid_field': 'no_name_here'},
                    {'name': 'valid_scheme_2', 'quantity_tolerance': 2.0}
                ]
            }, f)
        
        result = run_cli_command(['scheme', 'import', '-f', temp_file, '-c', 'skip'])
        
        assert '错误' in result.stdout, "包含无效方案的导入应该输出错误信息"
        
        list_result = run_cli_command(['scheme', 'list'])
        assert 'valid_scheme_1' not in list_result.stdout, "失败导入不应留下有效方案"
        assert 'valid_scheme_2' not in list_result.stdout, "失败导入不应留下有效方案"
        
        os.remove(temp_file)
    
    def test_import_rollback_no_partial_records(self):
        """测试失败导入不应创建导入记录"""
        temp_file = os.path.join(tempfile.gettempdir(), 'fail_import.json')
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump({
                'schemes': [
                    {'invalid': 'data'}
                ]
            }, f)
        
        result = run_cli_command(['scheme', 'import', '-f', temp_file, '-c', 'skip'])
        
        assert '错误' in result.stdout
        
        import_list_result = run_cli_command(['audit', 'import-list'])
        assert 'fail_import.json' not in import_list_result.stdout, "失败导入不应创建审计记录"
        
        os.remove(temp_file)

class TestRuleConsistency:
    """规则一致性测试 - 确保diff check和batch create使用相同规则"""
    
    def test_same_tolerance_result_in_diff_and_batch(self):
        """测试相同规则在diff check和batch create中结果一致"""
        bill_path = os.path.join(PROJECT_ROOT, 'samples', 'supplier_bill.csv')
        receive_path = os.path.join(PROJECT_ROOT, 'samples', 'receiving_list.csv')
        
        run_cli_command(['scheme', 'create', '-n', 'consistency_test', '-q', '1.0', '-a', '50.0'])
        
        diff_result = run_cli_command([
            'diff', 'check', '-b', bill_path, '-r', receive_path, '-s', 'consistency_test'
        ])
        assert diff_result.returncode == 0
        
        diff_output = diff_result.stdout
        has_diff = '仍然失败的差异' in diff_output
        
        run_cli_command(['import', 'bill', '-f', bill_path])
        run_cli_command(['import', 'receiving', '-f', receive_path])
        
        batch_result = run_cli_command([
            'batch', 'create', '-o', 'test_user', '-R', 'reviewer', 
            '-s', 'consistency_test', '--dry-run'
        ])
        assert batch_result.returncode == 0
        
        batch_output = batch_result.stdout
        batch_has_diff = '发现' in batch_output and '条差异记录' in batch_output
        
        assert has_diff == batch_has_diff, "diff check和batch create对差异的判断应该一致"
    
    def test_strict_mode_no_tolerance(self):
        """测试严格模式下不应有容差放过"""
        bill_path = os.path.join(PROJECT_ROOT, 'samples', 'supplier_bill.csv')
        receive_path = os.path.join(PROJECT_ROOT, 'samples', 'receiving_list.csv')
        
        run_cli_command(['scheme', 'create', '-n', 'strict_test', '-q', '0', '-a', '0'])
        
        diff_result = run_cli_command([
            'diff', 'check', '-b', bill_path, '-r', receive_path, '-s', 'strict_test'
        ])
        
        assert '容差放过' not in diff_result.stdout or '容差放过: 0' in diff_result.stdout, \
            "严格模式不应有容差放过"
    
    def test_scheme_preserved_in_batch_snapshot(self):
        """测试批次创建时规则快照被正确保存"""
        bill_path = os.path.join(PROJECT_ROOT, 'samples', 'supplier_bill.csv')
        receive_path = os.path.join(PROJECT_ROOT, 'samples', 'receiving_list.csv')
        
        run_cli_command(['scheme', 'create', '-n', 'snapshot_test', '-q', '2.5', '-a', '100.0', '--date-offset', '3'])
        
        run_cli_command(['import', 'bill', '-f', bill_path])
        run_cli_command(['import', 'receiving', '-f', receive_path])
        
        batch_result = run_cli_command([
            'batch', 'create', '-o', 'test_user', '-R', 'reviewer', '-s', 'snapshot_test'
        ])
        assert batch_result.returncode == 0
        
        batch_no = None
        for line in batch_result.stdout.split('\n'):
            if '成功创建批次' in line:
                batch_no = line.split(':')[1].strip()
                break
        
        assert batch_no is not None, "未能获取批次号"
        
        show_result = run_cli_command(['batch', 'show', '-b', batch_no])
        assert 'snapshot_test' in show_result.stdout, "批次应显示方案名称"
        assert '数量容差±2.5' in show_result.stdout, "批次应显示数量容差"
        assert '金额容差±100.0' in show_result.stdout, "批次应显示金额容差"
        assert '日期偏移3天' in show_result.stdout, "批次应显示日期偏移"

class TestImportRecordQuery:
    """导入记录查询测试 - 确保导入记录可查询"""
    
    def test_import_record_created_on_success(self):
        """测试成功导入应创建导入记录"""
        export_path = os.path.join(tempfile.gettempdir(), 'exported_schemes.json')
        
        run_cli_command(['scheme', 'create', '-n', 'export_test', '-q', '1.0', '-a', '50.0'])
        run_cli_command(['scheme', 'export', '-o', export_path])
        
        assert os.path.exists(export_path), "导出文件应存在"
        
        import_result = run_cli_command([
            'scheme', 'import', '-f', export_path, '-c', 'skip', '-o', 'test_operator', '-R', 'admin'
        ])
        assert import_result.returncode == 0
        
        import_list_result = run_cli_command(['audit', 'import-list'])
        assert 'exported_schemes.json' in import_list_result.stdout, "导入记录应包含文件名"
        assert 'OK' in import_list_result.stdout, "状态应为成功"
        
        list_result = run_cli_command(['audit', 'import-list'])
        lines = list_result.stdout.strip().split('\n')
        import_id = None
        for line in lines:
            if 'exported_schemes.json' in line:
                parts = line.split()
                import_id = parts[0]
                break
        
        assert import_id is not None, "未能获取导入记录ID"
        
        detail_result = run_cli_command(['audit', 'import-detail', '-i', import_id])
        assert 'test_operator' in detail_result.stdout, "详情应包含操作人"
        assert 'admin' in detail_result.stdout, "详情应包含角色"
        
        os.remove(export_path)
    
    def test_import_record_details_available(self):
        """测试导入记录详情可查询"""
        temp_file = os.path.join(tempfile.gettempdir(), 'detail_test.json')
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump({
                'schemes': [
                    {'name': 'detail_scheme', 'business_line': '测试业务线', 
                     'description': '测试描述', 'quantity_tolerance': 3.0, 
                     'amount_tolerance': 150.0, 'date_offset_days': 5,
                     'required_fields': ['bill_no'], 'ignored_fields': ['unit_price']}
                ]
            }, f)
        
        import_result = run_cli_command([
            'scheme', 'import', '-f', temp_file, '-c', 'skip', '-o', 'user', '-R', 'reviewer'
        ])
        assert import_result.returncode == 0
        
        list_result = run_cli_command(['audit', 'import-list'])
        lines = list_result.stdout.strip().split('\n')
        
        import_id = None
        for line in lines:
            if 'detail_test.json' in line:
                parts = line.split()
                import_id = parts[0]
                break
        
        assert import_id is not None, "未能获取导入记录ID"
        
        detail_result = run_cli_command(['audit', 'import-detail', '-i', import_id])
        assert 'detail_scheme' in detail_result.stdout, "详情应包含方案名称"
        assert 'user' in detail_result.stdout, "详情应包含操作人"
        assert 'reviewer' in detail_result.stdout, "详情应包含角色"
        assert '3' in detail_result.stdout, "详情应包含数量容差"
        assert '150' in detail_result.stdout, "详情应包含金额容差"
        
        os.remove(temp_file)
    
    def test_import_record_status_success(self):
        """测试成功导入的记录状态应为success"""
        temp_file = os.path.join(tempfile.gettempdir(), 'status_test.json')
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump({
                'schemes': [
                    {'name': 'status_scheme', 'quantity_tolerance': 1.0}
                ]
            }, f)
        
        run_cli_command(['scheme', 'import', '-f', temp_file, '-c', 'skip'])
        
        list_result = run_cli_command(['audit', 'import-list'])
        assert 'OK' in list_result.stdout, "成功导入的状态应为OK"
        
        os.remove(temp_file)
    
    def test_conflict_action_recorded_correctly(self):
        """测试冲突处理方式被正确记录"""
        run_cli_command(['scheme', 'create', '-n', 'conflict_base', '-q', '1.0'])
        
        temp_file = os.path.join(tempfile.gettempdir(), 'conflict_test.json')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump({
                'schemes': [
                    {'name': 'conflict_base', 'quantity_tolerance': 99.0}
                ]
            }, f)
        
        run_cli_command(['scheme', 'import', '-f', temp_file, '-c', 'overwrite'])
        
        list_result = run_cli_command(['audit', 'import-list'])
        assert 'overwrite' in list_result.stdout.lower(), "应记录覆盖操作"
        
        os.remove(temp_file)

class TestCLICommandExamples:
    """CLI命令示例测试 - 验证README中的命令示例可执行"""
    
    def test_readme_scheme_create_example(self):
        """测试README中的方案创建示例"""
        result = run_cli_command(['scheme', 'create', '-n', 'strict', '--description', '严格模式', '-q', '0', '-a', '0'])
        assert result.returncode == 0, f"方案创建失败: {result.stderr}"
        
        result = run_cli_command(['scheme', 'create', '-n', 'loose', '--description', '宽松模式', '-q', '1.0', '-a', '50.0', '--set-active'])
        assert result.returncode == 0, f"方案创建失败: {result.stderr}"
        
        result = run_cli_command(['scheme', 'create', '-n', 'flexible', '-b', '华东区', '--description', '灵活模式', '-q', '2.5', '-a', '100.0', '-r', 'bill_no', '-r', 'item_code', '-i', 'unit_price'])
        assert result.returncode == 0, f"方案创建失败: {result.stderr}"
    
    def test_readme_scheme_list_and_show(self):
        """测试README中的方案列表和详情命令"""
        run_cli_command(['scheme', 'create', '-n', 'list_test', '-q', '0.5'])
        
        list_result = run_cli_command(['scheme', 'list'])
        assert list_result.returncode == 0, f"方案列表失败: {list_result.stderr}"
        assert 'list_test' in list_result.stdout
        
        show_result = run_cli_command(['scheme', 'show', '-n', 'list_test'])
        assert show_result.returncode == 0, f"方案详情失败: {show_result.stderr}"
        assert 'list_test' in show_result.stdout
        assert '数量容差: 0.5' in show_result.stdout
    
    def test_readme_diff_check_examples(self):
        """测试README中的差异检查示例"""
        bill_path = os.path.join(PROJECT_ROOT, 'samples', 'supplier_bill.csv')
        receive_path = os.path.join(PROJECT_ROOT, 'samples', 'receiving_list.csv')
        
        run_cli_command(['scheme', 'create', '-n', 'diff_test', '-q', '1.0', '-a', '50.0'])
        run_cli_command(['scheme', 'switch', '-n', 'diff_test'])
        
        result = run_cli_command(['diff', 'check', '-b', bill_path, '-r', receive_path])
        assert result.returncode == 0, f"差异检查失败: {result.stderr}"
        
        result = run_cli_command(['diff', 'check', '-b', bill_path, '-r', receive_path, '--no-scheme'])
        assert result.returncode == 0, f"无方案差异检查失败: {result.stderr}"
    
    def test_readme_import_export_example(self):
        """测试README中的导入导出示例"""
        output_path = os.path.join(tempfile.gettempdir(), 'test_export.json')
        
        run_cli_command(['scheme', 'create', '-n', 'export_example', '-q', '2.0'])
        
        export_result = run_cli_command(['scheme', 'export', '-o', output_path])
        assert export_result.returncode == 0, f"导出失败: {export_result.stderr}"
        assert os.path.exists(output_path), "导出文件不存在"
        
        import_result = run_cli_command(['scheme', 'import', '-f', output_path, '-c', 'skip'])
        assert import_result.returncode == 0, f"导入失败: {import_result.stderr}"
        
        os.remove(output_path)

class TestBatchAndAppealWorkflow:
    """批次和申诉工作流测试"""
    
    def test_full_workflow_with_scheme(self):
        """测试完整的批次创建和申诉流程"""
        bill_path = os.path.join(PROJECT_ROOT, 'samples', 'supplier_bill.csv')
        receive_path = os.path.join(PROJECT_ROOT, 'samples', 'receiving_list.csv')
        
        run_cli_command(['scheme', 'create', '-n', 'workflow_test', '-q', '0', '-a', '0', '--date-offset', '1'])
        
        batch_result = run_cli_command([
            'batch', 'create', '-b', bill_path, '-r', receive_path, 
            '-o', '张三', '-R', 'reviewer', '-s', 'workflow_test'
        ])
        assert batch_result.returncode == 0, f"创建批次失败: {batch_result.stderr}"
        
        import re
        match = re.search(r'成功创建批次:\s*(BATCH_\d+_\d+)', batch_result.stdout)
        assert match, f"未能从输出中提取批次号: {batch_result.stdout}"
        batch_no = match.group(1)
        
        assert batch_no is not None, "未能获取批次号"
        
        appeal_result = run_cli_command([
            'appeal', 'initiate', '-b', batch_no, '-o', '张三', '-R', 'reviewer', '-n', '测试申诉'
        ])
        assert appeal_result.returncode == 0, f"发起申诉失败: {appeal_result.stderr}"
        
        approve_result = run_cli_command([
            'appeal', 'approve', '-b', batch_no, '-o', '李四', '-R', 'approver', '-n', '同意申诉'
        ])
        assert approve_result.returncode == 0, f"审批失败: {approve_result.stderr}"
        
        appeal_list = run_cli_command(['appeal', 'list', '-b', batch_no])
        assert 'approved' in appeal_list.stdout.lower(), "申诉应显示已审批状态"

class TestRolePermissionValidation:
    """角色权限校验测试"""
    
    def test_missing_role_parameter(self):
        """测试缺少角色参数应报错"""
        bill_path = os.path.join(PROJECT_ROOT, 'samples', 'supplier_bill.csv')
        receive_path = os.path.join(PROJECT_ROOT, 'samples', 'receiving_list.csv')
        
        run_cli_command(['import', 'bill', '-f', bill_path])
        run_cli_command(['import', 'receiving', '-f', receive_path])
        
        batch_result = run_cli_command(['batch', 'create', '-o', 'test_user'])
        assert batch_result.returncode != 0, "缺少角色参数应该失败"
        assert 'role' in batch_result.stderr.lower() or 'required' in batch_result.stderr.lower()
    
    def test_invalid_role(self):
        """测试无效角色应报错"""
        bill_path = os.path.join(PROJECT_ROOT, 'samples', 'supplier_bill.csv')
        receive_path = os.path.join(PROJECT_ROOT, 'samples', 'receiving_list.csv')
        
        run_cli_command(['import', 'bill', '-f', bill_path])
        run_cli_command(['import', 'receiving', '-f', receive_path])
        
        batch_result = run_cli_command(['batch', 'create', '-o', 'test_user', '-R', 'invalid_role'])
        assert '错误' in batch_result.stdout, "无效角色应该输出错误信息"
        assert "无效的角色" in batch_result.stdout
    
    def test_reviewer_cannot_approve(self):
        """测试reviewer角色不能审批"""
        bill_path = os.path.join(PROJECT_ROOT, 'samples', 'supplier_bill.csv')
        receive_path = os.path.join(PROJECT_ROOT, 'samples', 'receiving_list.csv')
        
        run_cli_command(['scheme', 'create', '-n', 'role_test', '-q', '0', '-a', '0', '--date-offset', '1'])
        
        batch_result = run_cli_command([
            'batch', 'create', '-b', bill_path, '-r', receive_path, 
            '-o', '张三', '-R', 'reviewer', '-s', 'role_test'
        ])
        
        import re
        match = re.search(r'成功创建批次:\s*(BATCH_\d+_\d+)', batch_result.stdout)
        assert match, f"未能从输出中提取批次号: {batch_result.stdout}"
        batch_no = match.group(1)
        
        assert batch_no is not None, "未能获取批次号"
        
        run_cli_command(['appeal', 'initiate', '-b', batch_no, '-o', '张三', '-R', 'reviewer', '-n', 'test'])
        
        approve_result = run_cli_command([
            'appeal', 'approve', '-b', batch_no, '-o', '张三', '-R', 'reviewer', '-n', 'test'
        ])
        assert '错误' in approve_result.stdout, "reviewer不应能审批"

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
