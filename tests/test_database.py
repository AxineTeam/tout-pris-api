import sqlite3

import pytest
from sqlalchemy.orm import Session

from app.database import enable_sqlite_pragmas, get_db


def test_get_db_yields_a_session_then_closes_it():
    generator = get_db()
    db = next(generator)
    assert isinstance(db, Session)
    with pytest.raises(StopIteration):
        next(generator)


def test_enable_sqlite_pragmas(tmp_path):
    connection = sqlite3.connect(tmp_path / "wal_test.db")
    enable_sqlite_pragmas(connection, None)
    assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert connection.execute("PRAGMA synchronous").fetchone()[0] == 1
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    connection.close()
