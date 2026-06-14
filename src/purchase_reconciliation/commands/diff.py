import click
from tabulate import tabulate

from ..utils import (
    read_supplier_bill, read_receiving_list, validate_supplier_bill_full,
    validate_receiving_list_full
)
from ..storage import get_config
from ..models import DiffItem

@click.group(name='diff')
def diff_command():
    pass

@diff_command.command(name='check')
@click.option('--bill-file', '-b', type=click.Path(exists=True), help='供应商账单文件路径')
@click.option('--receiving-file', '-r', type=click.Path(exists=True), help='收货清单文件路径')
@click.option('--dry-run', '-d', is_flag=True, default=True, help='仅检查不入库')
def check_diff(bill_file, receiving_file, dry_run):
    bill_path = bill_file or get_config('last_bill_file')
    receiving_path = receiving_file or get_config('last_receiving_file')
    
    if not bill_path:
        click.echo("错误: 请提供供应商账单文件或先使用 import bill 命令导入")
        return
    
    if not receiving_path:
        click.echo("错误: 请提供收货清单文件或先使用 import receiving 命令导入")
        return
    
    bill_validation = validate_supplier_bill_full(bill_path)
    receive_validation = validate_receiving_list_full(receiving_path)
    
    all_errors = []
    all_errors.extend(bill_validation.errors)
    all_errors.extend(receive_validation.errors)
    
    if all_errors:
        click.echo(f"\n[DRY-RUN] 验证失败，发现 {len(all_errors)} 个错误:")
        click.echo("-" * 60)
        
        for err in all_errors:
            click.echo(f"  行 {err.row}: [{err.error_type}] {err.field}")
            click.echo(f"    值: '{err.value}'")
            click.echo(f"    原因: {err.message}")
        
        click.echo("-" * 60)
        click.echo("验证未通过，数据不会落库")
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
                supplier_name=supplier_name
            ))
    
    if not diff_items:
        click.echo("检查完成: 未发现差异")
        return
    
    click.echo(f"\n发现 {len(diff_items)} 条差异记录:")
    table_data = []
    for item in diff_items:
        table_data.append([
            item.supplier_code,
            item.item_code,
            item.item_name,
            item.bill_quantity,
            item.receive_quantity,
            item.quantity_diff,
            item.bill_amount,
            item.receive_amount,
            item.amount_diff
        ])
    
    headers = [
        '供应商编码', '物料编码', '物料名称',
        '账单数量', '收货数量', '数量差异',
        '账单金额', '收货金额', '金额差异'
    ]
    
    click.echo(tabulate(table_data, headers=headers, floatfmt='.2f'))
    
    if not dry_run:
        click.echo("\n--dry-run 未启用，但 diff check 命令仅做检查，不入库。")
        click.echo("如需生成批次，请使用 batch create 命令。")