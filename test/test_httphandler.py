import unittest
from rhc.httphandler import HTTPHandler


class MyHandler(HTTPHandler):

    def __init__(self, socket, content=None):
        super(MyHandler, self).__init__(socket, content)

    def on_http_data(self):
        self.saved_http_headers = self.http_headers
        self.saved_http_content = self.http_content


class HTTPHandlerTest(unittest.TestCase):

    def setUp(self):
        self.handler = MyHandler(None)

    def test_basic(self):
        self.assertFalse(self.handler.closed)

    def test_status_empty_1(self):
        self.handler.on_data('\n')
        self.assertTrue(self.handler.closed)
        self.assertEqual(
            self.handler.error, 'Invalid status line: too few tokens')

    def test_status_empty_2(self):
        self.handler.on_data('\r\n')
        self.assertTrue(self.handler.closed)
        self.assertEqual(
            self.handler.error, 'Invalid status line: too few tokens')

    def test_status_short(self):
        self.handler.on_data('HTTP/1.1\r\n')
        self.assertTrue(self.handler.closed)
        self.assertEqual(
            self.handler.error, 'Invalid status line: too few tokens')

    def test_status_no_http(self):
        self.handler.on_data('HTTQ/1.1 HI THERE\r\n')
        self.assertTrue(self.handler.closed)
        self.assertEqual(
            self.handler.error, 'Invalid status line: not HTTP/1.1')

    def test_status_code_invalid(self):
        self.handler.on_data('HTTP/1.1 HI THERE\r\n')
        self.assertTrue(self.handler.closed)
        self.assertEqual(
            self.handler.error, 'Invalid status line: non-integer status code')

    def test_status_valid(self):
        self.handler.on_data('HTTP/1.1 100 HI THERE\r\n')
        self.assertFalse(self.handler.closed)
        self.assertEqual(self.handler.http_status_code, 100)
        self.assertEqual(self.handler.http_status_message, 'HI THERE')

    def test_header_missing_colon(self):
        self.handler.on_data('HTTP/1.1 100 HI THERE\r\nthis is a bad header\n')
        self.assertTrue(self.handler.closed)
        self.assertEqual(self.handler.error, 'Invalid header: missing colon')

    def test_header_valid(self):
        self.handler.on_data(
            'HTTP/1.1 100 HI THERE\r\n this : is a good header \n')
        self.assertFalse(self.handler.closed)
        self.assertEqual(self.handler.http_headers['this'], 'is a good header')

    def test_header_invalid_length(self):
        self.handler.on_data(
            'HTTP/1.1 100 HI THERE\r\n this : is a good header \nContent-Length:HI\n\n')
        self.assertTrue(self.handler.closed)
        self.assertEqual(self.handler.error, 'Invalid content length')

    def test_header_invalid_transfer_encoding(self):
        self.handler.on_data(
            'HTTP/1.1 100 HI THERE\r\n this : is a good header \nTransfer-Encoding:HI\n\n')
        self.assertTrue(self.handler.closed)
        self.assertEqual(
            self.handler.error, 'Unsupported Transfer-Encoding value')

    def test_header_valid_content_length(self):
        self.handler.on_data(
            'HTTP/1.1 100 HI THERE\r\n this : is a good header \nContent-Length:100\n\n')
        self.assertFalse(self.handler.closed)

    def test_header_valid_content_length_data(self):
        self.handler.on_data(
            'HTTP/1.1 100 HI THERE\r\n this : is a good header \nContent-Length:10\n\nabcde12345')
        self.assertFalse(self.handler.closed)

    def test_chunked_invalid_length(self):
        self.handler.on_data(
            'HTTP/1.1 100 HI THERE\r\nTransfer-Encoding:chunked\r\n\r\nG\r\n')
        self.assertTrue(self.handler.closed)
        self.assertEqual(
            self.handler.error, 'Invalid transfer-encoding chunk length: G')

    def test_chunked_valid_content(self):
        self.handler.on_data(
            'HTTP/1.1 100 HI THERE\r\nTransfer-Encoding:chunked\r\n\r\na\r\nabcde12345\r\n')
        self.assertFalse(self.handler.closed)
        self.assertEqual(self.handler.http_content, 'abcde12345')

    def test_chunked_extra_content(self):
        self.handler.on_data(
            'HTTP/1.1 100 HI THERE\r\nTransfer-Encoding:chunked\r\n\r\na\r\nabcde123456\r\n')
        self.assertTrue(self.handler.closed)
        self.assertEqual(self.handler.error, 'Extra data at end of chunk')

    def test_chunked_invalid_footer(self):
        self.handler.on_data(
            'HTTP/1.1 100 HI THERE\r\nTransfer-Encoding:chunked\r\n\r\na\r\nabcde12345\r\n')
        self.handler.on_data('0\r\nthis is a test\r\n')
        self.assertTrue(self.handler.closed)
        self.assertEqual(self.handler.error, 'Invalid footer: missing colon')

    def test_chunked_valid_chunked(self):
        self.handler.on_data(
            'HTTP/1.1 100 HI THERE\r\nTransfer-Encoding:chunked\r\n\r\n')
        self.handler.on_data('5\r\nabcde\r\n3\r\n123\r\n0\r\n')
        self.handler.on_data('footer:test\r\n\r\n')
        self.assertFalse(self.handler.closed)
        self.assertEqual(self.handler.saved_http_content, 'abcde123')
        self.assertEqual(self.handler.saved_http_headers['footer'], 'test')

    def test_header_valid_server(self):
        self.handler.on_data(
            'YO /this/is/a/test HTTP/1.1\r\nHost:whatever\nContent-Length:0\r\n\r\n')
        self.assertFalse(self.handler.closed)
        self.assertTrue(self.handler.http_method, 'YO')
        self.assertTrue(self.handler.http_resource, '/this/is/a/test')

    def test_query_string(self):
        self.handler.on_data(
            'YO /this/is/a/test?name=value&othername=othervalue HTTP/1.1\r\nHost:whatever\nContent-Length:0\r\n\r\n')
        self.assertFalse(self.handler.closed)
        self.assertEqual(self.handler.http_resource, '/this/is/a/test')
        self.assertEqual(self.handler.http_query['name'], 'value')
        self.assertEqual(self.handler.http_query['othername'], 'othervalue')
        self.assertEqual(
            self.handler.http_query_string, 'name=value&othername=othervalue')
