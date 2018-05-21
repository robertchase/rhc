'''
The MIT License (MIT)

Copyright (c) 2013-2017 Robert H Chase

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
import os
import select
import socket
import ssl as ssl_library
import time


EVENT_READ = select.POLLIN | select.POLLPRI
EVENT_WRITE = select.POLLOUT


class Server(object):

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
        self._poll_map = {}
        self._poll = select.poll()
        self._id = 0

    @property
    def next_id(self):
        self._id += 1
        return self._id

    def add_server(self, port, handler, context=None, ssl=None, ssl_certfile=None, ssl_keyfile=None):
        '''
          Start a listening socket.

          Parameters:
            port    - listening port
            handler - name of handler class (subclass of BasicHandler)
            context - optional context associated with this listener
            ssl     - optional SSLParam, if this exists the keyfile and
                      certfile are the only values respected.
        '''
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        s.setblocking(False)
        s.listen(100)
        if ssl:
            ssl_ctx = ssl_library.create_default_context(purpose=ssl_library.Purpose.CLIENT_AUTH)
            if isinstance(ssl, SSLParam) and ssl.certfile:
                ssl_ctx.load_cert_chain(ssl.certfile, ssl.keyfile)
            if ssl_certfile:
                ssl_ctx.load_cert_chain(ssl_certfile, ssl_keyfile)
        else:
            ssl_ctx = None
        l = Listener(s, self, context=context, handler=handler, ssl_ctx=ssl_ctx)
        self._register(s, EVENT_READ, l._do_accept)
        return l

    def add_connection(self, address, handler, context=None, ssl=None, certfile=None, cafile=None):
        '''
          Connect to a listening socket.

          Parameters:
            address - (ip-address or name, port)
            handler - name of handler class (subclass of BasicHandler)
            context - optional context associated with connection
            ssl     - optional SSLParam, if this exists (not None or False)
                      then ssl will be setup using python defaults.
        '''
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(0)
        h = handler(s, context)
        h._incoming = False
        h._network = self
        h.name = '%s:%s' % address
        h.host = address[0]
        h.id = self.next_id
        if ssl:
            ssl_ctx = ssl_library.create_default_context()  # ignore the SSLParams, and make our own context
            ssl_ctx.check_hostname = False
            if certfile is not None:
                ssl_ctx.load_cert_chain(certfile)
            if cafile is not None:
                ssl_ctx.load_verify_locations(cafile)
            else:
                ssl_ctx.verify_mode = ssl_library.CERT_NONE
            h._ssl_ctx = ssl_ctx
        h.after_init()
        try:
            s.connect(address)
        except socket.error, e:
            error, errmsg = e
            if errno.EINPROGRESS == error:
                self._register(s, EVENT_WRITE, h._on_delayed_connect)
            else:
                h.on_fail()
                h.close_reason = 'failed to setup connection: %s' % errmsg
                h.close()
        else:
            h._on_connect()
        return h

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

          if max_iterations is set, it will limit the number of times the
          service loop will execute if network activity persists.
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

    def close(self):
        for _, sock in self._poll_map.values():
            try:
                sock.close()
            except Exception:
                pass

    def _register(self, sock, mask, callback):
        fileno = sock.fileno()
        if fileno in self._poll_map:
            self._poll.modify(fileno, mask)
        else:
            self._poll.register(fileno, mask)
        self._poll_map[fileno] = (callback, sock)

    def _unregister(self, sock):
        sock = sock.fileno()
        if sock in self._poll_map:
            self._poll.unregister(sock)
            del self._poll_map[sock]

    def _set_pending(self, callback):
        self._pending.append(callback)

    def _service(self, timeout):
        processed = False
        self._pending = []

        for sock, _ in self._poll.poll(timeout * 1000):
            processed = True
            self._poll_map[sock][0]()

        for callback in self._pending:
            callback()
        return processed


SERVER = Server()


class SSLParam(object):

    '''
      For using SSL with a client or server.

      *** Note comments in add_server and add_connection ***

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
    def __init__(self, keyfile=None, certfile=None, server_side=False, cert_reqs=ssl_library.CERT_NONE, ssl_version=ssl_library.PROTOCOL_TLSv1, ca_certs=None):
        self.keyfile = keyfile
        self.certfile = certfile
        self.server_side = server_side
        self.cert_reqs = cert_reqs  # CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED
        self.ssl_version = ssl_version
        self.ca_certs = ca_certs

    def set_ca_certs(self, ca_certs):
        self.cert_reqs = ssl_library.CERT_REQUIRED
        self.ca_certs = ca_certs


class BasicHandler(object):

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
        self._sending = ''
        self._sock = socket
        self._incoming = True
        self._ssl_ctx = None
        self._network = None

        self.name = 'BasicHandler::init'
        self.host = None
        self.error = None
        self.close_reason = None
        self.txByteCount = 0
        self.rxByteCount = 0
        self.EINTR_cnt = 0
        self.EWOULDBLOCK_cnt = 0

        self.t_init = time.time()
        self.t_open = 0
        self.t_ready = 0
        self.t_close = 0

        self.on_init()

    def send(self, data):
        if len(self._sending) != 0:
            self._sending += data
        else:
            self._do_write(data)

    def close(self, reason=None):
        if not self.closed:
            self.t_close = time.time()
            self.closed = True
            self._network._unregister(self._sock)
            if self._sock:
                self._sock.close()
            if reason:
                self.close_reason = reason
            self._on_close()  # for libraries
            self.on_close()

    def is_ssl(self):
        return self._ssl_ctx is not None

    @property
    def is_open(self):
        return not self.closed

    # ---
    # ---
    # --- Handler identifiers -------------------------------------------
    def address(self):
        try:
            return self._sock.getsockname()
        except socket.error:
            return ('Closing', 0)

    def peer_address(self):
        try:
            return self._sock.getpeername()
        except socket.error:
            return ('Closing', 0)

    def full_address(self):
        local = '%s:%s' % self.address()
        remote = '%s:%s' % self.peer_address()
        if self._incoming:
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
    def on_init(self):
        ''' called at the end of __init__ '''
        pass

    def after_init(self):
        ''' called after id assignment and ssl setup '''
        pass

    def on_accept(self):
        '''
          Called by a listening socket after accepting an incoming connection.

          Return None (or zero or False) to immediately close the socket, or
          anything else to begin handling activity on the socket during calls
          to Server.service.
        '''
        return True

    def on_failed_handshake(self, messsage):
        '''
          Called when ssl handshake fails.
          After return, on_close will be called.
        '''
        pass

    def on_fail(self):
        '''
          Called when outbound connection attempt fails; self.error will be set.
          After return, on_close will be called.
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
    # --- I/O
    def _on_delayed_connect(self):
        try:
            rc = self._sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if rc != 0:
                self.error = os.strerror(rc)
        except Exception as e:
            self.error = str(e)
            rc = 1
        if rc == 0:
            self._on_connect()
        else:
            self.close_reason = 'failed to connect'
            self.on_fail()
            self.close()

    def _on_connect(self):
        self.name = self.full_address()
        self.t_open = time.time()
        self.on_open()
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # bye bye NAGLE
        if self._ssl_ctx:
            try:
                self._sock = self._ssl_ctx.wrap_socket(self._sock, server_side=self._incoming, do_handshake_on_connect=False)
            except Exception as e:
                self.close_reason = str(e)
                self.close()
            else:
                self._do_handshake()
        else:
            self._on_ready()

    def _do_handshake(self):
        try:
            self._sock.do_handshake()
        except ssl_library.SSLWantReadError:
            self._network._register(self._sock, EVENT_READ, self._do_handshake)
        except ssl_library.SSLWantWriteError:
            self._network._register(self._sock, EVENT_WRITE, self._do_handshake)
        except Exception as e:
            self.on_failed_handshake(str(e))
            self.close_reason = 'failed ssl handshake'
            self.close()
        else:
            self.peer_cert = self._sock.getpeercert()
            if not self.on_handshake(self.peer_cert):
                self.close_reason = 'failed ssl certificate check'
                self.close()
                return
            self._on_ready()

    def _on_ready(self):
        self.t_ready = time.time()
        self._network._register(self._sock, EVENT_READ, self._do_read)
        self.on_ready()

    @property
    def _is_pending(self):
        return self._ssl_ctx is not None and self._sock.pending()

    def _do_read(self):
        try:
            data = self._sock.recv(self.RECV_LEN)
        except ssl_library.SSLWantReadError:
            self._network._register(self._sock, EVENT_READ, self._do_read)
        except ssl_library.SSLWantWriteError:
            self._network._register(self._sock, EVENT_WRITE, self._do_read)
        except socket.error as e:
            errnum, errmsg = e
            if errnum == errno.ENOENT:
                pass  # apparently this can happen. http://www.programcreek.com/python/example/374/errno.ENOENT says it comes from the SSL library.
            else:
                self.close_reason = 'recv error on socket: %s' % errmsg
                self.close()
        except Exception as e:
            self.close_reason = 'recv error on socket: %s' % str(e)
            self.close()
        else:
            if len(data) == 0:
                self.close_reason = 'remote close'
                self.close()
            else:
                self._network._register(self._sock, EVENT_READ, self._do_read)
                self.rxByteCount += len(data)
                self.on_data(data)
                if self._is_pending:
                    self._network._set_pending(self._do_read)  # give buffered ssl data another chance

    def _do_write(self, data=None):
        if data is None:
            data = self._sending
            self._sending = ''
        if not data:
            self.close_reason = 'logic error in handler'
            self.close()
            return
        try:
            l = self._sock.send(data)
        except ssl_library.SSLWantReadError:
            self._network._register(self._sock, EVENT_READ, self._do_write)
        except ssl_library.SSLWantWriteError:
            self._network._register(self._sock, EVENT_WRITE, self._do_write)
        except socket.error as e:
            errnum, errmsg = e
            if errnum in (errno.EINTR, errno.EWOULDBLOCK):
                self.error = errmsg
                self.on_send_error()  # not fatal
                self._sending = data
                self._network._register(self._sock, EVENT_WRITE, self._do_write)
            else:
                self.close('send error on socket: %s' % errmsg)
        except Exception as e:
            self.close('send error on socket: %s' % str(e))
        else:
            self.txByteCount += l
            if l == len(data):
                self._network._register(self._sock, EVENT_READ, self._do_read)
                self.on_send_complete()
            else:
                # we couldn't send all the data. buffer the remainder in self._sending and start
                # waiting for the socket to be writable again (EVENT_WRITE).
                self._sending = data[l:]
                self._network._register(self._sock, EVENT_WRITE, self._do_write)
    # --- I/O
    # ---
    # ---

    def _on_close(self):
        pass


class Listener(object):

    def __init__(self, socket, server, handler, context=None, ssl_ctx=None):
        self.socket = socket
        self.network = server
        self.handler = handler
        self.context = context
        self.ssl_ctx = ssl_ctx

    def close(self):
        ''' close a listening socket

            Normally, a listening socket lasts for for duration of a server's life. If
            there is a need to close a listener, this is the way to do it.
        '''
        self.network._unregister(self.socket)
        self.socket.close()

    def _do_accept(self):
        s, _ = self.socket.accept()
        s.setblocking(False)
        h = self.handler(s, self.context)
        h._network = self.network
        h._ssl_ctx = self.ssl_ctx
        h.id = self.network.next_id
        h.after_init()
        if h.on_accept():
            h._on_connect()
        else:
            h.close('connection not accepted')
