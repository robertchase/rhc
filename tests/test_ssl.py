import rhc.tcpsocket as network
import os

PORT = 12345


class PlainServer(network.BasicHandler):

    def on_data(self, data):
        self.send('hellohello')  # respond badly to client hello


class Client(network.BasicHandler):

    def on_init(self):
        self.is_failed_handshake = False

    def on_failed_handshake(self, reason):
        self.is_failed_handshake = True

    def on_close(self):
        assert self.close_reason == 'failed ssl handshake'  # reason from _do_handshake
        assert self.t_ready == 0                            # connection never ready


def test_no_ssl_server():
    n = network.Server()
    n.add_server(PORT, PlainServer)                              # non-ssl server
    c = n.add_connection(('localhost', PORT), Client, ssl=True)  # ssl client
    while c.is_open:
        n.service()
    n.close()
    assert c.is_failed_handshake                                 # ends badly


class SuccessClient(Client):

    def on_ready(self):
        self.test_close_reason = 'test'                     # immediately close on handshake
        self.close(self.test_close_reason)

    def on_close(self):
        assert self.close_reason == self.test_close_reason  # verify close came from on_ready
        assert self.t_ready != 0                            # should have an on_ready time


def test_success():
    n = network.Server()
    cert_dir = os.path.dirname(__file__) + '/cert/'
    certfile = cert_dir + 'cert.pem'
    keyfile = cert_dir + 'key.pem'
    n.add_server(PORT, network.BasicHandler, ssl=True,
                 ssl_certfile=certfile, ssl_keyfile=keyfile)  # self-signed certs
    c = n.add_connection(('localhost', PORT), SuccessClient, ssl=True)
    while c.is_open:
        n.service()
    n.close()
    assert c.is_failed_handshake is False  # ssl handshake worked
