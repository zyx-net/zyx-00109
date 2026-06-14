import click
import os

from ..utils import read_supplier_bill, read_receiving_list, validate_csv_structure
from ..storage import save_config, get_config

BILL_REQUIRED_FIELDS = [
    'bill_no', 'item_code', 'item_name', 'quantity', 
    'unit_price', 'amount', 'bill_date', 'supplier_code', 'supplier_name'
]

RECEIVE_REQUIRED_FIELDS = [
    'receive_no', 'item_code', 'item_name', 'quantity',
    'unit_price', 'amount', 'receive_date', 'supplier_code',
    'supplier_name', 'purchase_order_no'
]

@click.group(name='import')
def import_command():
    pass

@import_command.command(name='bill')
@click.option('--file', '-f', required=True, type=click.Path(exists=True), help='供应商账单CSV文件路径')
def import_bill(file):
    if not validate_csv_structure(file, BILL_REQUIRED_FIELDS):
        click.echo(f"错误: 供应商账单文件格式不正确")
        return
    
    try:
        items = read_supplier_bill(file)
        save_config('last_bill_file', file, '上次导入的供应商账单文件路径')
        click.echo(f"成功导入供应商账单: {len(items)} 条记录")
    except Exception as e:
        click.echo(f"错误: 导入供应商账单失败 - {str(e)}")

@import_command.command(name='receiving')
@click.option('--file', '-f', required=True, type=click.Path(exists=True), help='内部收货清单CSV文件路径')
def import_receiving(file):
    if not validate_csv_structure(file, RECEIVE_REQUIRED_FIELDS):
        click.echo(f"错误: 收货清单文件格式不正确")
        return
    
    try:
        items = read_receiving_list(file)
        save_config('last_receiving_file', file, '上次导入的收货清单文件路径')
        click.echo(f"成功导入收货清单: {len(items)} 条记录")
    except Exception as e:
        click.echo(f"错误: 导入收货清单失败 - {str(e)}")