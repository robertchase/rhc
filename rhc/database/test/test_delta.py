import pytest

from rhc.database.dao import DAO


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
def data(db):
    return Parent(foo=1, bar=2).save()


def test_save_one(data):
    data.foo = 3
    data.save()
    assert len(data._updated_fields) == 1
    assert 'foo' in data._updated_fields
    tt = Parent.load(data.id)
    assert tt.foo == 3
    assert tt.bar == 2


def test_save_none(data):
    data.foo = 1
    data.bar = 2
    data.save()
    assert len(data._updated_fields) == 0
