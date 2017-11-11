import json
import logging
import pytest

import rhc.connect as connect
import rhc.httphandler as http


logging.basicConfig(level=logging.DEBUG)


PORT = 12344
URL = 'http://localhost:{}'.format(PORT)


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


def test_non_json():

    def on_complete(rc, result):
        assert rc == 0
        assert isinstance(result, str)
        assert json.loads(result)

    connect.SERVER.add_server(PORT, _TestServer)
    connect.run(
        connect.connect(
            on_complete,
            URL,
            is_json=False,
        )
    )
    connect.SERVER.close()


def test_body():

    DATA = 'test'

    def on_complete(rc, result):
        assert rc == 0
        assert result['body'] == DATA

    connect.SERVER.add_server(PORT, _TestServer)
    connect.run(
        connect.connect(
            on_complete,
            URL,
            body=DATA,
        )
    )
    connect.SERVER.close()


@pytest.mark.parametrize('method', [
    ('GET'),
    ('PUT'),
    ('POST'),
    ('DELETE'),
])
def test_method(method):

    def on_complete(rc, result):
        assert rc == 0
        assert result['method'] == method

    connect.SERVER.add_server(PORT, _TestServer)
    connect.run(
        connect.connect(
            on_complete,
            URL,
            method=method,
        )
    )
    connect.SERVER.close()


def test_query():

    def on_complete(rc, result):
        assert rc == 0
        assert result['query_string'] == 'foo=bar&akk=eek'
        assert len(result['query']) == 2
        assert result['query']['foo'] == 'bar'
        assert result['query']['akk'] == 'eek'

    connect.SERVER.add_server(PORT, _TestServer)
    connect.run(
        connect.connect(
            on_complete,
            URL + '?foo=bar&akk=eek',
        )
    )
    connect.SERVER.close()


@pytest.mark.parametrize('method,body,has_query_string', [
    ('GET', dict(this='is', a='test'), True),
    ('PUT', dict(that='was', a='test'), False),
])
def test_dict_body(method, body, has_query_string):

    def on_complete(rc, result):
        assert rc == 0
        assert (len(result['query_string']) > 0) is has_query_string
        assert (len(result['body']) > 0) is not has_query_string

    connect.SERVER.add_server(PORT, _TestServer)
    connect.run(
        connect.connect(
            on_complete,
            URL,
            body=body,
            method=method,
        )
    )
    connect.SERVER.close()


@pytest.mark.parametrize('timeout,pause,is_timeout', [
    (100, 1, False),
    (1, 100, True),
])
def test_timeout(timeout, pause, is_timeout):

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

    connect.SERVER.add_server(PORT, _TestServer)
    connect.run(
        connect.connect(
            on_complete,
            URL,
            timeout=timeout / 1000.0,
            handler=Handler,
        )
    )
    connect.SERVER.close()


def test_wrapper():

    class Wrapper(object):
        def __init__(self, result):
            pass

    def on_complete(rc, result):
        assert rc == 0
        assert isinstance(result, Wrapper)

    connect.SERVER.add_server(PORT, _TestServer)
    connect.run(
        connect.connect(
            on_complete,
            URL,
            wrapper=Wrapper,
        )
    )
    connect.SERVER.close()


def test_headers():

    def on_complete(rc, result):
        assert rc == 0
        assert result['headers']['whatever'] == 'yeah'

    connect.SERVER.add_server(PORT, _TestServer)
    connect.run(
        connect.connect(
            on_complete,
            URL,
            headers=dict(whatever='yeah'),
        )
    )
    connect.SERVER.close()


def test_form():

    def on_complete(rc, result):
        assert rc == 0
        assert result['headers']['content-type'] == \
            'application/x-www-form-urlencoded'
        assert result['body'] in (
                'whatever=yeah&yeah=whatever',
                'yeah=whatever&whatever=yeah'
            )

    connect.SERVER.add_server(PORT, _TestServer)
    connect.run(
        connect.connect(
            on_complete,
            URL,
            body=dict(whatever='yeah', yeah='whatever'),
            is_form=True,
        )
    )
    connect.SERVER.close()
