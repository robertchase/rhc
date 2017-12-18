import pytest

from rhc.httphandler import HTTPHandler
from rhc.resthandler import RESTRequest


@pytest.fixture
def handler():

    class _network(object):
        def _unregister(self, sock):
            pass


    class _context(object):
        def __init__(self):
            self.context = {}


    class _handler(HTTPHandler):

        def __init__(self):
            super(_handler, self).__init__(0, context=_context())
            self._network = _network()

        def on_http_data(self):
            self.request = RESTRequest(self)  # use RESTRequest to cache result


    return _handler()


def test_basic(handler):
    assert handler.is_open


def test_status_empty_1(handler):
    handler.on_data('\n')
    assert handler.closed
    assert handler.error == 'Invalid status line: too few tokens'


def test_status_empty_2(handler):
    handler.on_data('\r\n')
    assert handler.closed
    assert handler.error == 'Invalid status line: too few tokens'


def test_status_short(handler):
    handler.on_data('HTTP/1.1\r\n')
    assert handler.closed
    assert handler.error == 'Invalid status line: too few tokens'


def test_status_no_http(handler):
    handler.on_data('HTTQ/1.1 HI THERE\r\n')
    assert handler.closed
    assert handler.error == 'Invalid status line: not HTTP/1.0 or HTTP/1.1'


def test_status_code_invalid(handler):
    handler.on_data('HTTP/1.1 HI THERE\r\n')
    assert handler.closed
    assert handler.error == 'Invalid status line: non-integer status code'


def test_status_valid(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\n')
    assert handler.is_open
    assert handler.http_status_code == 100
    assert handler.http_status_message == 'HI THERE'


def test_header_missing_colon(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\nthis is a bad header\n')
    assert handler.closed
    assert handler.error == 'Invalid header: missing colon'


def test_header_valid(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\n this : is a good header \n')
    assert handler.is_open
    assert handler.http_headers['this'] == 'is a good header'


def test_header_invalid_length(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\n this : is a good header \nContent-Length:HI\n\n')
    assert handler.closed
    assert handler.error == 'Invalid content length'


def test_header_invalid_transfer_encoding(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\n this : is a good header \nTransfer-Encoding:HI\n\n')
    assert handler.closed
    assert handler.error == 'Unsupported Transfer-Encoding value'


def test_header_valid_content_length(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\n this : is a good header \nContent-Length:100\n\n')
    assert handler.is_open


def test_header_valid_content_length_data(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\n this : is a good header \nContent-Length:10\n\nabcde12345')
    assert handler.is_open


def test_chunked_invalid_length(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\nTransfer-Encoding:chunked\r\n\r\nG\r\n')
    assert handler.closed
    assert handler.error == 'Invalid transfer-encoding chunk length: G'


def test_chunked_valid_content(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\nTransfer-Encoding:chunked\r\n\r\na\r\nabcde12345\r\n')
    assert handler.is_open
    assert handler.http_content == 'abcde12345'


def test_chunked_extra_content(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\nTransfer-Encoding:chunked\r\n\r\na\r\nabcde123456\r\n')
    assert handler.closed
    assert handler.error == 'Extra data at end of chunk'


def test_chunked_invalid_footer(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\nTransfer-Encoding:chunked\r\n\r\na\r\nabcde12345\r\n')
    handler.on_data('0\r\nthis is a test\r\n')
    assert handler.closed
    assert handler.error == 'Invalid footer: missing colon'


def test_chunked_valid_chunked(handler):
    handler.on_data('HTTP/1.1 100 HI THERE\r\nTransfer-Encoding:chunked\r\n\r\n')
    handler.on_data('5\r\nabcde\r\n3\r\n123\r\n0\r\n')
    handler.on_data('footer:test\r\n\r\n')
    assert handler.is_open
    assert handler.request.http_content == 'abcde123'
    assert handler.request.http_headers['footer'] == 'test'


def test_header_valid_server(handler):
    handler.on_data('YO /this/is/a/test HTTP/1.1\r\nHost:whatever\nContent-Length:0\r\n\r\n')
    assert handler.is_open
    assert handler.request.http_method == 'YO'
    assert handler.request.http_resource == '/this/is/a/test'


def test_query_string(handler):
    handler.on_data('YO /this/is/a/test?name=value&othername=othervalue HTTP/1.1\r\nHost:whatever\nContent-Length:0\r\n\r\n')
    assert handler.is_open
    assert handler.request.http_resource == '/this/is/a/test'
    assert handler.request.http_query['name'] == 'value'
    assert handler.request.http_query['othername'] == 'othervalue'
    assert handler.request.http_query_string == 'name=value&othername=othervalue'


def test_multipart(handler):
    data = '''POST /upload HTTP/1.1\r
Host: localhost:3000\r
Content-Length: 590\r
Content-Type: multipart/form-data; boundary=----WebKitFormBoundaryzNeA5Pv9NTCGzDAc\r
\r
------WebKitFormBoundaryzNeA5Pv9NTCGzDAc\r
Content-Disposition: form-data; name="foo"\r
\r
whatever\r
------WebKitFormBoundaryzNeA5Pv9NTCGzDAc\r
Content-Disposition: form-data; name="uploadedfile"; filename="tmp.py"\r
Content-Type: text/x-python-script\r
\r
import json
import sys

f = open(sys.argv[1]) if len(sys.argv) >= 2 else sys.stdin

data = json.loads(f.read())
for record in data['feedback']['record']:
    print record['row']['source_ip'], record['row']['count'], record['identifiers']['header_from'], record['auth_results']['spf']['result']
\r
------WebKitFormBoundaryzNeA5Pv9NTCGzDAc--\r
'''
    handler.on_data(data)
    assert handler.is_open
    assert handler.request.http_multipart[0].disposition['name'] == '"foo"'
    assert handler.request.http_multipart[0].content == 'whatever\r\n'
    assert handler.request.http_multipart[1].disposition['filename'] == '"tmp.py"'
