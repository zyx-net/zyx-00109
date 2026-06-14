import click
import os
from tabulate import tabulate

from ..storage import (
    get_batch_by_no, get_diff_items_by_batch, update_diff_item_status,
    get_diff_item, add_audit_log
)
from ..models import AppealStatus, BatchStatus

@click.group(name='rollback')
def rollback_command():
    pass

@rollback_command.command(name='item')
@click.option('--batch-no', '-b', required=True, help='批次编号')
@click.option('--item-id', '-i', type=int, required=True, help='差异项ID')
@click.option('--operator', '-o', required=True, help='操作人')
@click.option('--note', '-n', help='回滚备注')
def rollback_item(batch_no, item_id, operator, note):
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    if batch.status == BatchStatus.COMPLETED:
        click.echo(f"错误: 批次 {batch_no} 已完成，无法回滚")
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
    
    update_diff_item_status(item_id, AppealStatus.ROLLED_BACK, operator, note or '')
    
    add_audit_log(
        batch.id, batch_no, 'ROLLBACK_ITEM', operator,
        target_item_id=item_id,
        note=note or f'回滚差异项 {item_id}'
    )
    
    click.echo(f"成功回滚差异项: {item_id}")

@rollback_command.command(name='batch')
@click.option('--batch-no', '-b', required=True, help='批次编号')
@click.option('--operator', '-o', required=True, help='操作人')
@click.option('--note', '-n', help='回滚备注')
def rollback_batch(batch_no, operator, note):
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    if batch.status == BatchStatus.COMPLETED:
        click.echo(f"错误: 批次 {batch_no} 已完成，无法回滚")
        return
    
    items = get_diff_items_by_batch(batch.id)
    approved_items = [item for item in items if item.status == AppealStatus.APPROVED]
    
    if not approved_items:
        click.echo(f"批次 {batch_no} 没有已审批通过的差异项可回滚")
        return
    
    for item in approved_items:
        update_diff_item_status(item.id, AppealStatus.ROLLED_BACK, operator, note or '')
    
    add_audit_log(
        batch.id, batch_no, 'ROLLBACK_BATCH', operator,
        note=note or f'回滚批次中 {len(approved_items)} 条已审批项'
    )
    
    click.echo(f"成功回滚批次 {batch_no} 中 {len(approved_items)} 条已审批项")

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
    
    click.echo(f"\n批次 {batch_no} 回滚状态:")
    click.echo(f"  总差异项数: {len(items)}")
    click.echo(f"  已审批通过: {len(approved_items)}")
    click.echo(f"  已回滚: {len(rolled_back_items)}")
    
    if rolled_back_items:
        table_data = []
        for item in rolled_back_items:
            table_data.append([
                item.id,
                item.item_code,
                item.item_name,
                item.amount_diff,
                item.operator,
                item.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        headers = ['ID', '物料编码', '物料名称', '金额差异', '操作人', '回滚时间']
        click.echo(f"\n已回滚项列表 ({len(rolled_back_items)} 条):")
        click.echo(tabulate(table_data, headers=headers, floatfmt='.2f'))