import click
from tabulate import tabulate

from ..utils import (
    read_supplier_bill, read_receiving_list, validate_supplier_bill_full,
    validate_receiving_list_full
)
from ..storage import get_config, get_active_rule_scheme, get_rule_scheme
from ..models import DiffItem, RuleScheme

@click.group(name='diff')
def diff_command():
    pass

def apply_tolerance(quantity_diff: float, amount_diff: float, 
                   quantity_tolerance: float, amount_tolerance: float) -> tuple:
    qty_tolerated = abs(quantity_diff) <= quantity_tolerance if quantity_tolerance > 0 else False
    amt_tolerated = abs(amount_diff) <= amount_tolerance if amount_tolerance > 0 else False
    return qty_tolerated, amt_tolerated

@diff_command.command(name='check')
@click.option('--bill-file', '-b', type=click.Path(exists=True), help='供应商账单文件路径')
@click.option('--receiving-file', '-r', type=click.Path(exists=True), help='收货清单文件路径')
@click.option('--scheme', '-s', help='使用的方案名称（不指定则使用激活方案）')
@click.option('--dry-run', '-d', is_flag=True, default=True, help='仅检查不入库')
@click.option('--no-scheme', is_flag=True, help='不使用任何方案，使用严格匹配')
def check_diff(bill_file, receiving_file, scheme, dry_run, no_scheme):
    bill_path = bill_file or get_config('last_bill_file')
    receiving_path = receiving_file or get_config('last_receiving_file')
    
    if not bill_path:
        click.echo("错误: 请提供供应商账单文件或先使用 import bill 命令导入")
        return
    
    if not receiving_path:
        click.echo("错误: 请提供收货清单文件或先使用 import receiving 命令导入")
        return
    
    active_scheme = None
    if not no_scheme:
        if scheme:
            active_scheme = get_rule_scheme(scheme)
            if not active_scheme:
                click.echo(f"错误: 方案 '{scheme}' 不存在")
                return
        else:
            active_scheme = get_active_rule_scheme()
    
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
    
    click.echo("\n" + "=" * 60)
    click.echo("对账检查")
    click.echo("=" * 60)
    
    if active_scheme:
        click.echo(f"使用方案: {active_scheme.name}")
        click.echo(f"  数量容差: {active_scheme.quantity_tolerance}")
        click.echo(f"  金额容差: {active_scheme.amount_tolerance}")
        click.echo(f"  日期偏移: {active_scheme.date_offset_days} 天")
        if active_scheme.ignored_fields:
            click.echo(f"  忽略字段: {', '.join(active_scheme.ignored_fields)}")
    elif no_scheme:
        click.echo("使用方案: (无 - 严格匹配)")
    else:
        click.echo("使用方案: (无激活方案，使用严格匹配)")
    
    click.echo("-" * 60)
    
    quantity_tolerance = active_scheme.quantity_tolerance if active_scheme else 0.0
    amount_tolerance = active_scheme.amount_tolerance if active_scheme else 0.0
    
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
    
    raw_diff_items = []
    tolerated_items = []
    
    for key in all_keys:
        bill_list = bill_dict.get(key, [])
        receive_list = receive_dict.get(key, [])
        
        bill_qty = sum(item.quantity for item in bill_list)
        receive_qty = sum(item.quantity for item in receive_list)
        bill_amt = sum(item.amount for item in bill_list)
        receive_amt = sum(item.amount for item in receive_list)
        
        quantity_diff = bill_qty - receive_qty
        amount_diff = bill_amt - receive_amt
        
        if abs(quantity_diff) > 0 or abs(amount_diff) > 0:
            supplier_code, item_code = key
            bill_no = bill_list[0].bill_no if bill_list else ''
            receive_no = receive_list[0].receive_no if receive_list else ''
            item_name = bill_list[0].item_name if bill_list else (receive_list[0].item_name if receive_list else '')
            supplier_name = bill_list[0].supplier_name if bill_list else (receive_list[0].supplier_name if receive_list else '')
            
            qty_tolerated, amt_tolerated = apply_tolerance(
                quantity_diff, amount_diff, quantity_tolerance, amount_tolerance
            )
            
            diff_item = DiffItem(
                bill_no=bill_no,
                receive_no=receive_no,
                item_code=item_code,
                item_name=item_name,
                bill_quantity=bill_qty,
                receive_quantity=receive_qty,
                quantity_diff=quantity_diff,
                bill_amount=bill_amt,
                receive_amount=receive_amt,
                amount_diff=amount_diff,
                supplier_code=supplier_code,
                supplier_name=supplier_name
            )
            
            if qty_tolerated and amt_tolerated:
                tolerated_items.append({
                    'item': diff_item,
                    'reason': '数量和金额均在容差范围内'
                })
            elif qty_tolerated:
                tolerated_items.append({
                    'item': diff_item,
                    'reason': '数量在容差范围内'
                })
            elif amt_tolerated:
                tolerated_items.append({
                    'item': diff_item,
                    'reason': '金额在容差范围内'
                })
            else:
                raw_diff_items.append(diff_item)
    
    if not raw_diff_items and not tolerated_items:
        click.echo("\n检查完成: 未发现差异")
        if active_scheme:
            click.echo("(所有差异均被容差吸收)")
        return
    
    click.echo(f"\n检查完成:")
    click.echo(f"  实际差异: {len(raw_diff_items)} 条")
    click.echo(f"  容差放过: {len(tolerated_items)} 条")
    click.echo("-" * 60)
    
    if tolerated_items:
        click.echo(f"\n【容差放过的差异】({len(tolerated_items)} 条):")
        tolerated_table = []
        for t in tolerated_items:
            item = t['item']
            tolerated_table.append([
                item.supplier_code,
                item.item_code,
                item.bill_quantity,
                item.receive_quantity,
                item.quantity_diff,
                item.bill_amount,
                item.receive_amount,
                item.amount_diff,
                t['reason']
            ])
        
        tolerance_headers = [
            '供应商编码', '物料编码',
            '账单数量', '收货数量', '数量差异',
            '账单金额', '收货金额', '金额差异', '放过原因'
        ]
        click.echo(tabulate(tolerated_table, headers=tolerance_headers, floatfmt='.2f'))
    
    if raw_diff_items:
        click.echo(f"\n【仍然失败的差异】({len(raw_diff_items)} 条):")
        table_data = []
        for item in raw_diff_items:
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
        
        if quantity_tolerance > 0 or amount_tolerance > 0:
            click.echo(f"\n说明: 数量容差 ±{quantity_tolerance}, 金额容差 ±{amount_tolerance}")
    
    if not dry_run:
        click.echo("\n--dry-run 未启用，但 diff check 命令仅做检查，不入库。")
        click.echo("如需生成批次，请使用 batch create 命令。")
