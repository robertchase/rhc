import pytest

from rhc.database.db import DB
from rhc.database.dao import DAO


@pytest.fixture
def _db():
    db = DB.setup(user='test', database='test_rhc', host='mysql', delta=True, commit=False)
    db.start_transaction()
    yield db
    db.stop_transaction(commit=False)


class Parent(DAO):

    TABLE = 'parent'

    FIELDS = (
        'id',
        'foo',
        'bar',
    )

    DEFAULT = dict(
        foo=0,
    )


@pytest.fixture
def _data(_db):
    return Parent(foo=1, bar=2).save()


def test_save_one(_data):
    _data.foo = 3
    _data.save()
    assert len(_data._updated_fields) == 1
    assert 'foo' in _data._updated_fields
    tt = Parent.load(_data.id)
    assert tt.foo == 3
    assert tt.bar == 2


def test_save_none(_data):
    _data.foo = 1
    _data.bar = 2
    _data.save()
    assert len(_data._updated_fields) == 0
