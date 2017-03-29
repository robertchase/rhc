import rhc.tcpsocket as network


'''
    standard 'hello world' for a network library

    to start the echo server run:

        python -m example.echo

    you can then connect to it with telnet on port
    12345 and see your input echoed back.

    Notes:

        1. the on_open method is called when a connection is made
           to the server

        2. the id attribute contains a unique id for connection
           to the server. each add_server call to Network
           generates id values independently. in other words,
           handler ids are only unique within a server.

        3. the on_close method is called when the connection is
           closed

        4. the on_data method is called with the data most recently
           received on the connection
'''


class Echo(network.BasicHandler):

    def on_open(self):
        print('open cid=', self.id)

    def on_data(self, data):
        print('echo cid=', self.id, ':', data.strip())
        self.send(data)

    def on_close(self, reason):
        print('close cid=', self.id, ':', reason)


n = network.Server()
n.add_server(12345, Echo)  # an Echo object is created for each connection
print('echo server started on 12345 (CTRL-c to exit)')
while True:  # runs forever
    n.service()
