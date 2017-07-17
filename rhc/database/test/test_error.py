import pytest

from rhc.database.dao import DAO


class Error(DAO):

    TABLE = 'parent'

    FIELDS = (
        'id',
        'foo',
        'bar',
        'ohno',
    )

    DEFAULT = dict(
        foo=0,
    )

    JSON_FIELDS = (
        'ohno',
    )

    def before_save(self):
        assert isinstance(self.ohno, str)  # field is jsonified


@pytest.fixture
def data(db):
    return Error(foo=1, bar=2, ohno=dict(a=1, b=2))


def test_save_json_with_exception(data):
    assert isinstance(data.ohno, dict)
    try:
        data.save()
    except Exception as e:
        assert e.__class__.__name__ == 'InternalError'
        assert e.args[0] == 1054
        assert e.args[1] == u"Unknown column 'ohno' in 'field list'"
    assert isinstance(data.ohno, dict)  # field is un-jsonified even after exception
