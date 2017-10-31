def test_simple(db_session):
    assert db_session.level == 0
    db_session.reset()
    assert db_session.level == 0


def test_transaction(db_session):
    assert db_session.level == 0
    db_session.start_transaction()
    assert db_session.level == 1
    db_session.reset()
    assert db_session.level == 0
