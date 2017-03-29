import rhc.tcpsocket as network


'''
    connect to google

    perform a simple GET on google:80 and stop
    when network activity stops.

    Notes:

        1. the on_ready method is called when the connection
           is complete (including ssl handshake, if appropriate)
'''


class Google(network.BasicHandler):

    def on_fail(self, reason):
        print 'failed to connect: %s' % reason

    def on_open(self):
        print 'open'

    def on_close(self):
        print 'close: %s' % self.close_reason

    def on_ready(self):
        print 'sending'
        self.send(b'GET / HTTP/1.1\r\n\r\n')

    def on_send_complete(self):
        print 'send complete'

    def on_data(self, data):
        print 'new chunk of data:'
        print data
        print


n = network.Server()
c = n.add_connection(('www.google.com', 80), Google)
# c = n.add_connection(('www.google.com', 443), Google, ssl=True)
while True:
    '''
        this is an easy way to figure out how to stop, but not
        very useful in real applications, for two reasons:

          1. a painful delay is added at the end
          2. a network delay encountered during connection
             or while sending or receiving data might cause
             a premature exit from the loop.

        since this is an HTTP connection, using an
        http.HTTPHandler would allow for more accurate
        determination of a complete network exchange.

        that's another example.
    '''
    if not n.service(2):  # wait for up to 2 seconds
        break             # if nothing happened, we're done
