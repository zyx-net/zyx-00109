import click
import json
from tabulate import tabulate

from ..storage import (
    save_rule_scheme, get_rule_scheme, get_all_rule_schemes,
    get_active_rule_scheme, set_active_rule_scheme, delete_rule_scheme,
    export_all_rule_schemes, import_rule_schemes, get_config
)
from ..models import RuleScheme

@click.group(name='scheme')
def scheme_command():
    pass

@scheme_command.command(name='create')
@click.option('--name', '-n', required=True, help='方案名称（唯一标识）')
@click.option('--business-line', '-b', default='', help='业务线名称')
@click.option('--description', '-d', default='', help='方案描述')
@click.option('--quantity-tolerance', '-q', type=float, default=0.0, help='数量容差')
@click.option('--amount-tolerance', '-a', type=float, default=0.0, help='金额容差')
@click.option('--date-offset', type=int, default=0, help='日期偏移天数（正数延后，负数提前）')
@click.option('--required-fields', '-r', multiple=True, help='必填字段（可多次指定）')
@click.option('--ignored-fields', '-i', multiple=True, help='忽略字段（可多次指定）')
@click.option('--set-active/--no-active', default=False, help='创建后设为激活方案')
def create_scheme(name, business_line, description, quantity_tolerance, amount_tolerance,
                  date_offset, required_fields, ignored_fields, set_active):
    existing = get_rule_scheme(name)
    if existing:
        click.echo(f"错误: 方案 '{name}' 已存在")
        return
    
    scheme = RuleScheme(
        name=name,
        business_line=business_line,
        description=description,
        quantity_tolerance=quantity_tolerance,
        amount_tolerance=amount_tolerance,
        date_offset_days=date_offset,
        required_fields=list(required_fields),
        ignored_fields=list(ignored_fields),
        is_active=set_active
    )
    
    if set_active:
        for s in get_all_rule_schemes():
            if s.is_active and s.name != name:
                s.is_active = False
                save_rule_scheme(s)
    
    save_rule_scheme(scheme)
    click.echo(f"方案 '{name}' 创建成功")
    if set_active:
        click.echo(f"方案 '{name}' 已设为激活状态")

@scheme_command.command(name='list')
@click.option('--verbose', '-v', is_flag=True, help='显示详细信息')
def list_schemes(verbose):
    schemes = get_all_rule_schemes()
    
    if not schemes:
        click.echo("暂无方案")
        return
    
    active_scheme = get_active_rule_scheme()
    active_name = active_scheme.name if active_scheme else None
    
    if verbose:
        click.echo("\n方案详情列表:")
        click.echo("=" * 80)
        for scheme in schemes:
            active_tag = " [激活]" if scheme.name == active_name else ""
            click.echo(f"\n名称: {scheme.name}{active_tag}")
            click.echo(f"  业务线: {scheme.business_line or '(未设置)'}")
            click.echo(f"  描述: {scheme.description or '(无)'}")
            click.echo(f"  数量容差: {scheme.quantity_tolerance}")
            click.echo(f"  金额容差: {scheme.amount_tolerance}")
            click.echo(f"  日期偏移: {scheme.date_offset_days} 天")
            click.echo(f"  必填字段: {', '.join(scheme.required_fields) or '(无)'}")
            click.echo(f"  忽略字段: {', '.join(scheme.ignored_fields) or '(无)'}")
    else:
        table_data = []
        for scheme in schemes:
            active_tag = " [激活]" if scheme.name == active_name else ""
            table_data.append([
                scheme.name + active_tag,
                scheme.business_line or '-',
                scheme.quantity_tolerance,
                scheme.amount_tolerance,
                scheme.date_offset_days
            ])
        
        headers = ['方案名称', '业务线', '数量容差', '金额容差', '日期偏移']
        click.echo(tabulate(table_data, headers=headers))

@scheme_command.command(name='show')
@click.option('--name', '-n', required=True, help='方案名称')
def show_scheme(name):
    scheme = get_rule_scheme(name)
    if not scheme:
        click.echo(f"错误: 方案 '{name}' 不存在")
        return
    
    active_tag = " [激活]" if scheme.is_active else ""
    click.echo(f"\n方案详情: {scheme.name}{active_tag}")
    click.echo("=" * 50)
    click.echo(f"业务线: {scheme.business_line or '(未设置)'}")
    click.echo(f"描述: {scheme.description or '(无)'}")
    click.echo(f"数量容差: {scheme.quantity_tolerance}")
    click.echo(f"金额容差: {scheme.amount_tolerance}")
    click.echo(f"日期偏移: {scheme.date_offset_days} 天")
    click.echo(f"必填字段: {', '.join(scheme.required_fields) if scheme.required_fields else '(无)'}")
    click.echo(f"忽略字段: {', '.join(scheme.ignored_fields) if scheme.ignored_fields else '(无)'}")

@scheme_command.command(name='switch')
@click.option('--name', '-n', required=True, help='要激活的方案名称')
def switch_scheme(name):
    if not get_rule_scheme(name):
        click.echo(f"错误: 方案 '{name}' 不存在")
        return
    
    if set_active_rule_scheme(name):
        click.echo(f"已切换到方案: {name}")
    else:
        click.echo(f"错误: 切换方案失败")

@scheme_command.command(name='delete')
@click.option('--name', '-n', required=True, help='要删除的方案名称')
@click.option('--force', '-f', is_flag=True, help='强制删除，无需确认')
def delete_scheme(name, force):
    if not get_rule_scheme(name):
        click.echo(f"错误: 方案 '{name}' 不存在")
        return
    
    if not force:
        if not click.confirm(f"确定要删除方案 '{name}' 吗？"):
            click.echo("取消删除")
            return
    
    if delete_rule_scheme(name):
        click.echo(f"方案 '{name}' 已删除")
    else:
        click.echo(f"错误: 删除方案失败")

@scheme_command.command(name='update')
@click.option('--name', '-n', required=True, help='要更新的方案名称')
@click.option('--business-line', '-b', help='业务线名称')
@click.option('--description', '-d', help='方案描述')
@click.option('--quantity-tolerance', '-q', type=float, help='数量容差')
@click.option('--amount-tolerance', '-a', type=float, help='金额容差')
@click.option('--date-offset', type=int, help='日期偏移天数')
@click.option('--required-fields', '-r', multiple=True, help='必填字段')
@click.option('--ignored-fields', '-i', multiple=True, help='忽略字段')
def update_scheme(name, business_line, description, quantity_tolerance, amount_tolerance,
                  date_offset, required_fields, ignored_fields):
    scheme = get_rule_scheme(name)
    if not scheme:
        click.echo(f"错误: 方案 '{name}' 不存在")
        return
    
    if business_line is not None:
        scheme.business_line = business_line
    if description is not None:
        scheme.description = description
    if quantity_tolerance is not None:
        scheme.quantity_tolerance = quantity_tolerance
    if amount_tolerance is not None:
        scheme.amount_tolerance = amount_tolerance
    if date_offset is not None:
        scheme.date_offset_days = date_offset
    if required_fields:
        scheme.required_fields = list(required_fields)
    if ignored_fields:
        scheme.ignored_fields = list(ignored_fields)
    
    save_rule_scheme(scheme)
    click.echo(f"方案 '{name}' 已更新")

@scheme_command.command(name='export')
@click.option('--output', '-o', required=True, help='导出文件路径')
def export_schemes(output):
    import os
    if os.path.exists(output):
        click.echo(f"错误: 目标文件已存在: {output}")
        return
    
    schemes_data = export_all_rule_schemes()
    
    with open(output, 'w', encoding='utf-8') as f:
        json.dump({
            'version': '1.0',
            'exported_at': __import__('datetime').datetime.now().isoformat(),
            'schemes': schemes_data
        }, f, ensure_ascii=False, indent=2)
    
    click.echo(f"已导出 {len(schemes_data)} 个方案到: {output}")

@scheme_command.command(name='import')
@click.option('--file', '-f', required=True, type=click.Path(exists=True), help='导入文件路径')
@click.option('--conflict', '-c', 
              type=click.Choice(['overwrite', 'skip', 'rename'], case_sensitive=False),
              default='skip',
              help='遇到同名方案时的处理方式: overwrite(覆盖), skip(跳过), rename(改名)')
def import_schemes(file, conflict):
    try:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        schemes_data = data.get('schemes', [])
        if not schemes_data:
            click.echo("文件中没有找到方案数据")
            return
        
        imported, skipped, overwritten, renamed = import_rule_schemes(schemes_data, conflict)
        
        click.echo(f"导入完成:")
        click.echo(f"  新增: {imported}")
        click.echo(f"  跳过: {skipped}")
        click.echo(f"  覆盖: {overwritten}")
        click.echo(f"  改名: {renamed}")
        
    except json.JSONDecodeError:
        click.echo(f"错误: 文件格式不正确，无法解析 JSON")
    except Exception as e:
        click.echo(f"错误: 导入失败 - {str(e)}")

@scheme_command.command(name='active')
def show_active():
    scheme = get_active_rule_scheme()
    if not scheme:
        click.echo("当前没有激活的方案")
        click.echo("使用 'scheme switch -n <方案名>' 切换方案")
        return
    
    click.echo(f"当前激活方案: {scheme.name}")
    click.echo(f"  业务线: {scheme.business_line or '(未设置)'}")
    click.echo(f"  数量容差: {scheme.quantity_tolerance}")
    click.echo(f"  金额容差: {scheme.amount_tolerance}")
    click.echo(f"  日期偏移: {scheme.date_offset_days} 天")
