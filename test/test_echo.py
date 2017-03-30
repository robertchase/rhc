import rhc.tcpsocket as network


PORT = 12345


class EchoServer(network.BasicHandler):

    def on_data(self, data):
        self.send(data)            # step 2: on server recv, send data back


class EchoClient(network.BasicHandler):

    def on_ready(self):
        self.test_data = b'test_data'
        self.send(self.test_data)  # step 1: on client connect, send data

    def on_data(self, data):       # step 3: on client recv, assert and close
        assert data == self.test_data
        self.close()


def test_echo():
    n = network.Server()
    n.add_server(PORT, EchoServer)
    c = n.add_connection(('localhost', PORT), EchoClient)
    while c.is_open:  # keep going until the client closes
        n.service()
    n.close()
