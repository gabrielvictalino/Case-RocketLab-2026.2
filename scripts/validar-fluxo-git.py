#!/usr/bin/env python3
"""Valida o evento do GitHub e o diff sem depender de pacotes externos."""

import json
import os
import re
import subprocess
import sys

TYPES = r'(?:feat|fix|docs|refactor|test|chore|style)'
BRANCH = re.compile(rf'{TYPES}/[a-z0-9]+(?:-[a-z0-9]+)*')
COMMIT = re.compile(rf'{TYPES}(?:\([a-z0-9]+(?:-[a-z0-9]+)*\))?!?: \S.*')


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def validate(event, event_name, repository):
    if event_name == 'pull_request':
        pr = event['pull_request']
        base = pr['base']['ref']
        head = pr['head']['ref']
        if base not in ('main', 'dev'):
            raise ValueError('Destino deve ser main ou dev.')
        if base == 'main':
            if head != 'dev' or pr['head']['repo']['full_name'] != repository:
                raise ValueError('main recebe apenas PRs da dev deste repositório.')
        elif not BRANCH.fullmatch(head):
            raise ValueError('Branch de trabalho deve seguir <tipo>/<descricao-kebab-case>.')
        if not COMMIT.fullmatch(pr['title']):
            raise ValueError('Título do PR deve seguir Conventional Commits.')
        start, end = pr['base']['sha'], pr['head']['sha']
        if base == 'dev':
            for sha in git('rev-list', '--no-merges', f'{start}..{end}').splitlines():
                if not COMMIT.fullmatch(git('show', '-s', '--format=%s', sha)):
                    raise ValueError(f'Commit {sha} não segue Conventional Commits.')
        subprocess.run(['git', 'diff', '--check', f'{start}...{end}'], check=True)
    elif event_name == 'push':
        if event['ref'] not in ('refs/heads/main', 'refs/heads/dev'):
            raise ValueError('Push fora das branches de integração.')
        start, end = event['before'], event['after']
        if set(start) == {'0'}:
            start = git('hash-object', '-t', 'tree', '/dev/null')
        subprocess.run(['git', 'diff', '--check', start, end], check=True)
    else:
        raise ValueError(f'Evento não suportado: {event_name}')


if __name__ == '__main__':
    try:
        with open(os.environ['GITHUB_EVENT_PATH'], encoding='utf-8') as source:
            validate(
                json.load(source), os.environ['GITHUB_EVENT_NAME'], os.environ['GITHUB_REPOSITORY']
            )
    except (ValueError, subprocess.CalledProcessError, KeyError) as error:
        print(f'Fluxo Git: {error}', file=sys.stderr)
        sys.exit(1)
    print('Fluxo Git validado.')
