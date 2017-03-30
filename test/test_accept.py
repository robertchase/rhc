import rhc.tcpsocket as network


PORT = 12345


class RejectServer(network.BasicHandler):

    def on_accept(self):
        return False  # not letting anybody in

    def on_close(self):
        assert self.close_reason == 'connection not accepted'  # message from Listener's close
        assert self.t_open == 0                                # connection never completed


def test_reject():
    n = network.Server()
    n.add_server(PORT, RejectServer)
    c = n.add_connection(('localhost', PORT), network.BasicHandler)  # random connection
    while c.is_open:
        n.service()
    n.close()


class AcceptServer(network.BasicHandler):

    def on_ready(self):  # if we're here, we made it past on_accept
        self.test_close_reason = 'bye'
        self.close(self.test_close_reason)

    def on_close(self):
        assert self.close_reason == self.test_close_reason  # message from on_ready close
        assert self.t_open != 0                             # connection completed


def test_accept():
    n = network.Server()
    n.add_server(PORT, AcceptServer)
    c = n.add_connection(('localhost', PORT), network.BasicHandler)  # random connection
    while c.is_open:
        n.service()
    n.close()
