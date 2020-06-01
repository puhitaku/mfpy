import sys
from datetime import datetime, time

import click

import mfpy
from mfpy.model import TimeEntry


@click.group()
@click.option('--company_id', '-c')
@click.option('--user_id', '-u')
@click.option('--password', '-p')
@click.pass_context
def cmd(ctx, company_id, user_id, password):
    ctx.obj = {
        'company_id': company_id,
        'user_id': user_id,
        'password': password,
    }


@cmd.command()
@click.pass_context
def startjob(ctx):
    with mfpy.client(ctx.obj['company_id'], ctx.obj['user_id'], ctx.obj['password']) as client:
        print(f'Starting job... ', end='')
        ok, status = client.start_job()
        print('OK!' if ok else f'Failed ({status})')


@cmd.command()
@click.pass_context
def finishjob(ctx):
    with mfpy.client(ctx.obj['company_id'], ctx.obj['user_id'], ctx.obj['password']) as client:
        print(f'Finishing job... ', end='')
        ok, status = client.finish_job()
        print('OK!' if ok else f'Failed ({status})')


@cmd.command()
@click.pass_context
def startbreak(ctx):
    with mfpy.client(ctx.obj['company_id'], ctx.obj['user_id'], ctx.obj['password']) as client:
        print(f'Starting break... ', end='')
        ok, status = client.start_break()
        print('OK!' if ok else f'Failed ({status})')


@cmd.command()
@click.pass_context
def finishbreak(ctx):
    with mfpy.client(ctx.obj['company_id'], ctx.obj['user_id'], ctx.obj['password']) as client:
        print(f'Finishing break... ', end='')
        ok, status = client.finish_break()
        print('OK!' if ok else f'Failed ({status})')


@cmd.command()
@click.argument('entries', nargs=-1)
@click.option('--date', '-d', type=click.DateTime(formats=['%Y-%m-%d']), default=datetime.now(), show_default=True)
@click.pass_context
def postentries(ctx, date, entries):
    """Post time entries.

    Syntax of entries:

        HH-MM,HH-MM

        The former one is the "start time" and the latter one is the "stop time".

    Example:

        mfpy -c company -u user@example.com -p p4ssw0rd postentries -d 2020-04-28 "10:00,11:00" "11:22,12:34"

        This will be posted like: 10:00 (start job) -> 11:00 (start break) -> 11:22 (end break) -> 12:34 (finish job)

    Limitation:

        Hour must be in 0..23.
    """

    if len(entries) == 0:
        click.echo("Fatal: no entries are specified")
        click.echo(postentries.get_help(ctx))
        return sys.exit(1)

    converted = []
    for entry in entries:
        start, stop = entry.split(',')
        start, stop = time.fromisoformat(start.strip()), time.fromisoformat(stop.strip())
        converted.append(
            TimeEntry(
                date.replace(hour=start.hour, minute=start.minute, second=start.second),
                date.replace(hour=stop.hour, minute=stop.minute, second=stop.second),
            )
        )

    with mfpy.client(ctx.obj['company_id'], ctx.obj['user_id'], ctx.obj['password']) as client:
        print(f'Posting {date.strftime("%Y-%m-%d")} ... ', end='')
        ok, status = client.post_entries(converted)
        print('OK!' if ok else f'Failed ({status})')


cmd()
