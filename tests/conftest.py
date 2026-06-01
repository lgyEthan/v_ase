import pytest


@pytest.fixture(autouse=True)
def clear_editor_sessions():
    from v_ase.session import sessions

    sessions.clear()
    yield
    sessions.clear()
