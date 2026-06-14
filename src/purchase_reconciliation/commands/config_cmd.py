import click
from tabulate import tabulate

from ..storage import save_config, get_config, get_all_configs

VALID_RULE_KEYS = [
    'quantity_tolerance',
    'amount_tolerance', 
    'allow_partial_appeal'
]

@click.group(name='config')
def config_command():
    pass

@config_command.command(name='set')
@click.option('--key', '-k', required=True, help='配置键')
@click.option('--value', '-v', required=True, help='配置值')
@click.option('--description', '-d', help='配置描述')
def set_config(key, value, description):
    if key.startswith('rule.'):
        rule_key = key.replace('rule.', '')
        if rule_key not in VALID_RULE_KEYS:
            click.echo(f"错误: 无效的对账规则键 '{rule_key}'")
            click.echo(f"有效规则键: {VALID_RULE_KEYS}")
            return
        
        try:
            if rule_key in ['quantity_tolerance', 'amount_tolerance']:
                float_value = float(value)
                if float_value < 0:
                    click.echo(f"错误: 规则值必须大于等于0")
                    return
            elif rule_key == 'allow_partial_appeal':
                if value.lower() not in ['true', 'false', '1', '0']:
                    click.echo(f"错误: allow_partial_appeal 必须是 true/false 或 1/0")
                    return
        except ValueError:
            click.echo(f"错误: 值 '{value}' 格式不正确")
            return
    
    save_config(key, value, description or '')
    click.echo(f"配置已保存: {key} = {value}")

@config_command.command(name='get')
@click.option('--key', '-k', required=True, help='配置键')
def get_config_value(key):
    value = get_config(key)
    if value is None:
        click.echo(f"配置 '{key}' 不存在")
        return
    
    click.echo(f"{key} = {value}")

@config_command.command(name='list')
def list_configs():
    configs = get_all_configs()
    
    if not configs:
        click.echo("暂无配置")
        return
    
    table_data = []
    for key, info in configs.items():
        table_data.append([
            key,
            info['value'],
            info['description']
        ])
    
    headers = ['配置键', '值', '描述']
    click.echo(tabulate(table_data, headers=headers))

@config_command.command(name='rule')
@click.option('--set', 'action', flag_value='set', help='设置对账规则')
@click.option('--list', 'action', flag_value='list', help='列出对账规则')
@click.option('--key', '-k', help='规则键 (quantity_tolerance/amount_tolerance/allow_partial_appeal)')
@click.option('--value', '-v', help='规则值')
def manage_rules(action, key, value):
    if action == 'list' or (action is None and key is None):
        click.echo("\n对账规则配置:")
        click.echo("=" * 50)
        
        rules = [
            ('rule.quantity_tolerance', '数量容差', '允许的数量差异容忍度'),
            ('rule.amount_tolerance', '金额容差', '允许的金额差异容忍度'),
            ('rule.allow_partial_appeal', '允许部分申诉', '是否允许部分申诉')
        ]
        
        table_data = []
        for rule_key, name, desc in rules:
            current_value = get_config(rule_key)
            table_data.append([
                name,
                rule_key,
                current_value or '(未设置)',
                desc
            ])
        
        headers = ['规则名', '配置键', '当前值', '说明']
        click.echo(tabulate(table_data, headers=headers))
        return
    
    if action == 'set' or (action is None and key is not None and value is not None):
        if not key:
            click.echo("错误: 设置规则时需要指定 --key/-k")
            return
        if not value:
            click.echo("错误: 设置规则时需要指定 --value/-v")
            return
        
        if key not in VALID_RULE_KEYS:
            click.echo(f"错误: 无效的规则键 '{key}'")
            click.echo(f"有效规则键: {VALID_RULE_KEYS}")
            return
        
        try:
            if key in ['quantity_tolerance', 'amount_tolerance']:
                float_value = float(value)
                if float_value < 0:
                    click.echo(f"错误: 规则值必须大于等于0")
                    return
            elif key == 'allow_partial_appeal':
                if value.lower() not in ['true', 'false', '1', '0']:
                    click.echo(f"错误: allow_partial_appeal 必须是 true/false 或 1/0")
                    return
        except ValueError:
            click.echo(f"错误: 值 '{value}' 格式不正确")
            return
        
        rule_key = f'rule.{key}'
        save_config(rule_key, value, f'对账规则: {key}')
        click.echo(f"规则已设置: rule.{key} = {value}")
        return
    
    click.echo("使用 config rule --list 查看规则或 config rule --set --key <键> --value <值> 设置规则")