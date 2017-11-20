import json
import logging
import pytest

import rhc.connect as connect
import rhc.httphandler as http


logging.basicConfig(level=logging.DEBUG)


PORT = 12344
URL = 'http://localhost:{}'.format(PORT)


@pytest.fixture
def server():
    connect.SERVER.add_server(PORT, _TestServer)
    yield None
    connect.SERVER.close()


def test_failed_to_connect():

    def on_complete(rc, result):
        assert rc == 1
        assert result == 'failed to connect'

    connect.run(
        connect.connect(
            on_complete,
            URL,
            is_json=False,
        )
    )


class _TestServer(http.HTTPHandler):
    def on_http_data(self):
        result = dict(
            headers=self.http_headers,
            method=self.http_method,
            body=self.http_content,
            query=self.http_query,
            query_string=self.http_query_string,
        )
        self.send_server(json.dumps(result))


def test_non_json(server):

    def on_complete(rc, result):
        assert rc == 0
        assert isinstance(result, str)
        assert json.loads(result)

    connect.run(
        connect.connect(
            on_complete,
            URL,
            is_json=False,
        )
    )


def test_body(server):

    DATA = 'test'

    def on_complete(rc, result):
        assert rc == 0
        assert result['body'] == DATA

    connect.run(
        connect.connect(
            on_complete,
            URL,
            body=DATA,
        )
    )


@pytest.mark.parametrize('method', [
    ('GET'),
    ('PUT'),
    ('POST'),
    ('DELETE'),
])
def test_method(server, method):

    def on_complete(rc, result):
        assert rc == 0
        assert result['method'] == method

    connect.run(
        connect.connect(
            on_complete,
            URL,
            method=method,
        )
    )


def test_query(server):

    def on_complete(rc, result):
        assert rc == 0
        assert result['query_string'] == 'foo=bar&akk=eek'
        assert len(result['query']) == 2
        assert result['query']['foo'] == 'bar'
        assert result['query']['akk'] == 'eek'

    connect.run(
        connect.connect(
            on_complete,
            URL + '?foo=bar&akk=eek',
        )
    )


@pytest.mark.parametrize('method,body,has_query_string', [
    ('GET', dict(this='is', a='test'), True),
    ('PUT', dict(that='was', a='test'), False),
])
def test_dict_body(server, method, body, has_query_string):

    def on_complete(rc, result):
        assert rc == 0
        assert (len(result['query_string']) > 0) is has_query_string
        assert (len(result['body']) > 0) is not has_query_string

    connect.run(
        connect.connect(
            on_complete,
            URL,
            body=body,
            method=method,
        )
    )


@pytest.mark.parametrize('timeout,pause,is_timeout', [
    (100, 1, False),
    (1, 100, True),
])
def test_timeout(server, timeout, pause, is_timeout):

    class Handler(connect.ConnectHandler):

        def on_ready(self):
            connect.TIMERS.add(self._ready, pause).start()

        def _ready(self):
            super(Handler, self).on_ready()

    def on_complete(rc, result):
        if is_timeout:
            assert rc == 1
            assert result == 'timeout'
        else:
            assert rc == 0

    connect.run(
        connect.connect(
            on_complete,
            URL,
            timeout=timeout / 1000.0,
            handler=Handler,
        )
    )


def test_wrapper(server):

    class Wrapper(object):
        def __init__(self, result):
            pass

    def on_complete(rc, result):
        assert rc == 0
        assert isinstance(result, Wrapper)

    connect.run(
        connect.connect(
            on_complete,
            URL,
            wrapper=Wrapper,
        )
    )


def test_headers(server):

    def on_complete(rc, result):
        assert rc == 0
        assert result['headers']['whatever'] == 'yeah'

    connect.run(
        connect.connect(
            on_complete,
            URL,
            headers=dict(whatever='yeah'),
        )
    )


def test_form(server):

    def on_complete(rc, result):
        assert rc == 0
        assert result['headers']['content-type'] == \
            'application/x-www-form-urlencoded'
        assert result['body'] in (
                'whatever=yeah&yeah=whatever',
                'yeah=whatever&whatever=yeah'
            )

    connect.run(
        connect.connect(
            on_complete,
            URL,
            body=dict(whatever='yeah', yeah='whatever'),
            is_form=True,
        )
    )
