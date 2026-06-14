import click
from tabulate import tabulate

from ..utils import (
    read_supplier_bill, read_receiving_list, 
    validate_bill_with_required_fields, validate_receiving_with_required_fields,
    build_matching_key, check_date_offset
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
    
    bill_required_fields = active_scheme.required_fields if active_scheme and active_scheme.required_fields else None
    receive_required_fields = active_scheme.required_fields if active_scheme and active_scheme.required_fields else None
    
    bill_validation = validate_bill_with_required_fields(bill_path, bill_required_fields)
    receive_validation = validate_receiving_with_required_fields(receiving_path, receive_required_fields)
    
    all_errors = []
    all_errors.extend(bill_validation.errors)
    all_errors.extend(receive_validation.errors)
    
    if all_errors:
        click.echo(f"\n[DRY-RUN] 验证失败，发现 {len(all_errors)} 个错误:")
        click.echo("-" * 60)
        
        for err in all_errors:
            if active_scheme and active_scheme.required_fields:
                err_msg = f"  行 {err.row}: [{err.error_type}] {err.field}"
                if err.error_type == "MISSING_FIELD":
                    err_msg += f" (方案必填: {', '.join(active_scheme.required_fields)})"
                click.echo(err_msg)
            else:
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
    
    quantity_tolerance = active_scheme.quantity_tolerance if active_scheme else 0.0
    amount_tolerance = active_scheme.amount_tolerance if active_scheme else 0.0
    date_offset = active_scheme.date_offset_days if active_scheme else 0
    ignored_fields = active_scheme.ignored_fields if active_scheme else []
    
    if active_scheme:
        click.echo(f"使用方案: {active_scheme.name}")
        click.echo(f"  数量容差: {quantity_tolerance}")
        click.echo(f"  金额容差: {amount_tolerance}")
        click.echo(f"  日期偏移: {date_offset} 天")
        if active_scheme.required_fields:
            click.echo(f"  必填字段: {', '.join(active_scheme.required_fields)}")
        if ignored_fields:
            click.echo(f"  忽略字段: {', '.join(ignored_fields)}")
    elif no_scheme:
        click.echo("使用方案: (无 - 严格匹配)")
    else:
        click.echo("使用方案: (无激活方案，使用严格匹配)")
    
    click.echo("-" * 60)
    
    bill_dict = {}
    for item in bill_items:
        key = build_matching_key({
            'supplier_code': item.supplier_code,
            'item_code': item.item_code,
            'supplier_name': item.supplier_name,
        }, ignored_fields)
        if key not in bill_dict:
            bill_dict[key] = []
        bill_dict[key].append(item)
    
    receive_dict = {}
    for item in receive_items:
        key = build_matching_key({
            'supplier_code': item.supplier_code,
            'item_code': item.item_code,
            'supplier_name': item.supplier_name,
        }, ignored_fields)
        if key not in receive_dict:
            receive_dict[key] = []
        receive_dict[key].append(item)
    
    all_keys = set(bill_dict.keys()) | set(receive_dict.keys())
    
    raw_diff_items = []
    tolerated_items = []
    date_failed_items = []
    
    for key in all_keys:
        bill_list = bill_dict.get(key, [])
        receive_list = receive_dict.get(key, [])
        
        bill_qty = sum(item.quantity for item in bill_list)
        receive_qty = sum(item.quantity for item in receive_list)
        bill_amt = sum(item.amount for item in bill_list)
        receive_amt = sum(item.amount for item in receive_list)
        
        quantity_diff = bill_qty - receive_qty
        amount_diff = bill_amt - receive_amt
        
        supplier_code = bill_list[0].supplier_code if bill_list else (receive_list[0].supplier_code if receive_list else '')
        item_code = key[1] if len(key) > 1 else (key[0] if key else '')
        bill_no = bill_list[0].bill_no if bill_list else ''
        receive_no = receive_list[0].receive_no if receive_list else ''
        item_name = bill_list[0].item_name if bill_list else (receive_list[0].item_name if receive_list else '')
        supplier_name = bill_list[0].supplier_name if bill_list else (receive_list[0].supplier_name if receive_list else '')
        bill_date = bill_list[0].bill_date if bill_list else ''
        receive_date = receive_list[0].receive_date if receive_list else ''
        
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
        
        date_in_offset, date_reason = check_date_offset(bill_date, receive_date, date_offset)
        
        qty_tolerated, amt_tolerated = apply_tolerance(
            quantity_diff, amount_diff, quantity_tolerance, amount_tolerance
        )
        
        has_diff = abs(quantity_diff) > 0 or abs(amount_diff) > 0
        
        if bill_list and receive_list and not date_in_offset:
            date_failed_items.append({
                'item': diff_item,
                'bill_date': bill_date,
                'receive_date': receive_date,
                'reason': date_reason
            })
        elif not has_diff:
            pass
        elif qty_tolerated and amt_tolerated:
            reasons = []
            if qty_tolerated:
                reasons.append('数量')
            if amt_tolerated:
                reasons.append('金额')
            if date_offset > 0 and date_in_offset:
                reasons.append(f'日期({date_reason})')
            tolerated_items.append({
                'item': diff_item,
                'reason': '和'.join(reasons) + '在容差范围内'
            })
        elif qty_tolerated or amt_tolerated:
            reasons = []
            if qty_tolerated:
                reasons.append('数量')
            if amt_tolerated:
                reasons.append('金额')
            if date_offset > 0 and date_in_offset:
                reasons.append(f'日期({date_reason})')
            tolerated_items.append({
                'item': diff_item,
                'reason': '和'.join(reasons) + '在容差范围内'
            })
        else:
            reasons = ['数量和金额均超出容差']
            raw_diff_items.append({
                'item': diff_item,
                'reason': reasons[0]
            })
    
    if not raw_diff_items and not tolerated_items and not date_failed_items:
        click.echo("\n检查完成: 未发现差异")
        if active_scheme:
            click.echo("(所有差异均被规则吸收)")
        return
    
    click.echo(f"\n检查完成:")
    click.echo(f"  实际差异: {len(raw_diff_items)} 条")
    click.echo(f"  日期超出偏移: {len(date_failed_items)} 条")
    click.echo(f"  容差放过: {len(tolerated_items)} 条")
    click.echo("-" * 60)
    
    if date_failed_items:
        click.echo(f"\n【日期超出偏移】({len(date_failed_items)} 条):")
        date_table = []
        for t in date_failed_items:
            item = t['item']
            date_table.append([
                item.supplier_code,
                item.item_code,
                item.bill_quantity,
                item.receive_quantity,
                item.quantity_diff,
                item.bill_amount,
                item.receive_amount,
                item.amount_diff,
                t['bill_date'],
                t['receive_date'],
                t['reason']
            ])
        
        date_headers = [
            '供应商编码', '物料编码',
            '账单数量', '收货数量', '数量差异',
            '账单金额', '收货金额', '金额差异',
            '账单日期', '收货日期', '失败原因'
        ]
        click.echo(tabulate(date_table, headers=date_headers, floatfmt='.2f'))
    
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
        for t in raw_diff_items:
            item = t['item']
            table_data.append([
                item.supplier_code,
                item.item_code,
                item.item_name,
                item.bill_quantity,
                item.receive_quantity,
                item.quantity_diff,
                item.bill_amount,
                item.receive_amount,
                item.amount_diff,
                t['reason']
            ])
        
        headers = [
            '供应商编码', '物料编码', '物料名称',
            '账单数量', '收货数量', '数量差异',
            '账单金额', '收货金额', '金额差异', '失败原因'
        ]
        
        click.echo(tabulate(table_data, headers=headers, floatfmt='.2f'))
        
        if quantity_tolerance > 0 or amount_tolerance > 0 or date_offset > 0:
            rules = []
            if quantity_tolerance > 0:
                rules.append(f"数量容差 ±{quantity_tolerance}")
            if amount_tolerance > 0:
                rules.append(f"金额容差 ±{amount_tolerance}")
            if date_offset > 0:
                rules.append(f"日期偏移 ±{date_offset} 天")
            click.echo(f"\n说明: {', '.join(rules)}")
    
    if not dry_run:
        click.echo("\n--dry-run 未启用，但 diff check 命令仅做检查，不入库。")
        click.echo("如需生成批次，请使用 batch create 命令。")
