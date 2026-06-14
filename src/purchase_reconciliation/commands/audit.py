import click
from tabulate import tabulate

from ..storage import get_audit_logs, get_batch_by_no

@click.group(name='audit')
def audit_command():
    pass

@audit_command.command(name='list')
@click.option('--batch-no', '-b', help='批次编号（不指定则显示所有）')
def list_audit(batch_no):
    batch_id = None
    
    if batch_no:
        batch = get_batch_by_no(batch_no)
        if not batch:
            click.echo(f"错误: 批次 {batch_no} 不存在")
            return
        batch_id = batch.id
    
    logs = get_audit_logs(batch_id)
    
    if not logs:
        click.echo("暂无审计日志")
        return
    
    table_data = []
    for log in logs:
        table_data.append([
            log.id,
            log.batch_no,
            log.operation,
            log.operator,
            log.target_item_id or '',
            log.note[:50] + '...' if len(log.note) > 50 else log.note,
            log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    headers = ['日志ID', '批次编号', '操作类型', '操作人', '目标项ID', '备注', '操作时间']
    click.echo(tabulate(table_data, headers=headers))

@audit_command.command(name='summary')
def audit_summary():
    logs = get_audit_logs()
    
    if not logs:
        click.echo("暂无审计日志")
        return
    
    operation_counts = {}
    operator_counts = {}
    
    for log in logs:
        operation_counts[log.operation] = operation_counts.get(log.operation, 0) + 1
        operator_counts[log.operator] = operator_counts.get(log.operator, 0) + 1
    
    click.echo("审计日志汇总:")
    click.echo(f"  总操作数: {len(logs)}")
    click.echo("\n  操作类型分布:")
    for op, count in sorted(operation_counts.items()):
        click.echo(f"    {op}: {count}")
    
    click.echo("\n  操作人分布:")
    for operator, count in sorted(operator_counts.items()):
        click.echo(f"    {operator}: {count}")