import pytest
from rhc.resthandler import RESTMapper


class TestRestHandler(object):

    @pytest.fixture
    def mapper(self):
        mapper = RESTMapper()
        mapper.add('/test$', get=1, post=2, put=3, delete=4)
        mapper.add('/foo$', get=1, post=2)
        mapper.add('/foo$', put=5)
        return mapper

    @pytest.mark.parametrize('path, http_method, handler, group', [
        ('/test', 'GET', 1, ()),
        ('/testt', 'GET', None, None),
        ('/foo', 'post', 2, ()),
        ('/foo', 'put', 5, ())
    ])
    def test_basic(self, mapper, path, http_method, handler, group):
        handler, group, _ = mapper._match(path, http_method)
        assert handler == handler
        assert group == group

    def test_multiple(self, mapper):
        handler, group, _ = mapper._match('/foo', 'post')
        assert handler == 2
        handler, group, _ = mapper._match('/foo', 'put')
        assert handler == 5
