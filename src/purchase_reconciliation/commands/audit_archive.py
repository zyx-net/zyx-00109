import click
import json
import csv
import os
from tabulate import tabulate
from datetime import datetime

from ..storage import (
    get_audit_logs, get_batch_by_no, get_batch_audit_record, get_all_batch_audit_records,
    get_appeal_audit_records_by_batch, get_all_appeal_audit_records,
    get_rollback_audit_records_by_batch, get_all_rollback_audit_records,
    get_export_audit_records_by_batch, get_all_export_audit_records,
    get_scheme_import_record, get_all_scheme_import_records, get_scheme_import_details,
    get_complete_audit_trail, get_diff_items_by_batch,
    save_export_audit_record
)
from ..models import AppealStatus

@click.group(name='audit')
def audit_command():
    pass

@audit_command.command(name='list')
@click.option('--batch-no', '-b', help='批次编号（不指定则显示所有）')
def list_audit(batch_no):
    batch_id = None
    batch = None
    
    if batch_no:
        batch = get_batch_by_no(batch_no)
        if not batch:
            click.echo(f"错误: 批次 {batch_no} 不存在")
            return
        batch_id = batch.id
    
    logs = get_audit_logs(batch_id)
    
    if not logs:
        click.echo("暂无审计日志")
        return
    
    if batch and batch.scheme_snapshot:
        click.echo(f"批次 {batch_no} 规则快照: {batch.get_scheme_snapshot_summary()}")
        click.echo("")
    
    table_data = []
    for log in logs:
        table_data.append([
            log.id,
            log.batch_no,
            log.operation,
            log.operator,
            log.operator_role,
            log.target_item_id or '',
            log.note[:50] + '...' if len(log.note) > 50 else log.note,
            log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else ''
        ])
    
    headers = ['日志ID', '批次编号', '操作类型', '操作人', '角色', '目标项ID', '备注', '操作时间']
    click.echo(tabulate(table_data, headers=headers))

@audit_command.command(name='summary')
def audit_summary():
    logs = get_audit_logs()
    
    if not logs:
        click.echo("暂无审计日志")
        return
    
    operation_counts = {}
    operator_counts = {}
    role_counts = {}
    
    for log in logs:
        operation_counts[log.operation] = operation_counts.get(log.operation, 0) + 1
        operator_counts[log.operator] = operator_counts.get(log.operator, 0) + 1
        if log.operator_role:
            role_counts[log.operator_role] = role_counts.get(log.operator_role, 0) + 1
    
    click.echo("审计日志汇总:")
    click.echo(f"  总操作数: {len(logs)}")
    click.echo("\n  操作类型分布:")
    for op, count in sorted(operation_counts.items()):
        click.echo(f"    {op}: {count}")
    
    click.echo("\n  操作人分布:")
    for operator, count in sorted(operator_counts.items()):
        click.echo(f"    {operator}: {count}")
    
    if role_counts:
        click.echo("\n  角色分布:")
        for role, count in sorted(role_counts.items()):
            click.echo(f"    {role}: {count}")

@audit_command.command(name='batch')
@click.option('--batch-no', '-b', required=True, help='批次编号')
def audit_batch(batch_no):
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    batch_audit = get_batch_audit_record(batch.id)
    
    click.echo(f"\n批次 {batch_no} 审计详情:")
    click.echo("=" * 60)
    
    click.echo(f"\n批次基本信息:")
    click.echo(f"  批次编号: {batch.batch_no}")
    click.echo(f"  状态: {batch.status.value}")
    click.echo(f"  方案: {batch.scheme_name or '(无)'}")
    click.echo(f"  创建时间: {batch.created_at.strftime('%Y-%m-%d %H:%M:%S') if batch.created_at else ''}")
    
    if batch.scheme_snapshot:
        click.echo(f"\n  规则快照:")
        snap = batch.scheme_snapshot
        click.echo(f"    数量容差: {snap.get('quantity_tolerance', 0)}")
        click.echo(f"    金额容差: {snap.get('amount_tolerance', 0)}")
        click.echo(f"    日期偏移: {snap.get('date_offset_days', 0)} 天")
        if snap.get('required_fields'):
            click.echo(f"    必填字段: {', '.join(snap['required_fields'])}")
        if snap.get('ignored_fields'):
            click.echo(f"    忽略字段: {', '.join(snap['ignored_fields'])}")
    
    if batch_audit:
        click.echo(f"\n批次处理审计:")
        click.echo(f"  拦截项数: {batch_audit['intercepted_items']}")
        click.echo(f"  容差放过: {batch_audit['tolerated_items']} ({batch_audit['tolerated_rationale']})")
        click.echo(f"  日期失败: {batch_audit['date_failed_items']} ({batch_audit['date_failed_rationale']})")
        click.echo(f"  操作人: {batch_audit['operator']} ({batch_audit['operator_role']})")

@audit_command.command(name='appeal')
@click.option('--batch-no', '-b', help='批次编号（不指定则显示所有）')
def audit_appeal(batch_no):
    if batch_no:
        batch = get_batch_by_no(batch_no)
        if not batch:
            click.echo(f"错误: 批次 {batch_no} 不存在")
            return
        appeals = get_appeal_audit_records_by_batch(batch.id)
    else:
        appeals = get_all_appeal_audit_records()
    
    if not appeals:
        click.echo("暂无申诉审计记录")
        return
    
    click.echo(f"\n申诉审计记录 ({len(appeals)} 条):")
    click.echo("=" * 80)
    
    table_data = []
    for appeal in appeals:
        table_data.append([
            appeal['id'],
            appeal['batch_no'],
            appeal['item_id'],
            appeal['item_code'],
            appeal['item_name'],
            f"{appeal['amount_diff']:.2f}",
            appeal['action'],
            appeal['decision_rationale'][:30] + '...' if len(appeal['decision_rationale']) > 30 else appeal['decision_rationale'],
            appeal['operator'],
            appeal['created_at'].strftime('%Y-%m-%d %H:%M:%S') if appeal['created_at'] else ''
        ])
    
    headers = ['ID', '批次', '项ID', '物料编码', '物料名称', '金额差异', '操作', '依据', '操作人', '时间']
    click.echo(tabulate(table_data, headers=headers, floatfmt='.2f'))

@audit_command.command(name='rollback')
@click.option('--batch-no', '-b', help='批次编号（不指定则显示所有）')
def audit_rollback(batch_no):
    if batch_no:
        batch = get_batch_by_no(batch_no)
        if not batch:
            click.echo(f"错误: 批次 {batch_no} 不存在")
            return
        rollbacks = get_rollback_audit_records_by_batch(batch.id)
    else:
        rollbacks = get_all_rollback_audit_records()
    
    if not rollbacks:
        click.echo("暂无回滚审计记录")
        return
    
    click.echo(f"\n回滚审计记录 ({len(rollbacks)} 条):")
    click.echo("=" * 80)
    
    table_data = []
    for rb in rollbacks:
        table_data.append([
            rb['id'],
            rb['batch_no'],
            rb['item_id'],
            rb['item_code'],
            rb['item_name'],
            rb['previous_status'],
            'rolled_back',
            rb['rollback_reason'][:30] + '...' if len(rb['rollback_reason']) > 30 else rb['rollback_reason'],
            rb['operator'],
            rb['created_at'].strftime('%Y-%m-%d %H:%M:%S') if rb['created_at'] else ''
        ])
    
    headers = ['ID', '批次', '项ID', '物料编码', '物料名称', '原状态', '新状态', '原因', '操作人', '时间']
    click.echo(tabulate(table_data, headers=headers))

@audit_command.command(name='export-records')
@click.option('--batch-no', '-b', help='批次编号（不指定则显示所有）')
def audit_export(batch_no):
    if batch_no:
        exports = get_export_audit_records_by_batch(batch_no)
    else:
        exports = get_all_export_audit_records()
    
    if not exports:
        click.echo("暂无导出审计记录")
        return
    
    click.echo(f"\n导出审计记录 ({len(exports)} 条):")
    click.echo("=" * 80)
    
    table_data = []
    for exp in exports:
        table_data.append([
            exp['id'],
            exp['export_type'],
            exp['batch_no'] or 'N/A',
            exp['export_file'],
            exp['record_count'],
            exp['export_format'],
            exp['operator'],
            exp['created_at'].strftime('%Y-%m-%d %H:%M:%S') if exp['created_at'] else ''
        ])
    
    headers = ['ID', '类型', '批次', '文件', '记录数', '格式', '操作人', '时间']
    click.echo(tabulate(table_data, headers=headers))

@audit_command.command(name='import-list')
def audit_import_list():
    imports = get_all_scheme_import_records()
    
    if not imports:
        click.echo("暂无方案导入记录")
        return
    
    click.echo(f"\n方案导入记录 ({len(imports)} 条):")
    click.echo("=" * 80)
    
    table_data = []
    for imp in imports:
        status_tag = '✓' if imp['status'] == 'success' else '✗'
        table_data.append([
            imp['id'],
            imp['import_batch_no'],
            imp['file_path'],
            imp['conflict_action'],
            imp['imported_count'],
            imp['skipped_count'],
            imp['overwritten_count'],
            imp['renamed_count'],
            imp['error_count'],
            status_tag,
            imp['created_at'].strftime('%Y-%m-%d %H:%M:%S') if imp['created_at'] else ''
        ])
    
    headers = ['ID', '导入批次', '文件', '冲突策略', '新增', '跳过', '覆盖', '改名', '错误', '状态', '时间']
    click.echo(tabulate(table_data, headers=headers))

@audit_command.command(name='import-detail')
@click.option('--import-id', '-i', type=int, required=True, help='导入记录ID')
def audit_import_detail(import_id):
    record = get_scheme_import_record(import_id)
    
    if not record:
        click.echo(f"错误: 导入记录 {import_id} 不存在")
        return
    
    click.echo(f"\n导入记录 {import_id} 详情:")
    click.echo("=" * 60)
    click.echo(f"  导入批次: {record['import_batch_no']}")
    click.echo(f"  文件路径: {record['file_path']}")
    click.echo(f"  冲突策略: {record['conflict_action']}")
    click.echo(f"  状态: {record['status']}")
    click.echo(f"  操作人: {record['operator']} ({record['operator_role']})")
    click.echo(f"  时间: {record['created_at'].strftime('%Y-%m-%d %H:%M:%S') if record['created_at'] else ''}")
    
    click.echo(f"\n统计:")
    click.echo(f"  新增: {record['imported_count']}")
    click.echo(f"  跳过: {record['skipped_count']}")
    click.echo(f"  覆盖: {record['overwritten_count']}")
    click.echo(f"  改名: {record['renamed_count']}")
    click.echo(f"  错误: {record['error_count']}")
    
    if record['error_message']:
        click.echo(f"\n错误信息:")
        click.echo(f"  {record['error_message']}")
    
    details = get_scheme_import_details(import_id)
    if details:
        click.echo(f"\n导入方案详情:")
        table_data = []
        for detail in details:
            action_tag = {
                'new': '新增',
                'skip': '跳过',
                'overwrite': '覆盖',
                'rename': '改名'
            }.get(detail['action'], detail['action'])
            
            table_data.append([
                detail['id'],
                detail['original_name'],
                detail['final_name'],
                action_tag,
                detail['scheme_snapshot'].get('quantity_tolerance', 0),
                detail['scheme_snapshot'].get('amount_tolerance', 0)
            ])
        
        headers = ['ID', '原始名称', '最终名称', '操作', '数量容差', '金额容差']
        click.echo(tabulate(table_data, headers=headers))

@audit_command.command(name='trail')
@click.option('--batch-no', '-b', required=True, help='批次编号')
def audit_trail(batch_no):
    trail = get_complete_audit_trail(batch_no)
    
    if not trail:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    click.echo(f"\n批次 {batch_no} 完整审计链路:")
    click.echo("=" * 80)
    
    batch_info = trail['batch']
    click.echo(f"\n1. 批次信息:")
    click.echo(f"   批次编号: {batch_info['batch_no']}")
    click.echo(f"   状态: {batch_info['status']}")
    click.echo(f"   方案: {batch_info['scheme_name'] or '(无)'}")
    click.echo(f"   创建时间: {batch_info['created_at']}")
    
    if batch_info.get('scheme_snapshot'):
        snap = batch_info['scheme_snapshot']
        click.echo(f"\n   规则快照:")
        click.echo(f"     数量容差: {snap.get('quantity_tolerance', 0)}")
        click.echo(f"     金额容差: {snap.get('amount_tolerance', 0)}")
        click.echo(f"     日期偏移: {snap.get('date_offset_days', 0)} 天")
    
    batch_audit = trail.get('batch_audit')
    if batch_audit:
        click.echo(f"\n2. 批次处理审计:")
        click.echo(f"   拦截项数: {batch_audit['intercepted_items']}")
        click.echo(f"   容差放过: {batch_audit['tolerated_items']} 条")
        click.echo(f"   日期失败: {batch_audit['date_failed_items']} 条")
    
    appeal_audits = trail.get('appeal_audits', [])
    if appeal_audits:
        click.echo(f"\n3. 申诉审计 ({len(appeal_audits)} 条):")
        for appeal in appeal_audits[:5]:
            action_zh = {'INITIATE': '发起', 'APPROVE': '审批通过', 'REJECT': '拒绝'}.get(appeal['action'], appeal['action'])
            click.echo(f"   - {appeal['item_code']}: {action_zh} | {appeal['operator']} | {appeal['created_at'].strftime('%H:%M:%S') if appeal['created_at'] else ''}")
        if len(appeal_audits) > 5:
            click.echo(f"   ... 还有 {len(appeal_audits) - 5} 条")
    
    rollback_audits = trail.get('rollback_audits', [])
    if rollback_audits:
        click.echo(f"\n4. 回滚审计 ({len(rollback_audits)} 条):")
        for rb in rollback_audits:
            click.echo(f"   - {rb['item_code']}: 回滚 | {rb['operator']} | {rb['created_at'].strftime('%H:%M:%S') if rb['created_at'] else ''}")
    
    export_audits = trail.get('export_audits', [])
    if export_audits:
        click.echo(f"\n5. 导出审计 ({len(export_audits)} 条):")
        for exp in export_audits:
            click.echo(f"   - {exp['export_type']}: {exp['record_count']} 条 | {exp['export_file']}")
    
    audit_logs = trail.get('audit_logs', [])
    if audit_logs:
        click.echo(f"\n6. 操作日志 ({len(audit_logs)} 条):")
        for log in audit_logs[:5]:
            click.echo(f"   - {log['operation']} | {log['operator']} | {log['created_at']}")
        if len(audit_logs) > 5:
            click.echo(f"   ... 还有 {len(audit_logs) - 5} 条")

@audit_command.command(name='reexport')
@click.option('--batch-no', '-b', required=True, help='批次编号')
@click.option('--output', '-o', required=True, type=click.Path(), help='输出文件路径')
@click.option('--format', '-f', type=click.Choice(['json', 'csv', 'full']), default='json', help='导出格式')
def audit_reexport(batch_no, output, format):
    can_write, error_msg = validate_output_path(output)
    if not can_write:
        click.echo(f"错误: {error_msg}")
        return
    
    trail = get_complete_audit_trail(batch_no)
    
    if not trail:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    batch = get_batch_by_no(batch_no)
    items = get_diff_items_by_batch(batch.id) if batch else []
    
    if format == 'json':
        export_data = {
            'batch_info': trail['batch'],
            'batch_audit': trail.get('batch_audit'),
            'appeal_audits': trail.get('appeal_audits', []),
            'rollback_audits': trail.get('rollback_audits', []),
            'export_audits': trail.get('export_audits', []),
            'audit_logs': trail.get('audit_logs', [])
        }
        
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        
        save_export_audit_record(
            export_type='AUDIT_REEXPORT',
            batch_no=batch_no,
            export_file=output,
            record_count=len(trail.get('audit_logs', [])),
            export_format='json',
            rule_snapshot=batch.scheme_snapshot if batch else None,
            note='审计链路重导出'
        )
        
        click.echo(f"成功导出审计链路到: {output}")
        click.echo(f"导出格式: JSON")
        
    elif format == 'csv':
        with open(output, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                '批次编号', '项ID', '物料编码', '物料名称', '数量差异', '金额差异',
                '申诉状态', '申诉操作', '决定依据', '操作人', '角色', '时间'
            ])
            
            for appeal in trail.get('appeal_audits', []):
                writer.writerow([
                    appeal['batch_no'],
                    appeal['item_id'],
                    appeal['item_code'],
                    appeal['item_name'],
                    appeal['quantity_diff'],
                    appeal['amount_diff'],
                    appeal['original_status'],
                    appeal['action'],
                    appeal['decision_rationale'],
                    appeal['operator'],
                    appeal['operator_role'],
                    appeal['created_at'].strftime('%Y-%m-%d %H:%M:%S') if appeal['created_at'] else ''
                ])
        
        save_export_audit_record(
            export_type='AUDIT_REEXPORT',
            batch_no=batch_no,
            export_file=output,
            record_count=len(trail.get('appeal_audits', [])),
            export_format='csv',
            rule_snapshot=batch.scheme_snapshot if batch else None,
            note='审计链路重导出(CSV)'
        )
        
        click.echo(f"成功导出审计链路到: {output}")
        click.echo(f"导出格式: CSV")
        
    else:
        full_export = {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'batch': trail['batch'],
            'diff_items': [
                {
                    'id': item.id,
                    'item_code': item.item_code,
                    'item_name': item.item_name,
                    'bill_quantity': item.bill_quantity,
                    'receive_quantity': item.receive_quantity,
                    'quantity_diff': item.quantity_diff,
                    'bill_amount': item.bill_amount,
                    'receive_amount': item.receive_amount,
                    'amount_diff': item.amount_diff,
                    'status': item.status.value,
                    'appeal_note': item.appeal_note,
                    'operator': item.operator,
                    'operator_role': item.operator_role
                } for item in items
            ],
            'batch_audit': trail.get('batch_audit'),
            'appeal_audits': trail.get('appeal_audits', []),
            'rollback_audits': trail.get('rollback_audits', []),
            'export_audits': trail.get('export_audits', []),
            'audit_logs': trail.get('audit_logs', [])
        }
        
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(full_export, f, ensure_ascii=False, indent=2, default=str)
        
        save_export_audit_record(
            export_type='AUDIT_REEXPORT_FULL',
            batch_no=batch_no,
            export_file=output,
            record_count=len(items),
            export_format='full_json',
            rule_snapshot=batch.scheme_snapshot if batch else None,
            note='完整审计链路重导出(含差异项)'
        )
        
        click.echo(f"成功导出完整审计链路到: {output}")
        click.echo(f"导出格式: 完整JSON(含差异项详情)")

def validate_output_path(path):
    if not path:
        return False, "路径不能为空"
    
    path_dir = path.rsplit('/', 1)[0] if '/' in path else path.rsplit('\\', 1)[0] if '\\' in path else '.'
    
    if not path_dir or path_dir == path:
        path_dir = '.'
    
    if not os.path.exists(path_dir):
        try:
            os.makedirs(path_dir, exist_ok=True)
        except Exception as e:
            return False, f"无法创建目录 {path_dir}: {str(e)}"
    
    if os.path.exists(path):
        if os.path.isdir(path):
            return False, f"目标路径是目录而非文件: {path}"
        return False, f"目标文件已存在: {path}"
    
    return True, ""
