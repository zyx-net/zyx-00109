import click
from datetime import datetime

from ..utils import read_supplier_bill, read_receiving_list, generate_batch_no
from ..storage import (
    get_config, save_batch, save_diff_items, get_batch_by_no, get_all_batches,
    get_diff_items_by_batch, add_audit_log, update_diff_item_status
)
from ..models import DiffItem, Batch, BatchStatus, AppealStatus
from tabulate import tabulate

@click.group(name='batch')
def batch_command():
    pass

@batch_command.command(name='create')
@click.option('--bill-file', '-b', type=click.Path(exists=True), help='供应商账单文件路径')
@click.option('--receiving-file', '-r', type=click.Path(exists=True), help='收货清单文件路径')
@click.option('--dry-run', '-d', is_flag=True, default=False, help='仅检查不入库')
@click.option('--operator', '-o', required=True, help='操作人')
def create_batch(bill_file, receiving_file, dry_run, operator):
    bill_path = bill_file or get_config('last_bill_file')
    receiving_path = receiving_file or get_config('last_receiving_file')
    
    if not bill_path:
        click.echo("错误: 请提供供应商账单文件或先使用 import bill 命令导入")
        return
    
    if not receiving_path:
        click.echo("错误: 请提供收货清单文件或先使用 import receiving 命令导入")
        return
    
    try:
        bill_items = read_supplier_bill(bill_path)
        receive_items = read_receiving_list(receiving_path)
    except Exception as e:
        click.echo(f"错误: 读取文件失败 - {str(e)}")
        return
    
    bill_dict = {}
    for item in bill_items:
        key = (item.supplier_code, item.item_code)
        if key not in bill_dict:
            bill_dict[key] = []
        bill_dict[key].append(item)
    
    receive_dict = {}
    for item in receive_items:
        key = (item.supplier_code, item.item_code)
        if key not in receive_dict:
            receive_dict[key] = []
        receive_dict[key].append(item)
    
    all_keys = set(bill_dict.keys()) | set(receive_dict.keys())
    diff_items = []
    
    for key in all_keys:
        bill_list = bill_dict.get(key, [])
        receive_list = receive_dict.get(key, [])
        
        bill_qty = sum(item.quantity for item in bill_list)
        receive_qty = sum(item.quantity for item in receive_list)
        bill_amt = sum(item.amount for item in bill_list)
        receive_amt = sum(item.amount for item in receive_list)
        
        if bill_qty != receive_qty or bill_amt != receive_amt:
            supplier_code, item_code = key
            bill_no = bill_list[0].bill_no if bill_list else ''
            receive_no = receive_list[0].receive_no if receive_list else ''
            item_name = bill_list[0].item_name if bill_list else (receive_list[0].item_name if receive_list else '')
            supplier_name = bill_list[0].supplier_name if bill_list else (receive_list[0].supplier_name if receive_list else '')
            
            diff_items.append(DiffItem(
                bill_no=bill_no,
                receive_no=receive_no,
                item_code=item_code,
                item_name=item_name,
                bill_quantity=bill_qty,
                receive_quantity=receive_qty,
                quantity_diff=bill_qty - receive_qty,
                bill_amount=bill_amt,
                receive_amount=receive_amt,
                amount_diff=bill_amt - receive_amt,
                supplier_code=supplier_code,
                supplier_name=supplier_name,
                operator=operator
            ))
    
    if not diff_items:
        click.echo("检查完成: 未发现差异，无需创建批次")
        return
    
    if dry_run:
        click.echo(f"\n[DRY-RUN] 发现 {len(diff_items)} 条差异记录，未创建批次")
        table_data = []
        for item in diff_items:
            table_data.append([
                item.supplier_code, item.item_code, item.item_name,
                item.bill_quantity, item.receive_quantity, item.quantity_diff,
                item.bill_amount, item.receive_amount, item.amount_diff
            ])
        
        headers = [
            '供应商编码', '物料编码', '物料名称',
            '账单数量', '收货数量', '数量差异',
            '账单金额', '收货金额', '金额差异'
        ]
        click.echo(tabulate(table_data, headers=headers, floatfmt='.2f'))
        return
    
    batch_no = generate_batch_no()
    batch = Batch(batch_no=batch_no, status=BatchStatus.OPEN)
    batch_id = save_batch(batch)
    
    save_diff_items(diff_items, batch_id)
    
    add_audit_log(batch_id, batch_no, 'CREATE_BATCH', operator, note=f'创建批次，包含 {len(diff_items)} 条差异')
    
    click.echo(f"成功创建批次: {batch_no}")
    click.echo(f"批次ID: {batch_id}")
    click.echo(f"差异记录数: {len(diff_items)}")

@batch_command.command(name='list')
def list_batches():
    batches = get_all_batches()
    
    if not batches:
        click.echo("暂无批次")
        return
    
    table_data = []
    for batch in batches:
        table_data.append([
            batch.batch_no,
            batch.status.value,
            batch.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            batch.locked_by or '',
            batch.lock_time.strftime('%Y-%m-%d %H:%M:%S') if batch.lock_time else ''
        ])
    
    headers = ['批次编号', '状态', '创建时间', '锁定人', '锁定时间']
    click.echo(tabulate(table_data, headers=headers))

@batch_command.command(name='lock')
@click.option('--batch-no', '-b', required=True, help='批次编号')
@click.option('--operator', '-o', required=True, help='操作人')
def lock_batch(batch_no, operator):
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    if batch.status == BatchStatus.LOCKED:
        click.echo(f"错误: 批次 {batch_no} 已被锁定")
        return
    
    if batch.status == BatchStatus.COMPLETED:
        click.echo(f"错误: 批次 {batch_no} 已完成")
        return
    
    batch.status = BatchStatus.LOCKED
    batch.locked_by = operator
    batch.lock_time = datetime.now()
    save_batch(batch)
    
    add_audit_log(batch.id, batch_no, 'LOCK_BATCH', operator, note='锁定批次')
    
    click.echo(f"成功锁定批次: {batch_no}")

@batch_command.command(name='unlock')
@click.option('--batch-no', '-b', required=True, help='批次编号')
@click.option('--operator', '-o', required=True, help='操作人')
def unlock_batch(batch_no, operator):
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    if batch.status != BatchStatus.LOCKED:
        click.echo(f"错误: 批次 {batch_no} 未被锁定")
        return
    
    batch.status = BatchStatus.OPEN
    batch.locked_by = None
    batch.lock_time = None
    save_batch(batch)
    
    add_audit_log(batch.id, batch_no, 'UNLOCK_BATCH', operator, note='解锁批次')
    
    click.echo(f"成功解锁批次: {batch_no}")

@batch_command.command(name='show')
@click.option('--batch-no', '-b', required=True, help='批次编号')
def show_batch(batch_no):
    batch = get_batch_by_no(batch_no)
    
    if not batch:
        click.echo(f"错误: 批次 {batch_no} 不存在")
        return
    
    click.echo(f"\n批次信息:")
    click.echo(f"  批次编号: {batch.batch_no}")
    click.echo(f"  状态: {batch.status.value}")
    click.echo(f"  创建时间: {batch.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    click.echo(f"  锁定人: {batch.locked_by or '无'}")
    click.echo(f"  锁定时间: {batch.lock_time.strftime('%Y-%m-%d %H:%M:%S') if batch.lock_time else '无'}")
    
    items = get_diff_items_by_batch(batch.id)
    
    if not items:
        click.echo("\n无差异记录")
        return
    
    table_data = []
    for item in items:
        table_data.append([
            item.id,
            item.item_code,
            item.item_name,
            item.bill_quantity,
            item.receive_quantity,
            item.quantity_diff,
            item.amount_diff,
            item.status.value,
            item.appeal_note[:30] + '...' if len(item.appeal_note) > 30 else item.appeal_note,
            item.operator
        ])
    
    headers = ['ID', '物料编码', '物料名称', '账单数量', '收货数量', '数量差异', '金额差异', '状态', '备注', '操作人']
    click.echo(f"\n差异记录 ({len(items)} 条):")
    click.echo(tabulate(table_data, headers=headers, floatfmt='.2f'))