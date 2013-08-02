import struct
import unittest
from rhc.packethandler import FourBytePacketHandler

class MyHandler(FourBytePacketHandler):
    def __init__(self, socket, content=None):
        super(MyHandler, self).__init__(socket, content)
        self.data = None
    def on_data(self, data):
        self.data = data

class HTTPHandlerTest(unittest.TestCase):

    def setUp(self):
        self.handler = MyHandler(None)

    def test_basic(self):
        self.assertIsNone(self.handler.data)

    def test_send_something(self):
        test_data = "dude, where's my car?"
        self.handler.on_recv(struct.pack('!I', len(test_data)))
        self.assertIsNone(self.handler.data)
        self.handler.on_recv(test_data)
        self.assertEqual(self.handler.data, test_data)
