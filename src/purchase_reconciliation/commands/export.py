import click
import os
import csv

from ..storage import get_batch_by_no, get_diff_items_by_batch, get_all_batches, get_audit_logs
from ..models import AppealStatus
from ..utils import validate_path_conflict

@click.group(name='export')
def export_command():
    pass

@export_command.command(name='result')
@click.option('--batch-no', '-b', required=True, help='批次编号')
@click.option('--output', '-o', required=True, type=click.Path(), help='输出文件路径')
def export_result(batch_no, output):
    can_write, error_msg = validate_path_conflict(output)
    if not can_write:
        click.echo(f"错误: {error_msg}")
        return
    
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    items = get_diff_items_by_batch(batch.id)
    
    with open(output, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            '差异项ID', '账单编号', '收货编号', '物料编码', '物料名称',
            '供应商编码', '供应商名称', '账单数量', '收货数量', '数量差异',
            '账单金额', '收货金额', '金额差异', '申诉状态', '操作人', '角色', '备注', '更新时间'
        ])
        
        for item in items:
            writer.writerow([
                item.id,
                item.bill_no,
                item.receive_no,
                item.item_code,
                item.item_name,
                item.supplier_code,
                item.supplier_name,
                item.bill_quantity,
                item.receive_quantity,
                item.quantity_diff,
                item.bill_amount,
                item.receive_amount,
                item.amount_diff,
                item.status.value,
                item.operator,
                item.operator_role,
                item.appeal_note,
                item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if item.updated_at else ''
            ])
    
    click.echo(f"成功导出结果到: {output}")

@export_command.command(name='summary')
@click.option('--output', '-o', required=True, type=click.Path(), help='输出文件路径')
def export_summary(output):
    can_write, error_msg = validate_path_conflict(output)
    if not can_write:
        click.echo(f"错误: {error_msg}")
        return
    
    batches = get_all_batches()
    
    with open(output, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            '批次编号', '批次状态', '差异项总数', '待申诉', '已审批', '已拒绝', '已回滚',
            '创建时间', '锁定人', '锁定时间'
        ])
        
        for batch in batches:
            items = get_diff_items_by_batch(batch.id)
            pending = sum(1 for item in items if item.status == AppealStatus.PENDING)
            approved = sum(1 for item in items if item.status == AppealStatus.APPROVED)
            rejected = sum(1 for item in items if item.status == AppealStatus.REJECTED)
            rolled_back = sum(1 for item in items if item.status == AppealStatus.ROLLED_BACK)
            
            writer.writerow([
                batch.batch_no,
                batch.status.value,
                len(items),
                pending,
                approved,
                rejected,
                rolled_back,
                batch.created_at.strftime('%Y-%m-%d %H:%M:%S') if batch.created_at else '',
                batch.locked_by or '',
                batch.lock_time.strftime('%Y-%m-%d %H:%M:%S') if batch.lock_time else ''
            ])
    
    click.echo(f"成功导出汇总到: {output}")

@export_command.command(name='audit')
@click.option('--batch-no', '-b', help='批次编号（不指定则导出所有）')
@click.option('--output', '-o', required=True, type=click.Path(), help='输出文件路径')
def export_audit(batch_no, output):
    can_write, error_msg = validate_path_conflict(output)
    if not can_write:
        click.echo(f"错误: {error_msg}")
        return
    
    batch = None
    batch_id = None
    
    if batch_no:
        batch = get_batch_by_no(batch_no)
        if not batch:
            click.echo(f"错误: 批次 {batch_no} 不存在")
            return
        batch_id = batch.id
    
    logs = get_audit_logs(batch_id)
    
    with open(output, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            '日志ID', '批次编号', '操作类型', '操作人', '角色', '目标项ID', '备注', '操作时间'
        ])
        
        for log in logs:
            writer.writerow([
                log.id,
                log.batch_no,
                log.operation,
                log.operator,
                log.operator_role,
                log.target_item_id or '',
                log.note,
                log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else ''
            ])
    
    click.echo(f"成功导出审计日志到: {output}")