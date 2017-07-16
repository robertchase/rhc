import pytest

from rhc.database.db import DB
from rhc.database.dao import DAO


@pytest.fixture
def _db():
    db = DB.setup(user='test', database='test_rhc', host='mysql', commit=False)
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

    CALCULATED_FIELDS = dict(
        foo_bar='%s.foo + %s.bar' % (TABLE, TABLE),
    )

    CHILDREN = dict(
        child='rhc.database.test.test.Child',
    )


class Child(DAO):

    TABLE = 'child'

    FIELDS = (
        'id',
        'parent_id',
        'name',
    )

    FOREIGN = dict(
        parent='rhc.database.test.test.Parent',
    )

    @classmethod
    def by_name(cls, name):
        return cls.query().where('name=%s').execute(name, one=True)


def test_save(_db):
    t = Parent(foo=1, bar=2).save()
    assert t.id is not None
    assert t.foo == 1
    assert t.bar == 2


def test_load(_db):
    t = Parent(foo=1, bar=2).save()
    tt = Parent.load(t.id)
    assert t.id == tt.id
    assert tt.foo == 1
    assert tt.bar == 2


def test_default(_db):
    t = Parent(bar=1).save()
    assert t.foo == 0


def test_calculated(_db):
    t = Parent(foo=1, bar=2).save()
    tt = Parent.load(t.id)
    assert tt.foo_bar == 3


@pytest.fixture
def _data(_db):
    p = Parent(foo=1, bar=2).save()
    Child(parent=p, name='fred').save()
    Child(parent=p, name='sally').save()


def test_foreign(_data):
    c = Child.by_name('fred')
    assert c.parent.foo_bar == 3


def test_children(_data):
    p = next(Parent.list())
    c = p.children(Child)
    assert len(c) == 2


def test_join(_data):
    rs = Parent.query().join(Child).execute()
    assert len(rs) == 2
    names = [p.child.name for p in rs]
    assert len(names) == 2
    assert 'fred' in names
    assert 'sally' in names
