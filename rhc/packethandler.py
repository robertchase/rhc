'''
The MIT License (MIT)

Copyright (c) 2013-2014 Robert H Chase

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
import struct
from tcpsocket import BasicHandler, Client


class PacketHandler (BasicHandler):

    ''' Handle header+packet/TCP protocol '''

    def __init__(self, socket, context=None):
        super(PacketHandler, self).__init__(socket, context)
        self.txPacketCount = 0
        self.rxPacketCount = 0
        self.__setup_header()  # start off waiting for a header

    # ---
    # --- override these methods
    # ---

    # process header, return data length (0=header-only packet)
    def on_header(self, header):
        return 0

    def header_length(self):
        return 0

    # process data
    def on_data(self, data):
        pass

    # --- override this to handle complex (eg variable length) headers
    def setup_header(self):
        pass

    # ---
    # --- implement this method in subclass; add header and then super this method
    # ---
    def send(self, data):
        self.txPacketCount += 1
        super(PacketHandler, self).send(data)

    # ---
    # --- leave the following methods alone
    # ---

    def on_recv(self, data):
        self.__read_buf += data
        self.RECV_LEN -= len(data)
        if 0 == self.RECV_LEN:
            self.read_handler()

    def __data_handler(self):
        self.on_data(self.__read_buf)
        self.__setup_header()

    def __header_handler(self):
        self.rxPacketCount += 1
        self.RECV_LEN = self.on_header(self.__read_buf)
        if 0 == self.RECV_LEN:
            self.__setup_header()
        else:
            self.__setup_data()

    def __setup_header(self):
        self.__read_buf = ''
        self.read_handler = self.__header_handler
        self.RECV_LEN = self.header_length()
        assert (self.RECV_LEN > 0)
        self.setup_header()

    def __setup_data(self):
        self.__read_buf = ''
        self.read_handler = self.__data_handler


class TwoBytePacketHandler (PacketHandler):

    ''' PacketHandler for two byte network order data length header '''

    def on_header(self, header):
        return struct.unpack('!h', header)[0]

    def header_length(self):
        return 2

    def send(self, data):
        super(TwoBytePacketHandler, self).send(struct.pack('!h', len(data))
                                               + data)


class TwoBytePacketClient (Client):

    def write(self, data):
        super(TwoBytePacketClient, self).write(
            struct.pack('!h', len(data)) + data)

    def read(self):
        l = super(TwoBytePacketClient, self).read(2)
        l = struct.unpack('!h', l)[0]
        return super(TwoBytePacketClient, self).read(l)


class FourBytePacketHandler (PacketHandler):

    ''' PacketHandler for four byte network order data length header '''

    def on_header(self, header):
        return struct.unpack('!I', header)[0]

    def header_length(self):
        return 4

    def send(self, data):
        super(FourBytePacketHandler, self).send(struct.pack('!I', len(data))
                                                + data)


class FourBytePacketClient (Client):

    def write(self, data):
        super(FourBytePacketClient, self).write(
            struct.pack('!I', len(data)) + data)

    def read(self):
        l = super(FourBytePacketClient, self).read(4)
        l = struct.unpack('!I', l)[0]
        return super(FourBytePacketClient, self).read(l)


if '__main__' == __name__:
    # !!! TEST !!!
    from tcpsocket import Server
    import time

    TESTDATA = 'this is a test'

    class SHandler (TwoBytePacketHandler):

        def on_data(self, data):
            assert (TESTDATA == data)
            assert (len(data) + 2 == self.rxByteCount)
            assert (0 == self.txByteCount)
            self.send(data)
            assert (len(data) + 2 == self.txByteCount)

    class CHandler (TwoBytePacketHandler):

        def on_ready(self):
            assert (0 == self.txPacketCount)
            self.send(TESTDATA)
            assert (1 == self.txPacketCount)
            assert (len(TESTDATA) + 2 == self.txByteCount)

        def on_close(self):
            assert (1 == self.txPacketCount)
            assert (1 == self.rxPacketCount)
            self.context.done = True

        def on_fail(self):
            raise Exception('failed to connect to %s, %s' % (
                self.name, self.error))

        def on_data(self, data):
            assert (TESTDATA == data)
            assert (len(data) + 2 == self.rxByteCount)
            assert (len(data) + 2 == self.txByteCount)
            assert (1 == self.rxPacketCount)
            self.shutdown()

    class Context (object):

        def __init__(self):
            self.done = False

    s = Server()
    s.add_server(10130, SHandler)
    c = Context()
    s.add_connection(('localhost', 10130), CHandler, c)

    while not c.done:
        s.service()
        time.sleep(.01)
