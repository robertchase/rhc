import pytest

from rhc.database.db import DB


@pytest.fixture(scope='session')
def db_session():
    DB.setup(user='test', db='test_rhc', host='mysql', delta=True, commit=False)
    yield DB
    DB.close()


@pytest.fixture
def db(db_session):
    DB.start_transaction()
    yield DB
    DB.stop_transaction()
