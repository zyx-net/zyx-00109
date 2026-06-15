import click
from tabulate import tabulate

from ..storage import (
    get_batch_by_no, get_diff_items_by_batch, update_diff_item_status,
    get_diff_item, add_audit_log, save_appeal_audit_record, get_batch_audit_record
)
from ..models import AppealStatus, BatchStatus, OperatorRole

@click.group(name='appeal')
def appeal_command():
    pass

def validate_role(role: str, required_capability: str) -> bool:
    if not role:
        click.echo(f"错误: 缺少必要参数 --role/-R")
        click.echo(f"操作 '{required_capability}' 需要指定操作者角色 (reviewer/approver/admin)")
        click.echo(f"有效角色: {[r.value for r in OperatorRole]}")
        return False
    
    if not OperatorRole.is_valid(role):
        click.echo(f"错误: 无效的角色 '{role}'")
        click.echo(f"有效角色: {[r.value for r in OperatorRole]}")
        return False
    
    return True

@appeal_command.command(name='initiate')
@click.option('--batch-no', '-b', required=True, help='批次编号')
@click.option('--operator', '-o', required=True, help='操作人')
@click.option('--role', '-R', required=True, help='操作者角色 (reviewer/approver/admin)')
@click.option('--item-id', '-i', type=int, help='差异项ID（不指定则对所有pending项发起申诉）')
@click.option('--note', '-n', help='申诉备注')
def initiate_appeal(batch_no, operator, role, item_id, note):
    if not validate_role(role, '发起申诉'):
        return
    
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    if batch.status == BatchStatus.LOCKED:
        click.echo(f"错误: 批次 {batch_no} 已被锁定，无法发起申诉")
        return
    
    if batch.status == BatchStatus.COMPLETED:
        click.echo(f"错误: 批次 {batch_no} 已完成")
        return
    
    if item_id:
        item = get_diff_item(item_id)
        if not item:
            click.echo(f"错误: 差异项 {item_id} 不存在")
            return
        if item.batch_id != batch.id:
            click.echo(f"错误: 差异项 {item_id} 不属于批次 {batch_no}")
            return
        if item.status != AppealStatus.PENDING:
            click.echo(f"错误: 差异项 {item_id} 当前状态为 {item.status.value}，无法发起申诉")
            return
        
        items_to_appeal = [item]
    else:
        items = get_diff_items_by_batch(batch.id)
        items_to_appeal = [item for item in items if item.status == AppealStatus.PENDING]
        
        if not items_to_appeal:
            click.echo(f"批次 {batch_no} 没有待申诉的差异项")
            return
    
    for item in items_to_appeal:
        update_diff_item_status(item.id, AppealStatus.PENDING, operator, role, note or '')
        
        save_appeal_audit_record(
            batch_id=batch.id,
            batch_no=batch_no,
            item_id=item.id,
            item_code=item.item_code,
            item_name=item.item_name,
            quantity_diff=item.quantity_diff,
            amount_diff=item.amount_diff,
            original_status=item.status.value,
            action='INITIATE',
            decision_rationale=note or f'发起申诉: {item.appeal_note}',
            rule_snapshot=batch.scheme_snapshot,
            operator=operator,
            operator_role=role
        )
    
    add_audit_log(
        batch.id, batch_no, 'INITIATE_APPEAL', operator, role,
        target_item_id=item_id,
        note=note or f'对 {len(items_to_appeal)} 条差异项发起申诉'
    )
    
    click.echo(f"成功对 {len(items_to_appeal)} 条差异项发起申诉")
    click.echo(f"操作人: {operator} | 角色: {role}")
    click.echo(f"申诉记录已固化到审计归档")

@appeal_command.command(name='approve')
@click.option('--batch-no', '-b', required=True, help='批次编号')
@click.option('--operator', '-o', required=True, help='操作人')
@click.option('--role', '-R', required=True, help='操作者角色 (approver/admin)')
@click.option('--item-id', '-i', type=int, help='差异项ID（不指定则审批所有pending项）')
@click.option('--note', '-n', help='审批备注')
def approve_appeal(batch_no, operator, role, item_id, note):
    if not validate_role(role, '审批通过'):
        return
    
    if not OperatorRole.can_approve(role):
        click.echo(f"错误: 角色 '{role}' 没有审批通过的权限")
        click.echo(f"需要角色: approver 或 admin")
        return
    
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    if batch.status == BatchStatus.COMPLETED:
        click.echo(f"错误: 批次 {batch_no} 已完成")
        return
    
    if item_id:
        item = get_diff_item(item_id)
        if not item:
            click.echo(f"错误: 差异项 {item_id} 不存在")
            return
        if item.batch_id != batch.id:
            click.echo(f"错误: 差异项 {item_id} 不属于批次 {batch_no}")
            return
        if item.status == AppealStatus.ROLLED_BACK:
            click.echo(f"错误: 差异项 {item_id} 已回滚，无法审批")
            return
        if item.status == AppealStatus.APPROVED:
            click.echo(f"警告: 差异项 {item_id} 已审批通过")
            return
        
        items_to_approve = [item]
    else:
        items = get_diff_items_by_batch(batch.id)
        items_to_approve = [item for item in items if item.status == AppealStatus.PENDING]
        
        if not items_to_approve:
            click.echo(f"批次 {batch_no} 没有待审批的差异项")
            return
    
    approved_count = 0
    for item in items_to_approve:
        if item.status == AppealStatus.ROLLED_BACK:
            click.echo(f"跳过: 差异项 {item.id} 已回滚，无法审批")
            continue
        update_diff_item_status(item.id, AppealStatus.APPROVED, operator, role, note or '')
        
        save_appeal_audit_record(
            batch_id=batch.id,
            batch_no=batch_no,
            item_id=item.id,
            item_code=item.item_code,
            item_name=item.item_name,
            quantity_diff=item.quantity_diff,
            amount_diff=item.amount_diff,
            original_status=item.status.value,
            action='APPROVE',
            decision_rationale=note or '审批通过',
            rule_snapshot=batch.scheme_snapshot,
            operator=operator,
            operator_role=role
        )
        approved_count += 1
    
    add_audit_log(
        batch.id, batch_no, 'APPROVE_APPEAL', operator, role,
        target_item_id=item_id,
        note=note or f'审批通过 {approved_count} 条差异项'
    )
    
    click.echo(f"成功审批通过 {approved_count} 条差异项")
    click.echo(f"操作人: {operator} | 角色: {role}")
    click.echo(f"审批记录已固化到审计归档")

@appeal_command.command(name='reject')
@click.option('--batch-no', '-b', required=True, help='批次编号')
@click.option('--operator', '-o', required=True, help='操作人')
@click.option('--role', '-R', required=True, help='操作者角色 (approver/admin)')
@click.option('--item-id', '-i', type=int, help='差异项ID（不指定则拒绝所有pending项）')
@click.option('--note', '-n', help='拒绝备注')
def reject_appeal(batch_no, operator, role, item_id, note):
    if not validate_role(role, '拒绝申诉'):
        return
    
    if not OperatorRole.can_reject(role):
        click.echo(f"错误: 角色 '{role}' 没有拒绝申诉的权限")
        click.echo(f"需要角色: approver 或 admin")
        return
    
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    if batch.status == BatchStatus.COMPLETED:
        click.echo(f"错误: 批次 {batch_no} 已完成")
        return
    
    if item_id:
        item = get_diff_item(item_id)
        if not item:
            click.echo(f"错误: 差异项 {item_id} 不存在")
            return
        if item.batch_id != batch.id:
            click.echo(f"错误: 差异项 {item_id} 不属于批次 {batch_no}")
            return
        
        items_to_reject = [item]
    else:
        items = get_diff_items_by_batch(batch.id)
        items_to_reject = [item for item in items if item.status == AppealStatus.PENDING]
        
        if not items_to_reject:
            click.echo(f"批次 {batch_no} 没有待审批的差异项")
            return
    
    for item in items_to_reject:
        update_diff_item_status(item.id, AppealStatus.REJECTED, operator, role, note or '')
        
        save_appeal_audit_record(
            batch_id=batch.id,
            batch_no=batch_no,
            item_id=item.id,
            item_code=item.item_code,
            item_name=item.item_name,
            quantity_diff=item.quantity_diff,
            amount_diff=item.amount_diff,
            original_status=item.status.value,
            action='REJECT',
            decision_rationale=note or '拒绝申诉',
            rule_snapshot=batch.scheme_snapshot,
            operator=operator,
            operator_role=role
        )
    
    add_audit_log(
        batch.id, batch_no, 'REJECT_APPEAL', operator, role,
        target_item_id=item_id,
        note=note or f'拒绝 {len(items_to_reject)} 条差异项'
    )
    
    click.echo(f"成功拒绝 {len(items_to_reject)} 条差异项")
    click.echo(f"操作人: {operator} | 角色: {role}")
    click.echo(f"拒绝记录已固化到审计归档")

@appeal_command.command(name='list')
@click.option('--batch-no', '-b', required=True, help='批次编号')
def list_appeals(batch_no):
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    items = get_diff_items_by_batch(batch.id)
    
    if not items:
        click.echo(f"批次 {batch_no} 没有差异记录")
        return
    
    if batch.scheme_snapshot:
        click.echo(f"\n批次 {batch_no} 规则快照: {batch.get_scheme_snapshot_summary()}")
    
    table_data = []
    for item in items:
        table_data.append([
            item.id,
            item.item_code,
            item.item_name,
            item.quantity_diff,
            item.amount_diff,
            item.status.value,
            item.appeal_note[:30] + '...' if len(item.appeal_note) > 30 else item.appeal_note,
            item.operator,
            item.operator_role,
            item.updated_at.strftime('%Y-%m-%d %H:%M:%S') if item.updated_at else ''
        ])
    
    headers = ['ID', '物料编码', '物料名称', '数量差异', '金额差异', '状态', '备注', '操作人', '角色', '更新时间']
    click.echo(f"\n申诉列表 ({len(items)} 条):")
    click.echo(tabulate(table_data, headers=headers, floatfmt='.2f'))