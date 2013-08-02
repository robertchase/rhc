'''
The MIT License (MIT)

Copyright (c) 2013 Robert H Chase

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''
from tcpsocket import BasicHandler

import time


class HTTPHandler(BasicHandler):

    def __init__(self, socket, context=None):
        '''
            Handler for an HTTP connection.

                http_response - entire reponse
                http_status_code - integer code from status line
                http_status_message - message from status line
                http_headers - dictionary of headers
                http_content - content
                error - any error message

                on_http_request(self, headers, content)
                on_http_response(self)
                on_http_error(self)
        '''
        super(HTTPHandler, self).__init__(socket, context)
        self.__data = ''
        self.__setup()

    def on_http_request(self, headers, content):
        pass

    def on_http_response(self):
        pass

    def on_http_error(self):
        pass

    def send(self, method='GET', host=None, resource='/', headers={},
             content='', close=False):

        if 'Date' not in headers:
            headers['Date'] = time.strftime(
                "%a, %d %b %Y %H:%M:%S %Z", time.localtime())
        if 'Content-Length' not in headers:
            headers['Content-Length'] = len(content)
        if close:
            headers['Connection'] = 'close'

        if not host:
            host = '%s:%s' % self.peer_address()

        headers = '%s %s HTTP/1.1\r\nHost: %s\r\n%s\r\n\r\n' % (
            method, resource, host,
            '\r\n'.join(['%s: %s' % (k, v) for k, v in headers.items()]))

        self.on_http_request(headers, content)

        super(HTTPHandler, self).send(headers + content)

    def __setup(self):
        self.http_response = ''
        self.http_status_code = None
        self.http_status_message = None
        self.http_headers = {}
        self.http_content = ''
        self.__state = self.__status

    def on_data(self, data):
        self.http_response += data
        self.__data += data
        while self.__state():
            pass

    def __error(self, message):
        self.error = message
        self.on_http_error()
        self.close()
        return False

    def __line(self):
        test = self.__data.split('\n', 1)
        if len(test) == 1:
            return None
        line, self.__data = test
        if len(line):
            if line[-1] == '\r':
                line = line[:-1]
        return line

    def __status(self):
        line = self.__line()
        if line == None:
            return False
        toks = line.split()
        if len(toks) < 3:
            return self.__error('Invalid status line: too few tokens')
        if toks[0] != 'HTTP/1.1':
            return self.__error('Invalid status line: not HTTP/1.1')
        try:
            self.http_status_code = toks[1]
            self.http_status_code = int(self.http_status_code)
        except ValueError:
            return self.__error('Invalid status line: non-integer status code')
        self.http_status_message = ' '.join(toks[2:])
        self.__state = self.__header
        return True

    def __header(self):
        line = self.__line()
        if line == None:
            return False

        if len(line) == 0:
            if 'Content-Length' in self.http_headers:
                try:
                    self.__length = int(self.http_headers['Content-Length'])
                except ValueError:
                    return self.__error('Invalid content length')
                self.__state = self.__content
                return True

            elif 'Transfer-Encoding' in self.http_headers:
                if self.http_headers['Transfer-Encoding'] != 'chunked':
                    return self.__error('Unsupported Transfer-Encoding value')
                self.__state = self.__chunked_length
                return True

            else:
                return self.__error('Invalid headers: no content length')

        test = line.split(':', 1)
        if len(test) != 2:
            return self.__error('Invalid header: missing colon')
        name, value = test
        self.http_headers[name.strip()] = value.strip()
        return True

    def __content(self):
        if len(self.__data) >= self.__length:
            self.http_content = self.__data[:self.__length]
            self.on_http_response()
            self.__data = self.__data[self.__length:]
            self.__setup()
            return True
        return False

    def __chunked_length(self):
        line = self.__line()
        if line == None:
            return False
        line = line.split(';', 1)[0]
        try:
            self.__length = int(line, 16)
        except ValueError:
            return self.__error('Invalid transfer-encoding chunk length: %s' % line)
        if self.__length == 0:
            self.__state = self.__footer
            return True
        self.__state = self.__chunked_content
        return True

    def __chunked_content(self):
        if len(self.__data) >= self.__length:
            self.http_content += self.__data[:self.__length]
            self.__data = self.__data[self.__length:]
            self.__state = self.__chunked_content_end
            return True
        return False

    def __chunked_content_end(self):
        line = self.__line()
        if line == None:
            return False
        if line == '':
            self.__state = self.__chunked_length
            return True
        return self.__error('Extra data at end of chunk')

    def __footer(self):
        line = self.__line()
        if line == None:
            return False

        if len(line) == 0:
            self.on_http_response()
            self.__setup()
            return True

        test = line.split(':', 1)
        if len(test) != 2:
            return self.__error('Invalid footer: missing colon')
        name, value = test
        self.http_headers[name.strip()] = value.strip()
        return True
