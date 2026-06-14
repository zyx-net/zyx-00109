import click
from tabulate import tabulate

from ..storage import get_all_batches, get_diff_items_by_batch
from ..models import AppealStatus

@click.group(name='status')
def status_command():
    pass

@status_command.command(name='batch')
def batch_status():
    batches = get_all_batches()
    
    if not batches:
        click.echo("暂无批次")
        return
    
    table_data = []
    for batch in batches:
        items = get_diff_items_by_batch(batch.id)
        pending = sum(1 for item in items if item.status == AppealStatus.PENDING)
        approved = sum(1 for item in items if item.status == AppealStatus.APPROVED)
        rejected = sum(1 for item in items if item.status == AppealStatus.REJECTED)
        rolled_back = sum(1 for item in items if item.status == AppealStatus.ROLLED_BACK)
        
        table_data.append([
            batch.batch_no,
            batch.status.value,
            len(items),
            pending,
            approved,
            rejected,
            rolled_back,
            batch.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    headers = ['批次编号', '状态', '总差异数', '待申诉', '已审批', '已拒绝', '已回滚', '创建时间']
    click.echo(tabulate(table_data, headers=headers))

@status_command.command(name='item')
@click.option('--batch-no', '-b', required=True, help='批次编号')
def item_status(batch_no):
    from ..storage import get_batch_by_no
    
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    items = get_diff_items_by_batch(batch.id)
    
    if not items:
        click.echo(f"批次 {batch_no} 没有差异记录")
        return
    
    table_data = []
    for item in items:
        table_data.append([
            item.id,
            item.item_code,
            item.item_name,
            item.amount_diff,
            item.status.value,
            item.operator,
            item.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    headers = ['ID', '物料编码', '物料名称', '金额差异', '状态', '操作人', '更新时间']
    click.echo(f"\n批次 {batch_no} 的差异项状态:")
    click.echo(tabulate(table_data, headers=headers, floatfmt='.2f'))