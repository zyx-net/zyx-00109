import click

from .commands import import_cmd, diff, batch, appeal, rollback, export, status, audit, config_cmd, scheme_cmd

@click.group()
@click.version_option(version="1.0.0")
def cli():
    pass

cli.add_command(import_cmd.import_command)
cli.add_command(diff.diff_command)
cli.add_command(batch.batch_command)
cli.add_command(appeal.appeal_command)
cli.add_command(rollback.rollback_command)
cli.add_command(export.export_command)
cli.add_command(status.status_command)
cli.add_command(audit.audit_command)
cli.add_command(config_cmd.config_command)
cli.add_command(scheme_cmd.scheme_command)

if __name__ == "__main__":
    cli()