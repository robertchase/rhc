'''
The MIT License (MIT)

Copyright (c) 2013-2015 Robert H Chase

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
import errno
import select
import socket
import ssl
import time


class ENOENTException(Exception):
    pass


class Client(object):

    '''
      Synchronous client class for easy client creation.

      The connect is tried immediatedly on creation. The read and write functions
      poll until they are satisfied.
    '''
    def __init__(self, host, port):
        self.connection = None

        class Context(object):
            def __init__(self):
                self.handler = None
                self.done = False

        class Handler(BasicHandler):
            def __init__(self, socket, context=None):
                super(Handler, self).__init__(socket, context)
                self.data = ''

            def on_ready(self):
                self.context.done = True
                self.context.handler = self

            def on_close(self):
                self.context.done = True

            def on_fail(self):
                raise Exception('Connection to %s failed: %s' % (self.name, self.error))

            def on_data(self, data):
                self.data += data

        ctx = Context()
        Server().add_connection((host, port), Handler, ctx)
        while not ctx.done:
            Server().service()
            time.sleep(.01)

        self.connection = ctx.handler

    def write(self, data):
        self.connection.send(data)
        while self.connection.more_to_send():
            if self.connection.closed:
                raise Exception('Connection closed')
            Server().service()
            time.sleep(.01)

    def read(self, length=0):
        if length == 0:
            length = len(self.connection.data)
        while length > len(self.connection.data):
            if self.connection.closed:
                raise Exception('Connection closed')
            Server().service()
            time.sleep(.01)
        ret, self.connection.data = self.connection.data[:length], self.connection.data[length:]
        return ret


class Server (object):

    '''
      Async TCP socket handling for both inbound and outbound connections.

      Use add_server to add a listening socket, and add_connection to add a new
      outbound connection. Call the service method fairly frequently to respond
      to asynchronous network events.

      Logic for handling events on a connection is delegated to a handler
      class which extends BasicHandler. A new instantiation of the handler is
      allocated for each connection. An optional context is also permitted, one
      context shared for every socket on a listener, and one unshared context
      for each outbound connection.
    '''
    def __init__(self):
        self.__readable = []
        self.__writeable = []
        self.__handshake = []

    def close(self):
        for h in self.__readable:
            h.close()
        for h in self.__writeable:
            h.close()

    def add_server(self, port, handler, context=None, ssl=None):
        '''
          Start a listening socket.

          Parameters:
            port    - listening port
            handler - name of handler class (subclass of BasicHandler)
            context - optional context associated with this listener
            ssl     - optional SSLParam
        '''
        Listener(port, handler, context, self.__readable, self.__handshake,
                 ssl=ssl)

    def add_connection(self, address, handler, context=None, ssl=None):
        '''
          Connect to a listening socket.

          Parameters:
            address - (ip-address or name, port)
            handler - name of handler class (subclass of BasicHandler)
            context - optional context associated with connection
            ssl     - optional SSLParam
        '''
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(0)
        try:
            s.connect(address)
        except socket.error, e:
            error, errmsg = e
            if errno.EINPROGRESS != error:
                # --- temporarily construct a handler in order to fail/close it
                h = handler(0, context)
                h.name = '%s:%s' % address
                h.error = str(e)
                h.on_fail()
                h.close_reason = 'failed to setup connection'
                h.on_close()
                return
        h = handler(s, context)
        h.name = '%s:%s' % address
        if ssl:
            h.set_ssl(ssl)
        self.__writeable.append(h)

    def _service(self, delay):
        '''
          called from service until no work is left to be done. this enforces
          some fairness by moving round-robin through the sockets with work
          to do, performing one operation per socket on each _service call.
        '''

        # --- number of sockets with operations
        count = 0

        # --- these are closed, but not cleaned up yet
        for s in self.__readable:
            if s.closed:
                self.__readable.remove(s)
        for s in self.__handshake:
            if s.closed:
                self.__handshake.remove(s)

        # --- ssl sockets in handshake negotiation
        for s in self.__handshake:
            count += 1
            if s.ssl_do_handshake():
                self.__handshake.remove(s)
                self.__readable.append(s)

        # --- select sockets with activity
        readable, writeable, other = select.select(
            self.__readable, self.__writeable, [], delay
        )
        count += len(readable) + len(writeable)

        # --- handle one thing on each socket with activity
        for s in self.__readable:
            '''
              an ssl socket reads data in chunks meaning that a socket may
              appear to be empty (no data to read) even though there is more
              data in the ssl buffer. the pending method will tell us if
              ssl has some buffered data from a previously read chunk.

              the logic here looks at every socket in the potentially
              readable list and checks it for the presense of either data
              on the socket or pending data in the ssl buffer.
            '''
            if s in readable:
                s.readable()
            elif s.pending():
                count += 1
                s.readable()

        # --- outbound connections waiting for completion
        for s in writeable:
            if s.writeable():
                if s.is_ssl():
                    self.__handshake.append(s)
                else:
                    self.__readable.append(s)
            self.__writeable.remove(s)

        # --- select sockets waiting to write
        sending = [s for s in self.__readable if s.more_to_send()]
        readable, sendable, other = select.select([], sending, [], 0)
        for s in sendable:
            count += 1
            s._send()

        # --- zero when no sockets have activity
        return count

    def service(self, delay=0, max_iterations=0):
        '''
          exhaust all network activity (arriving data and
          connecting/disconnecting sockets).

          the value of delay will be used on the first call to select to block
          while waiting for network activity. the block will stop after delay
          seconds or when the first activity is detected.

          if activity is detected (and handled) on the first call to select,
          each socket will be given time to do one thing after which the
          process will continue until all activity is handled. on additional
          calls to select, the delay value will be zero (no delay).
        '''
        iterations = 0
        did_anything = False
        while (self._service(delay)):
            did_anything = True
            delay = 0
            if max_iterations:
                iterations += 1
                if iterations == max_iterations:
                    break
        return did_anything


SERVER = Server()


class SSLParam (object):

    '''
      For using SSL with a client or server.

      A server must provide a keyfile and certfile, as well as indicate
      server_side=True. A client need not specify anything
      unless certificate checking is required. In this case, a certificate
      authority file must be specified (ca_certs) and cert_reqs changed
      to the desired level of checking.

      The on_open method will be called at initial connection, and
      the on_handshake method will be called after ssl handshake is
      complete. If certificate checking is performed, a non-null
      certificate will be provided to the on_handshake method which can
      be rejected by returning a False.
    '''
    def __init__(self, keyfile=None, certfile=None, server_side=False,
                 cert_reqs=ssl.CERT_NONE, ssl_version=ssl.PROTOCOL_TLSv1, ca_certs=None):
        self.keyfile = keyfile
        self.certfile = certfile
        self.server_side = server_side
        self.cert_reqs = cert_reqs  # CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED
        self.ssl_version = ssl_version
        self.ca_certs = ca_certs

    def set_ca_certs(self, ca_certs):
        self.cert_reqs = ssl.CERT_REQUIRED
        self.ca_certs = ca_certs


class BasicHandler (object):

    '''
      Base class for connection listeners.
    '''
    def __init__(self, socket, context=None):
        self.RECV_LEN = 1024
        self.MAX_RECV_LEN = 0
        self.NAGLE = False
        self.start = time.time()
        self.context = context
        self.closed = False
        self.__closing = False
        self.__sending = ''
        self.__socket = socket
        self.__incoming = True

        self.name = 'BasicHandler::init'
        self.error = None
        self.close_reason = None
        self.txByteCount = 0
        self.rxByteCount = 0
        self.EINTR_cnt = 0
        self.EWOULDBLOCK_cnt = 0

        # ---
        # ---
        # --- SSL support -------------------------------------------------
        self.__ssl_param = None
        self.__ssl_peer_cert = None
        self.__ssl_want_read = False
        self.__ssl_want_write = False

    def get_ssl_peer_cert(self):
        return self.__ssl_peer_cert

    def is_ssl(self):
        if self.__ssl_param:
            return True
        return False

    def get_ssl_cipher(self):
        if self.is_ssl():
            return self.__socket.cipher()
        return None

    def set_ssl(self, ssl_param):
        '''
          Internal use.
        '''
        self.__ssl_param = ssl_param

    def ssl_do_handshake(self):
        '''
          Internal use.
        '''
        if self.__ssl_want_read:
            try:
                handle = self == select.select([self], [], [], 0)[0][0]
            except IndexError:
                handle = False
        elif self.__ssl_want_write:
            try:
                handle = self == select.select([], [self], [], 0)[1][0]
            except IndexError:
                handle = False
        else:
            handle = True
        if handle:
            self.__ssl_want_read = False
            self.__ssl_want_write = False
            try:
                self.__socket.do_handshake()
                self.__ssl_peer_cert = self.__socket.getpeercert()
            except ssl.SSLError, err:
                err = err.args[0]
                if ssl.SSL_ERROR_WANT_READ == err:
                    self.__ssl_want_read = True
                elif ssl.SSL_ERROR_WANT_WRITE == err:
                    self.__ssl_want_write = True
                else:
                    self.error = 'unexpected SSLError: code=%s' % str(err)
                    self.close()
                    return True
                return False
            except Exception, e:
                self.error = str(e)
                return True

            if not self.on_handshake(self.__ssl_peer_cert):
                self.error = 'on_handshake: invalid certificate'
                self.close()
            else:
                self.on_ready()
            return True

        return False
    # --- SSL Support ---------------------------------------------------
    # ---
    # ---

    # ---
    # ---
    # --- Handler identifiers -------------------------------------------
    def address(self):
        try:
            return self.__socket.getsockname()
        except socket.error:
            return ('Closing', 0)

    def peer_address(self):
        try:
            return self.__socket.getpeername()
        except socket.error:
            return ('Closing', 0)

    def full_address(self):
        local = '%s:%s' % self.address()
        remote = '%s:%s' % self.peer_address()
        if self.__incoming:
            direction = '<-'
        else:
            direction = '->'
        return '%s %s %s' % (local, direction, remote)

    def get_identifier(self):
        local = '%s:%s' % self.address()
        remote = '%s:%s' % self.peer_address()
        return '%s.%s.%s' % (local, remote, self.start)
    # --- Handler identifiers -------------------------------------------
    # ---
    # ---

    # ---
    # ---
    # --- Callback Methods ----------------------------------------------
    def on_accept(self):
        '''
          Called by a listening socket after accepting an incoming connection.

          Return None (or zero or False) to immediately close the socket, or
          anything else to begin handling activity on the socket during calls
          to Server.service.
        '''
        return True

    def on_opening(self):
        '''
          Before calling on_open, take the opportunity to perform some actions
          on the socket or handler.
        '''
        self.name = self.full_address()
        if not self.NAGLE:
            self.__socket.setsockopt(
                socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        if self.__ssl_param:
            self.__socket = ssl.wrap_socket(
                self.__socket,
                keyfile=self.__ssl_param.keyfile,
                certfile=self.__ssl_param.certfile,
                server_side=self.__ssl_param.server_side,
                cert_reqs=self.__ssl_param.cert_reqs,
                ssl_version=self.__ssl_param.ssl_version,
                ca_certs=self.__ssl_param.ca_certs,
                do_handshake_on_connect=False
            )
        self.on_open()
        if not self.is_ssl():
            self.on_ready()

    def on_fail(self):
        '''
          Called when outbound connection attempt fails; self.error will be set.
          After return on_close will be called.
        '''
        pass

    def on_open(self):
        '''
          Called on successful tcp connect.

          If this is an ssl connection, then the socket won't be ready for
          normal interaction until after the ssl handshake is complete. This is
          indicated by a call to the on_handshake method. For indication of
          socket ready for normal operations, see on_ready.
        '''
        pass

    def on_handshake(self, peer_cert):
        '''
          Called on successful completion of ssl handshake.

          If a peer certificate has been acquired in the process,
          this will be passed as a dictionary object which is
          the result of sslsocket.getpeercert(); otherwise,
          None is passed. If the certificate fails any tests that
          the on_handshake method performs, a False will close the
          socket; otherwise, return True.
        '''
        return True

    def on_ready(self):
        '''
          called after successful connect or, on ssl connection, after successful
          ssl handshake.
        '''
        pass

    def on_close(self):
        '''
          Called when the socket is closed.
        '''
        pass

    def on_data(self, data):
        '''
          Called when data is available.
        '''
        pass

    def on_send(self, bytes_sent):
        '''
          Called when some data is sent (socket.send, not self.send)
        '''
        pass

    def on_send_error(self):
        '''
          Called when socket send fails. Error message in self.error.
        '''
        pass

    def on_send_complete(self):
        '''
          Called when all the data in the application buffer has been sent.

          Data is cached in the application buffer whenever a call to the send
          method is not able to send all of the specified data. Whenever data is
          cached, the Server ().service () call will check to see if the socket
          becomes writable, and continue sending until the cache is empty.

          Under normal conditions, a call to the send method with a small amount
          of data to send will result in this method being called immediately.
        '''
        pass
    # --- Callback Methods ----------------------------------------------
    # ---
    # ---

    # ---
    # ---
    # --- Close Methods -------------------------------------------------
    def close(self):
        self.__close()

    def shutdown(self, how=None):
        '''
          Close the socket. If it is already in the process of closing, or already
          closed, don't do anything. If how is 'w', SHUT_WR will be specified,
          if how is 'r', SHUT_RD will be specified; otherwise SHUT_RDWR will be
          specified.

          When the socket becomes readable and and recv returns an emtpy string,
          or the socket becomes writable and send causes a socket error, then the
          socket, and Handler, will be fully closed.
        '''
        if not self.__closing:
            if not self.closed:

                if 'w' == how:
                    how = socket.SHUT_WR
                elif 'r' == how:
                    how = socket.SHUT_RD
                else:
                    how = socket.SHUT_RDWR

                self.__closing = True
                self.__socket.shutdown(how)

    def __close(self):
        if not self.closed:
            self.__closing = False
            self.closed = True
            if self.__socket:
                self.__socket.close()
            self.on_close()
    # --- Close Methods -------------------------------------------------
    # ---
    # ---

    # --- SEND
    def send(self, data):
        self._send(data)

    def _send(self, data=None):
        '''
          Send data on socket.

          The socket.send function does not have to send any of the specified data.
          This method buffers data and sends as much as socket.send will allow
          each time the method is called. If socket.send only performs a partial
          send, then calls to Server ().service () will re-call this method until
          all data is sent. This method ensures that multiple calls will maintain
          the order of the data.
        '''
        if data:
            self.__sending += data

        count = 0
        if len(self.__sending):
            try:
                count = self.__socket.send(self.__sending)
            except socket.error, e:
                errnum, errmsg = e

                if errno.EINTR == errnum:
                    self.EINTR_cnt += 1

                elif errno.EWOULDBLOCK == errnum:
                    self.EWOULDBLOCK_cnt += 1

                else:
                    self.error = str(e)
                    self.on_send_error()
                    self.close_reason = 'send error on socket'
                    self.__close()

            if count:
                self.txByteCount += count
                self.__sending = self.__sending[count:]
                self.on_send(count)

                if not self.more_to_send():
                    self.on_send_complete()

    # ---
    # ---
    # --- Service Methods -----------------------------------------------
    def recv(self):
        length = self.RECV_LEN
        if self.MAX_RECV_LEN > 0:
            if length > self.MAX_RECV_LEN:
                length = self.MAX_RECV_LEN
        if length < 1:
            self.close_reason = 'length error'
            self.error = 'Invalid length: %s' % length
            return None
        try:
            data = self.__socket.recv(length)  # read up to 'len' bytes
        except socket.error, e:                # socket closed

            # this error doesn't make sense, but can happen.
            # treat like EWOULDBLOCK by raising Exception to caller.
            if e.args[0] == errno.ENOENT:
                raise ENOENTException()

            self.close_reason = 'socket error'
            self.error = e
            return None                        # socket closed on error
        if data:
            self.rxByteCount += len(data)
        else:
            self.close_reason = 'remote close'
        return data

    def readable(self):
        '''
          A zero-length read from a readable socket indicates a socket close
          event. If the peer socket performed a SHUT_WR, then it would still be
          possible to send data to the peer. This method, therefore, will not
          close the socket unless zero data is read from the socket AND there is
          no more data to send. If the peer performed a hard close or a SHUT_RDWR,
          then the next attempt to send remaining data would indicate a socket
          problem and things will be properly closed (see the send method).
        '''
        try:
            data = self.recv()
        except ENOENTException:
            return
        if data:
            self.on_recv(data)
        elif not self.more_to_send():
            self.__close()

    def on_recv(self, data):
        self.on_data(data)

    def writeable(self):
        self.__incoming = False
        try:
            rc = self.__socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if 0 == rc:
                pass
            elif errno.ECONNREFUSED == rc:
                self.error = 'no listener at address'
            elif errno.ENETUNREACH == rc:
                self.error = 'network is unreachable'
            elif errno.ECONNRESET == rc:
                self.error = 'connection reset by peer'
            elif errno.ETIMEDOUT == rc:
                self.error = 'connection timeout'
            else:
                self.error = 'failed to connect, so_error=%d' % rc
        except Exception, e:
            self.error = str(e)
            rc = 1
        if 0 == rc:
            self.on_opening()
            return 1
        self.on_fail()
        self.close_reason = 'failed to connect'
        self.__close()
        return 0

    def fileno(self):  # used by select
        try:
            fileno = self.__socket.fileno()
        except socket.error:
            return 0
        return fileno

    def pending(self):
        if self.is_ssl():
            return self.__socket.pending()
        return False

    def more_to_send(self):
        if 0 == len(self.__sending):
            return False
        return True
    # --- Service Methods -----------------------------------------------
    # ---
    # ---


class Listener:

    def __init__(self, port, handler, context, readable, handshake, ssl=None,
                 listen=True):
        self.__handler = handler
        self.__context = context
        self.__readable = readable
        self.__handshake = handshake
        self.__ssl = ssl
        self.closed = False
        s = self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        s.setblocking(0)
        if listen:
            self.listen()

    def listen(self):
        self.__socket.listen(10)
        self.__readable.append(self)

    def close(self):
        if self.__socket:
            self.__socket.close()
        self.closed = True

    def fileno(self):
        return self.__socket.fileno()

    def readable(self):
        s, address = self.__socket.accept()
        s.setblocking(0)
        h = self.__handler(s, self.__context)
        if h.on_accept():
            if self.__ssl:
                h.set_ssl(self.__ssl)
            h.on_opening()
            if self.__ssl:
                self.__handshake.append(h)
            else:
                self.__readable.append(h)
        else:
            h.close()

    def pending(self):
        return False

    def more_to_send(self):
        return False
