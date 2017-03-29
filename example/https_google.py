import rhc.tcpsocket as network

from example.http_google import Google


n = network.Server()
c = n.add_connection(('www.google.com', 443), Google, ssl=True)
while c.is_open:
    n.service()
