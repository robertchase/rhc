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
import os
import select
import socket
import ssl
import time


class ENOENTException(Exception):
    pass


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

        self._read_wait = {}
        self._write_wait = {}

    def _register(self, sock, is_read, callback):
        if is_read:
            self._read_wait[sock] = callback
            if sock in self._write_wait:
                del self._write_wait[sock]
        else:
            self._write_wait[sock] = callback
            if sock in self._read_wait:
                del self._read_wait[sock]

    def _unregister(self, sock):
        if sock in self._read_wait:
            del self._read_wait[sock]
        elif sock in self._write_wait:
            del self._write_wait[sock]

    def _set_pending(self, callback):
        self._pending.append(callback)

    def _service(self, timeout):
        processed = False
        self._pending = []

        read_wait = [s for s in self._read_wait.keys()]
        write_wait = [s for s in self._write_wait.keys()]
        readable, writeable, other = select.select(read_wait, write_wait, [], timeout)
        for s in readable:
            processed = True
            self._read_wait[s]()
        for s in writeable:
            processed = True
            self._write_wait[s]()

        for callback in self._pending:
            callback()
        return processed

    def close(self):
        for h in self.__readable:
            h.close()
        self.__readable = []
        for h in self.__writeable:
            h.close()
        self.__writeable = []

    def add_server(self, port, handler, context=None, ssl=None):
        '''
          Start a listening socket.

          Parameters:
            port    - listening port
            handler - name of handler class (subclass of BasicHandler)
            context - optional context associated with this listener
            ssl     - optional SSLParam
        '''
        Listener(port, handler, context, self.__readable, self.__handshake, ssl=ssl)

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
        h = handler(s, context)
        h.__incoming = False
        h._network = self
        h.name = '%s:%s' % address
        if ssl:
            ssl_ctx = ssl.create_default_context()  # ignore the SSLParams, and make our own context
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            h._ssl_ctx = ssl_ctx
        try:
            s.connect(address)
        except socket.error, e:
            error, errmsg = e
            if errno.EINPROGRESS == error:
                self._register(s, False, h._on_delayed_connect)
            else:
                h.on_fail()
                h.close_reason = 'failed to setup connection: %s' % errmsg
                h.close()
        else:
            h._on_connect()

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
    def __init__(self, keyfile=None, certfile=None, server_side=False, cert_reqs=ssl.CERT_NONE, ssl_version=ssl.PROTOCOL_TLSv1, ca_certs=None):
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
        self._sending = ''
        self._socket = socket
        self.__incoming = True
        self._ssl_ctx = None
        self._network = None

        self.name = 'BasicHandler::init'
        self.error = None
        self.close_reason = None
        self.txByteCount = 0
        self.rxByteCount = 0
        self.EINTR_cnt = 0
        self.EWOULDBLOCK_cnt = 0

        self.on_init()

    # --- SSL Support ---------------------------------------------------
    # ---
    # ---

    # ---
    # ---
    # --- Handler identifiers -------------------------------------------
    def address(self):
        try:
            return self._socket.getsockname()
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
    # --- I/O
    def _on_delayed_connect(self):
        try:
            rc = self._socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if rc != 0:
                self.error = os.strerror(rc)
        except Exception as e:
            self.error = str(e)
            rc = 1
        if rc == 0:
            self._on_connect()
        else:
            self.on_fail()
            self.close_error = 'failed to connect'
            self.close()

    def _on_connect(self):
        self.on_open()
        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # bye bye NAGLE
        if self._ssl_ctx:
            try:
                self._socket = self._ssl_ctx.wrap_socket(self._socket, server_side=self.is_inbound, do_handshake_on_connect=False)
            except Exception as e:
                self.close_reason = str(e)
                self.close()
            else:
                self._do_handshake()
        else:
            self._on_ready()

    def _do_handshake(self):
        try:
            self._socket.do_handshake()
        except ssl.SSLWantReadError:
            self._network._register(self._socket, True, self._do_handshake)
        except ssl.SSLWantWriteError:
            self._network._register(self._socket, False, self._do_handshake)
        except Exception as e:
            self.on_failed_handshake(str(e))
            self.close('failed ssl handshake')
        else:
            self.peer_cert = self._socket.getpeercert()
            if not self.on_handshake(self.peer_cert):
                self.close_reason = 'failed ssl certificate check'
                self.close()
                return
            self._on_ready()

    def _on_ready(self):
        self._network._register(self._socket, True, self._do_read)
        self.on_ready()

    @property
    def _is_pending(self):
        return self._ssl_ctx is not None and self._sock.pending()

    def _do_read(self):
        try:
            data = self._socket.recv(self.RECV_LEN)
        except ssl.SSLWantReadError:
            self._network._register(self._socket, True, self._do_read)
        except ssl.SSLWantWriteError:
            self._network._register(self._socket, False, self._do_read)
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
                self.rxByteCount += len(data)
                self.on_data(data)
                if self._is_pending:
                    self._network._set_pending(self._do_read)  # give buffered ssl data another chance

    def _do_write(self, data=None):
        data = data if data is not None else self._sending
        if not data:
            self.close('logic error in handler')
            return
        try:
            l = self._sock.send(data)
        except ssl.SSLWantReadError:
            self._network._register(self._socket, True, self._do_write)
        except ssl.SSLWantWriteError:
            self._network._register(self._socket, False, self._do_write)
        except socket.error as e:
            errnum, errmsg = e
            if errnum in (errno.EINTR, errno.EWOULDBLOCK):
                self.on_send_error(errmsg)  # not fatal
                self._sending = data
                self._network._register(self._socket, False, self._do_write)
            else:
                self.close('send error on socket: %s' % errmsg)
        except Exception as e:
            self.close('send error on socket: %s' % str(e))
        else:
            self.tx_count += l
            if l == len(data):
                self._sending = b''
                self._register(self._socket, False, self._do_write)
                self.on_send_complete()
            else:
                '''
                    we couldn't send all the data. buffer the remainder in self._sending and start
                    waiting for the socket to be writable again (EVENT_WRITE).
                '''
                self._sending = data[l:]
                self._register(self._socket, False, self._do_write)
    # --- I/O
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

    def _on_close(self):
        pass

    def __close(self):
        if not self.closed:
            self.__closing = False
            self.closed = True
            if self.__socket:
                self.__socket.close()
            self._on_close()  # for libraries
            self.on_close()
    # --- Close Methods -------------------------------------------------
    # ---
    # ---

    # --- SEND
    @property
    def _is_sending(self):
        return len(self._sending) != 0

    def send(self, data):
        if self._is_sending:
            self._sending += data
        else:
            self._do_write(data)

    def _send(self):
        '''
          Send data on socket.

          The socket.send function does not have to send any of the specified data.
          This method manages a buffer of data and sends as much as socket.send
          will allow each time the method is called. If socket.send only performs
          a partial send, then calls to SERVER.service() will re-call this method
          until all data is sent. This method ensures that multiple calls will
          maintain the order of the data.

          Note that the data buffer is managed as a list of strings. If the string
          types are encoded differently, as might be the case with http header and
          content strings, then combining them might be a problem. The send method
          allows for a string or a tuple of strings, and appends the data from
          each new call to the end of the buffer as separate strings.
        '''
        if len(self.__sending):
            count = 0
            try:
                while len(self.__sending):
                    data = self.__sending[0]
                    n = self.__socket.send(data)
                    count += n
                    if n == len(data):
                        self.__sending = self.__sending[1:]  # sent entire string
                    else:
                        if n > 0:
                            self.__sending[0] = data[n:]  # sent partial string
                        break  # come back later and try again
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

            except Exception as e:
                self.error = str(e)
                self.on_send_error()
                self.close_reason = 'send error on socket: %s' % self.error
                self.__close()

            if count:
                self.txByteCount += count
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
            if rc == 0:
                pass
            elif rc == errno.ECONNREFUSED:
                self.error = 'no listener at address'
            elif rc == errno.ENETUNREACH:
                self.error = 'network is unreachable'
            elif rc == errno.ECONNRESET:
                self.error = 'connection reset by peer'
            elif rc == errno.ETIMEDOUT:
                self.error = 'connection timeout'
            else:
                self.error = 'failed to connect, so_error=%d' % rc
        except Exception, e:
            self.error = str(e)
            rc = 1
        if rc == 0:
            if not self.on_opening():
                return 0
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
        if len(self.__sending) == 0:
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
            if h.on_opening():
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
