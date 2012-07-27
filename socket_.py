import sys
import kbint
import _socket
from pyev  import *
from errno import *
from weakref import ref
from os import strerror
from socket import error
from traceback import print_exc
from exceptions_ import Timeout
from addrinfo import addrinfo, bind
from greenlet import greenlet, getcurrent
if 3 == sys.version_info[0]:
    from io import BytesIO as StringIO
    from _socket import socket as realsocket
    NEWLINE = bytes('\n', 'ascii')
else:
    from cStringIO import StringIO
    NEWLINE = '\n'

class TCPServerWrapper:
    def __init__(self, s, handler):
        self.handler = handler
        self.s = s
        self.srv = srv = ev_io()
        memmove(byref(srv), tcpsrv0, sizeof_io)
        srv.fd = s.fileno()
        id_ = c_uint(id(self)).value
        srv.data = id_
        objects[id_] = ref(self)

    def __del__(self):
        try:
            if self.srv.active:
                ev_io_stop(EV_DEFAULT_UC, byref(self.srv))
            id_ = c_uint(id(self)).value
            del objects[id_]
        except:
            pass

    def fileno(self):
        return self.s.fileno()

    def close(self):
        if self.srv.active:
            ev_io_stop(EV_DEFAULT_UC, byref(self.srv))

    def start(self):
        if not self.srv.active:
            ev_io_start(EV_DEFAULT_UC, byref(self.srv))

    def stop(self):
        if self.srv.active:
            ev_io_stop(EV_DEFAULT_UC, byref(self.srv))

    def serve_forever(self, flags=0):
        self.start()
        run(flags)

    def exit(self, how=EVBREAK_ALL):
        self.stop()
        break_(how)

class SocketWrapper:
    def __init__(self, s):
        self.cli = cli = Cli()
        memmove(byref(cli), cli0, sizeof_cli)
        cli.r_io.fd = cli.w_io.fd = cli.x_io.fd = s.fileno()
        id_ = c_uint(id(self)).value
        cli.r_io.data = cli.w_io.data = cli.x_io.data = \
        cli.r_tm.data = cli.w_tm.data = cli.x_tm.data = id_
        objects[id_] = ref(self)
        self.s   = s
        self.buf = StringIO()

    def reading(self):
        return bool(self.cli.r_tm.active)

    reading = property(reading)

    def writing(self):
        return bool(self.cli.w_tm.active)

    writing = property(writing)

    def fileno(self):
        return self.s.fileno()

    def dup(self):
        return SocketWrapper(self.s)

    def bind(self, addr):
        self.s.bind(addr)

    def listen(self, request_queue_size=8192):
        self.s.listen(request_queue_size)

    if 3 == sys.version_info[0]:
        def accept(self, timeout):
            id_ = c_uint(id(self)).value
            if id_ not in objects:
                raise error(EPIPE, 'Broken pipe')
            s = self.s
            self.r_wait(timeout)
            try:
                fd, addr = s._accept()
            except error as e:
                self.handle_r_error()
                raise
            c = realsocket(s.family, s.type, s.proto,
                           fileno=fd)
            c.setblocking(0)
            return SocketWrapper(c), addr
    else:
        def accept(self, timeout):
            id_ = c_uint(id(self)).value
            if id_ not in objects:
                raise error(EPIPE, 'Broken pipe')
            self.r_wait(timeout)
            try:
                s, addr = self.s.accept()
            except error as e:
                self.handle_r_error()
                raise
            s.setblocking(0)
            return SocketWrapper(s), addr

    def connect(self, addr, timeout):
        e = self.s.connect_ex(addr)
        if EALREADY == e or EINPROGRESS == e or \
           EISCONN  == e or EWOULDBLOCK == e:
            id_ = c_uint(id(self)).value
            if id_ not in objects:
                raise error(EPIPE, 'Broken pipe')
            self.x_wait(timeout)
            e = self.s.connect_ex(addr)
        if 0 == e or EISCONN == e:
            return
        raise error(e, strerror(e))

    def recvfrom(self, size, timeout):
        id_ = c_uint(id(self)).value
        if id_ not in objects:
            raise error(EPIPE, 'Broken pipe')
        self.r_wait(timeout)
        self.s.recvfrom(size)

    def sendto(self, data, addr, timeout):
        id_ = c_uint(id(self)).value
        if id_ not in objects:
            raise error(EPIPE, 'Broken pipe')
        self.w_wait(timeout)
        self.s.sendto(data, addr)

    def recv(self, size, timeout):
        id_ = c_uint(id(self)).value
        if id_ not in objects:
            return ''
        self.r_wait(timeout)
        try:
            return self.s.recv(size)
        except error as e:
            self.handle_r_error()
            if e.errno == ECONNRESET or \
               e.errno == ENOTCONN   or \
               e.errno == ESHUTDOWN:
                return ''

    def send(self, data, timeout):
        id_ = c_uint(id(self)).value
        while 1:
            if id_ not in objects:
                raise error(EPIPE, 'Broken pipe')
            self.w_wait(timeout)
            try:
                return self.s.send(data)
            except error as e:
                if e.errno != EWOULDBLOCK:
                    self.handle_w_error()
                    raise

    def read(self, size, timeout=-1):
        if -1 == timeout:
            self.r_co = getcurrent()
            try:
                return self._read(size)
            finally:
                self.r_co = None
        else:
            assert self.r_co is None, 'read conflict'
            cli = self.cli
            self.r_co = getcurrent()
            cli.r_tm.at = timeout
            ev_timer_start(EV_DEFAULT_UC, byref(cli.r_tm))
            try:
                return self._read(size)
            finally:
                ev_timer_stop(EV_DEFAULT_UC, byref(cli.r_tm))
                self.r_co = None

    def _read(self, size):
        buf = self.buf
        buf.seek(0, 2)
        bufsize = buf.tell()
        if bufsize >= size:
            buf.seek(0)
            rv = buf.read(size)
            self.buf = StringIO()
            self.buf.write(buf.read())
            return rv
        self.buf = StringIO()
        id_ = c_uint(id(self)).value
        while 1:
            if id_ not in objects:
                return buf.getvalue()
            left = size - bufsize
            try:
                self._r_wait()
            except Timeout:
                self.buf = buf
                raise
            try:
                data = self.s.recv(left)
            except error as e:
                if e.errno == ECONNRESET or \
                   e.errno == ENOTCONN   or \
                   e.errno == ESHUTDOWN:
                    self.close()
                    return buf.getvalue()
                raise
            if not data:
                break
            n = len(data)
            if n == size and not bufsize:
                return data
            if n == left:
                buf.write(data)
                del data
                break
            buf.write(data)
            bufsize += n
            del data
        return buf.getvalue()

    def readline(self, size, timeout=-1):
        if -1 == timeout:
            self.r_co = getcurrent()
            try:
                return self._readline(size)
            finally:
                self.r_co = None
        else:
            assert self.r_co is None, 'read conflict'
            cli = self.cli
            self.r_co = getcurrent()
            cli.r_tm.at = timeout
            ev_timer_start(EV_DEFAULT_UC, byref(cli.r_tm))
            try:
                return self._readline(size)
            finally:
                ev_timer_stop(EV_DEFAULT_UC, byref(cli.r_tm))
                self.r_co = None

    def _readline(self, size):
        buf = self.buf
        buf.seek(0, 2)
        if buf.tell() > 0:
            buf.seek(0)
            bline = buf.readline(size)
            if bline.endswith(NEWLINE) or \
               len(bline) == size:
                self.buf = StringIO()
                self.buf.write(buf.read())
                return bline
            del bline
            buf.seek(0, 2)
        bufsize = buf.tell()
        if bufsize >= size:
            buf.seek(0)
            rv = buf.read(size)
            self.buf = StringIO()
            self.buf.write(buf.read())
            return rv
        self.buf = StringIO()
        id_ = c_uint(id(self)).value
        while 1:
            if id_ not in objects:
                return buf.getvalue()
            try:
                self._r_wait()
            except Timeout:
                self.buf = buf
                raise
            try:
                data = self.s.recv(8192)
            except error as e:
                if e.errno == ECONNRESET or \
                   e.errno == ENOTCONN   or \
                   e.errno == ESHUTDOWN:
                    self.close()
                    return buf.getvalue()
                raise
            if not data:
                break
            left = size - bufsize
            nl = data.find(NEWLINE, 0, left)
            if nl >= 0:
                nl += 1
                self.buf.write(data[nl:])
                if bufsize:
                    buf.write(data[:nl])
                    break
                else:
                    return data[:nl]
            n = len(data)
            if n == size and not bufsize:
                return data
            if n >= left:
                buf.write(data[:left])
                self.buf.write(data[left:])
                break
            buf.write(data)
            bufsize += n
        return buf.getvalue()

    def write(self, data, timeout=-1):
        assert self.w_co is None, 'write conflict'
        pos  = 0
        cli  = self.cli
        left = len(data)
        self.w_co = getcurrent()
        if -1 == timeout:
            try:
                while pos < left:
                    ev_io_start(EV_DEFAULT_UC, byref(cli.w_io))
                    try:
                        self.w_co.switch()
                        try:
                            pos += self.s.send(
                                data[pos:pos+8192])
                        except error as e:
                            if EWOULDBLOCK != e.errno:
                                self.close()
                                raise
                    finally:
                        ev_io_stop(EV_DEFAULT_UC, byref(cli.w_io))
            finally:
                self.w_co = None
        else:
            cli.w_tm.at = timeout
            ev_timer_start(EV_DEFAULT_UC, byref(cli.w_tm))
            try:
                while pos < left:
                    ev_io_start(EV_DEFAULT_UC, byref(cli.w_io))
                    try:
                        try:
                            self.w_co.switch()
                        except Timeout as e:
                            e.num_sent = pos
                            raise e
                        try:
                            pos += self.s.send(
                                data[pos:pos+8192])
                        except error as e:
                            if EWOULDBLOCK != e.errno:
                                self.close()
                                raise
                    finally:
                        ev_io_stop(EV_DEFAULT_UC, byref(cli.w_io))
            finally:
                ev_timer_stop(EV_DEFAULT_UC, byref(cli.w_tm))
                self.w_co = None

    def flush(self, timeout=-1):
        pass

    def handle_r_error(self):
        cli = self.cli
        if cli.w_tm.active:
            if cli.w_io.active:
                self.w_co.throw(error,
                    error(EPIPE, 'Broken pipe'))
            else:
                ev_timer_stop(EV_DEFAULT_UC,
                    byref(cli.w_tm))
        self.s.close()

    def handle_w_error(self):
        cli = self.cli
        if cli.r_tm.active:
            if cli.r_io.active:
                self.r_co.throw(error,
                    error(EPIPE, 'Broken pipe'))
            else:
                ev_timer_stop(EV_DEFAULT_UC,
                    byref(cli.r_tm))
        self.s.close()

    code = '''def %s(self):
    cli = self.cli
    if cli.w_tm.active:
        if cli.w_io.active:
            self.w_co.throw(error,
                error(EPIPE, 'Broken pipe'))
        else:
            ev_timer_stop(EV_DEFAULT_UC,
                byref(cli.w_tm))
    if cli.r_tm.active:
        if cli.r_io.active:
            self.r_co.throw(error,
                error(EPIPE, 'Broken pipe'))
        else:
            ev_timer_stop(EV_DEFAULT_UC,
                byref(cli.r_tm))
    self.s.close()
    id_ = c_uint(id(self)).value
    if id_ in objects:
        del objects[id_]'''
    for func in ['__del__', 'close']:
        exec(code % func)

    code = '''def _%(type)s_wait(self):
    ev_io_start(EV_DEFAULT_UC, byref(self.cli.%(type)s_io))
    try:
        self.%(type)s_co.parent.switch()
    finally:
        ev_io_stop(EV_DEFAULT_UC,
            byref(self.cli.%(type)s_io))
def %(type)s_wait(self, timeout):
    assert self.%(type)s_co is None, '%(name)s conflict'
    cli = self.cli
    self.%(type)s_co = co = getcurrent()
    cli.%(type)s_tm.at = timeout
    ev_timer_start(EV_DEFAULT_UC, byref(cli.%(type)s_tm))
    ev_io_start(EV_DEFAULT_UC, byref(cli.%(type)s_io))
    try:
        co.parent.switch()
    finally:
        ev_io_stop(EV_DEFAULT_UC, byref(cli.%(type)s_io))
        ev_timer_stop(EV_DEFAULT_UC, byref(cli.%(type)s_tm))
        self.%(type)s_co = None'''
    for type_, name in [('r', 'read'), ('w', 'write'),
                        ('x', 'connect')]:
        exec(code % {'type': type_, 'name': name})
    del code, func, type_, name
    r_co = w_co = x_co = None

class TCPServer(TCPServerWrapper):
    def __init__(self, address, handler):
        attrs = bind(address, _socket.SOCK_STREAM)
        self.__dict__.update(attrs)
        TCPServerWrapper.__init__(self, self.s, handler)

    def start(self, request_queue_size=-1):
        if -1 == request_queue_size:
            request_queue_size = self.request_queue_size
        if not self.activated:
            self.s.listen(request_queue_size)
            self.activated = 1
        TCPServerWrapper.start(self)

    request_queue_size, activated = 8192, 0

Server = TCPServer

class TCPSocket(SocketWrapper):
    def __init__(self, address, timeout):
        family, addr = addrinfo(address)
        if isinstance(addr, int):
            s = _socket.fromfd(addr, family,
                _socket.SOCK_STREAM)
            s.setblocking(0)
            SocketWrapper.__init__(self, s)
        else:
            s = _socket.socket(family, sock_type,
                _socket.SOCK_STREAM)
            s.setblocking(0)
            SocketWrapper.__init__(self, s)
            self.connect(addr)

Socket = TCPSocket

class Cli(Structure):
    _fields_ = [('r_io', ev_io), ('r_tm', ev_timer),
                ('w_io', ev_io), ('w_tm', ev_timer),
                ('x_io', ev_io), ('x_tm', ev_timer)]

if 3 == sys.version_info[0]:
    def handle_request(l, w, e):
        id_ = w.contents.data
        srv = objects[id_]()
        s = srv.s
        fd, addr = s._accept()
        c = realsocket(s.family, s.type, s.proto,
                       fileno=fd)
        c.setblocking(0)
        greenlet(srv.handler).switch(SocketWrapper(c), addr)
else:
    def handle_request(l, w, e):
        id_ = w.contents.data
        srv = objects[id_]()
        s, addr = srv.s.accept()
        s.setblocking(0)
        greenlet(srv.handler).switch(SocketWrapper(s), addr)

code = '''def %(type)s_io_cb(l, w, e):
    id_ = w.contents.data
    cli = objects[id_]()
    if cli is not None and cli.%(type)s_co is not None:
        try:
            cli.%(type)s_co.switch()
        except:
            print_exc(file=sys.stderr)
def %(type)s_tm_cb(l, w, e):
    id_ = w.contents.data
    cli = objects[id_]()
    if cli is not None and cli.%(type)s_co is not None:
        try:
            cli.%(type)s_co.throw(
                Timeout,
                Timeout(ETIMEDOUT, '%(name)s timed out'))
        except:
            print_exc(file=sys.stderr)'''
for type_, name in [('r', 'read'), ('w', 'write'),
                    ('x', 'connect')]:
    exec(code % {'type': type_, 'name': name})
del code, name

def find_cb(type_):
    for k, v in type_._fields_:
        if 'cb' == k:
            return v

c_handle_request = find_cb(ev_io)(handle_request)

for type_ in 'rwx':
    exec(('c_%s_io_cb = find_cb(ev_io   )(%s_io_cb)\n'
          'c_%s_tm_cb = find_cb(ev_timer)(%s_tm_cb)'
    ) % tuple([type_] * 4))
del type_

def get_tcpsrv0():
    io, buf = ev_io(), create_string_buffer(sizeof_io)
    memset(byref(io), 0, sizeof_io)
    io.events = EV__IOFDSET | EV_READ
    io.cb = c_handle_request
    memmove(buf, byref(io), sizeof(ev_io))
    return buf

sizeof_io = sizeof(ev_io)
tcpsrv0 = get_tcpsrv0(); del get_tcpsrv0

def get_cli0():
    cli, buf = Cli(), create_string_buffer(sizeof_cli)
    memset(byref(cli), 0, sizeof_cli)
    cli.r_io.cb, cli.w_io.cb, cli.x_io.cb,  \
    cli.r_tm.cb, cli.w_tm.cb, cli.x_tm.cb = (
        c_r_io_cb, c_w_io_cb, c_x_io_cb,
        c_r_tm_cb, c_w_tm_cb, c_x_tm_cb)
    cli.r_io.events = EV__IOFDSET | EV_READ
    cli.w_io.events = EV__IOFDSET | EV_WRITE
    cli.x_io.events = EV__IOFDSET | EV_WRITE | EV_READ
    cli.r_tm.repeat = cli.w_tm.repeat = cli.x_tm.repeat = 0.
    memmove(buf, byref(cli), sizeof_cli)
    return buf

sizeof_cli = sizeof(Cli)
cli0 = get_cli0(); del get_cli0

objects = {}
exit = break_
mainloop = serve_forever = run
