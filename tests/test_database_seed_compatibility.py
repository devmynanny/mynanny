from app import db as db_module


class _Rows:
    def fetchall(self):
        return []


class _Connection:
    def __init__(self):
        self.inserts = []

    def execute(self, statement, parameters=None):
        if str(statement).startswith("SELECT"):
            return _Rows()
        self.inserts.append((str(statement), parameters))
        return _Rows()


class _Transaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        return False


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    def begin(self):
        return _Transaction(self.connection)


def test_qualification_seed_binds_a_boolean_for_postgres_compatibility(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(db_module, "engine", _Engine(connection))
    monkeypatch.setattr(db_module, "_table_exists", lambda _conn, _table: True)

    db_module.ensure_qualifications_seed()

    assert connection.inserts
    for statement, parameters in connection.inserts:
        assert ":is_active" in statement
        assert parameters["is_active"] is True
