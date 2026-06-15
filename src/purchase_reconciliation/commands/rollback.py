import click
import os
from tabulate import tabulate

from ..storage import (
    get_batch_by_no, get_diff_items_by_batch, update_diff_item_status,
    get_diff_item, add_audit_log, is_batch_rollback_conflict, has_pending_items,
    save_rollback_audit_record, get_appeal_audit_records_by_batch
)
from ..models import AppealStatus, BatchStatus, OperatorRole

@click.group(name='rollback')
def rollback_command():
    pass

def validate_admin_role(role: str, operation: str) -> bool:
    if not role:
        click.echo(f"错误: 缺少必要参数 --role/-R")
        click.echo(f"操作 '{operation}' 需要指定操作者角色 (admin)")
        click.echo(f"有效角色: {[r.value for r in OperatorRole]}")
        return False
    
    if not OperatorRole.is_valid(role):
        click.echo(f"错误: 无效的角色 '{role}'")
        click.echo(f"有效角色: {[r.value for r in OperatorRole]}")
        return False
    
    if not OperatorRole.can_rollback(role):
        click.echo(f"错误: 角色 '{role}' 没有回滚权限")
        click.echo(f"需要角色: admin")
        return False
    
    return True

def check_rollback_conflicts(batch_id: int, batch_no: str) -> tuple[bool, str]:
    if is_batch_rollback_conflict(batch_id):
        return True, f"批次 {batch_no} 中存在已回滚的差异项，无法重复回滚"
    
    if has_pending_items(batch_id):
        return True, f"批次 {batch_no} 中存在待处理的差异项，请先完成审批"
    
    return False, ""

@rollback_command.command(name='item')
@click.option('--batch-no', '-b', required=True, help='批次编号')
@click.option('--item-id', '-i', type=int, required=True, help='差异项ID')
@click.option('--operator', '-o', required=True, help='操作人')
@click.option('--role', '-R', required=True, help='操作者角色 (admin)')
@click.option('--note', '-n', help='回滚备注')
def rollback_item(batch_no, item_id, operator, role, note):
    if not validate_admin_role(role, '回滚差异项'):
        return
    
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    if batch.status == BatchStatus.COMPLETED:
        click.echo(f"错误: 批次 {batch_no} 已完成，无法回滚")
        return
    
    has_conflict, conflict_msg = check_rollback_conflicts(batch.id, batch_no)
    if has_conflict:
        click.echo(f"错误: {conflict_msg}")
        return
    
    item = get_diff_item(item_id)
    
    if not item:
        click.echo(f"错误: 差异项 {item_id} 不存在")
        return
    
    if item.batch_id != batch.id:
        click.echo(f"错误: 差异项 {item_id} 不属于批次 {batch_no}")
        return
    
    if item.status != AppealStatus.APPROVED:
        click.echo(f"错误: 差异项 {item_id} 当前状态为 {item.status.value}，只有已审批通过的项才能回滚")
        return
    
    previous_status = item.status.value
    
    appeal_audits = get_appeal_audit_records_by_batch(batch.id)
    related_appeal = next((a for a in appeal_audits if a['item_id'] == item_id and a['action'] == 'APPROVE'), None)
    
    update_diff_item_status(item_id, AppealStatus.ROLLED_BACK, operator, role, note or '')
    
    save_rollback_audit_record(
        batch_id=batch.id,
        batch_no=batch_no,
        item_id=item_id,
        item_code=item.item_code,
        item_name=item.item_name,
        rollback_reason=note or '',
        previous_status=previous_status,
        rule_snapshot=batch.scheme_snapshot,
        appeal_audit_id=related_appeal['id'] if related_appeal else None,
        operator=operator,
        operator_role=role
    )
    
    add_audit_log(
        batch.id, batch_no, 'ROLLBACK_ITEM', operator, role,
        target_item_id=item_id,
        note=note or f'回滚差异项 {item_id}'
    )
    
    click.echo(f"成功回滚差异项: {item_id}")
    click.echo(f"操作人: {operator} | 角色: {role}")
    click.echo(f"回滚记录已固化到审计归档")

@rollback_command.command(name='batch')
@click.option('--batch-no', '-b', required=True, help='批次编号')
@click.option('--operator', '-o', required=True, help='操作人')
@click.option('--role', '-R', required=True, help='操作者角色 (admin)')
@click.option('--note', '-n', help='回滚备注')
def rollback_batch(batch_no, operator, role, note):
    if not validate_admin_role(role, '回滚批次'):
        return
    
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    if batch.status == BatchStatus.COMPLETED:
        click.echo(f"错误: 批次 {batch_no} 已完成，无法回滚")
        return
    
    has_conflict, conflict_msg = check_rollback_conflicts(batch.id, batch_no)
    if has_conflict:
        click.echo(f"错误: {conflict_msg}")
        return
    
    items = get_diff_items_by_batch(batch.id)
    approved_items = [item for item in items if item.status == AppealStatus.APPROVED]
    
    if not approved_items:
        click.echo(f"批次 {batch_no} 没有已审批通过的差异项可回滚")
        return
    
    appeal_audits = get_appeal_audit_records_by_batch(batch.id)
    
    for item in approved_items:
        previous_status = item.status.value
        related_appeal = next((a for a in appeal_audits if a['item_id'] == item.id and a['action'] == 'APPROVE'), None)
        
        update_diff_item_status(item.id, AppealStatus.ROLLED_BACK, operator, role, note or '')
        
        save_rollback_audit_record(
            batch_id=batch.id,
            batch_no=batch_no,
            item_id=item.id,
            item_code=item.item_code,
            item_name=item.item_name,
            rollback_reason=note or '',
            previous_status=previous_status,
            rule_snapshot=batch.scheme_snapshot,
            appeal_audit_id=related_appeal['id'] if related_appeal else None,
            operator=operator,
            operator_role=role
        )
    
    add_audit_log(
        batch.id, batch_no, 'ROLLBACK_BATCH', operator, role,
        note=note or f'回滚批次中 {len(approved_items)} 条已审批项'
    )
    
    click.echo(f"成功回滚批次 {batch_no} 中 {len(approved_items)} 条已审批项")
    click.echo(f"操作人: {operator} | 角色: {role}")
    click.echo(f"回滚记录已固化到审计归档")

@rollback_command.command(name='check')
@click.option('--batch-no', '-b', required=True, help='批次编号')
def check_rollback_status(batch_no):
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    items = get_diff_items_by_batch(batch.id)
    
    rolled_back_items = [item for item in items if item.status == AppealStatus.ROLLED_BACK]
    approved_items = [item for item in items if item.status == AppealStatus.APPROVED]
    pending_items = [item for item in items if item.status == AppealStatus.PENDING]
    
    click.echo(f"\n批次 {batch_no} 回滚状态检查:")
    click.echo(f"  总差异项数: {len(items)}")
    click.echo(f"  待处理: {len(pending_items)}")
    click.echo(f"  已审批通过: {len(approved_items)}")
    click.echo(f"  已回滚: {len(rolled_back_items)}")
    
    has_conflict, conflict_msg = check_rollback_conflicts(batch.id, batch_no)
    if has_conflict:
        click.echo(f"\n  [!] 回滚冲突: {conflict_msg}")
    else:
        click.echo(f"\n  [OK] 可以执行回滚操作")
    
    if rolled_back_items:
        table_data = []
        for item in rolled_back_items:
            table_data.append([
                item.id,
                item.item_code,
                item.item_name,
                item.amount_diff,
                item.operator,
                item.operator_role,
                item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if item.updated_at else ''
            ])
        
        headers = ['ID', '物料编码', '物料名称', '金额差异', '操作人', '角色', '回滚时间']
        click.echo(f"\n已回滚项列表 ({len(rolled_back_items)} 条):")
        click.echo(tabulate(table_data, headers=headers, floatfmt='.2f'))