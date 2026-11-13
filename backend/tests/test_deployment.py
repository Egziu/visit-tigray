"""A failed migration or grant must prevent deployment bootstrap."""
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(('migration_exit', 'grant_exit', 'expected', 'commands'), [
    (17, 0, 17, ['alembic']),
    (0, 19, 19, ['alembic', 'psql']),
    (0, 0, 0, ['alembic', 'psql', 'python']),
])
def test_predeploy_fail_closed(tmp_path, migration_exit, grant_exit, expected, commands):
    binary = tmp_path / 'bin'
    binary.mkdir()
    log = tmp_path / 'commands'
    for name, status in [('alembic', migration_exit), ('psql', grant_exit), ('python', 0)]:
        path = binary / name
        path.write_text(f'#!/bin/sh\necho {name} >> "$COMMAND_LOG"\nexit {status}\n')
        path.chmod(0o755)
    environment = {**os.environ, 'PATH': f'{binary}:/usr/bin:/bin', 'COMMAND_LOG': str(log),
                   'DATABASE_MIGRATION_URL': 'postgresql+psycopg://localhost/test',
                   'SEED_STAGING': 'false'}
    result = subprocess.run(['bash', str(Path(__file__).resolve().parents[1] / 'scripts/predeploy.sh')],
                            env=environment, capture_output=True, text=True, check=False)
    assert result.returncode == expected, result.stderr
    assert log.read_text().splitlines() == commands
