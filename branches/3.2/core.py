import ctypes.util
from ctypes import *
where = ctypes.util.find_library('ev')
assert where, 'core.py needs libev installed.'
libev = CDLL(where)
class Idle:
    def __init__(self):
        self.idle = idle = ev_idle()
        memmove(byref(idle), idle0, sizeof_idle)
        id_ = c_uint(id(self)).value
        objects[id_] = ref(self)

    def __del__(self):
        if self.idle.active:
            ev_idle_stop(EV_DEFAULT_UC, byref(self.idle))
        id_ = c_uint(id(self)).value
        if id_ in objects:
            del objects[id_]

    def __call__(self):
        self.co = co = getcurrent()
        ev_idle_start(EV_DEFAULT_UC, byref(self.idle))
        try:
            co.parent.switch()
        finally:
            ev_idle_stop(EV_DEFAULT_UC, byref(self.idle))
            self.co = None
        id_ = c_uint(id(self)).value
        if id_ in objects:
            del objects[id_]

    co = None

class Sleep:
    def __init__(self):
        self.timer = timer = ev_timer()
        memmove(byref(timer), sleep0, sizeof_idle)
        id_ = c_uint(id(self)).value
        objects[id_] = ref(self)

    def __del__(self):
        if self.timer.active:
            ev_timer_stop(EV_DEFAULT_UC, byref(self.timer))
        id_ = c_uint(id(self)).value
        if id_ in objects:
            del objects[id_]

    def __call__(self, seconds):
        self.co =  co = getcurrent()
        self.timer.at = seconds
        ev_timer_start(EV_DEFAULT_UC, byref(self.timer))
        try:
            co.parent.switch()
        finally:
            ev_timer_stop(EV_DEFAULT_UC, byref(self.timer))
            self.co = None

    co = None

class tcp_server_wrapper:
    def __init__(self, s, handler):
        self.handler = handler
        self.s = s
        self.srv = srv = ev_io()
        memmove(byref(srv), srv0, sizeof_io)
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

    def start(self, request_queue_size=8192):
        if not self.srv.active:
            ev_io_start(EV_DEFAULT_UC, byref(self.srv))

    def stop(self):
        if self.srv.active:
            ev_io_stop(EV_DEFAULT_UC, byref(self.srv))

    def serve_forever(self):
        self.start()
        ev_loop(EV_DEFAULT_UC, 0)

    def exit(self):
        self.stop()
        ev_unloop(EV_DEFAULT_UC, EVUNLOOP_ALL)

class Server(tcp_server_wrapper):
    def __init__(self, address, handler):
        attrs = bind(address, _socket.SOCK_STREAM)
        self.__dict__.update(attrs)
        tcp_server_wrapper.__init__(self, self.s, handler)

    def start(self, request_queue_size=8192):
        if not self.activated:
            self.s.listen(request_queue_size)
            self.activated = 1
        tcp_server_wrapper.start(self)

    activated = 0

class socket_wrapper:
    def __init__(self, s):
        self.cli = cli = Cli()
        memmove(byref(cli), cli0, sizeof_cli)
        cli.r_io.fd = cli.w_io.fd = cli.x_io.fd = \
            s.fileno()
        id_ = c_uint(id(self)).value
        cli.r_io.data = cli.w_io.data = cli.x_io.data = \
        cli.r_tm.data = cli.w_tm.data = cli.x_tm.data = id_
        objects[id_] = ref(self)
        self.s   = s
        self.buf = StringIO()

    def reading(self):
        return bool(self.cli.r_tm.active)

    def writing(self):
        return bool(self.cli.w_tm.active)

    reading = property(reading)
    writing = property(writing)

    def fileno(self):
        return self.s.fileno()

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

    def recv(self, size, timeout):
        id_ = c_uint(id(self)).value
        if id_ not in objects:
            return ''
        self.r_wait_with_timeout(timeout)
        try:
            return self.s.recv(size)
        except error as e:
            self.handle_r_error()
            if e.errno == ECONNRESET or \
               e.errno == ENOTCONN   or \
               e.errno == ESHUTDOWN:
                return ''

    def recvfrom(self, size, timeout):
        id_ = c_uint(id(self)).value
        if id_ not in objects:
            raise error(EPIPE, 'Broken pipe')
        self.r_wait_with_timeout(timeout)
        self.s.recvfrom(size)

    def send(self, data, timeout):
        id_ = c_uint(id(self)).value
        while 1:
            if id_ not in objects:
                raise error(EPIPE, 'Broken pipe')
            self.w_wait_with_timeout(timeout)
            try:
                return self.s.send(data)
            except error as e:
                if e.errno != EWOULDBLOCK:
                    self.handle_w_error()
                    raise

    def sendto(self, data, addr, timeout):
        id_ = c_uint(id(self)).value
        if id_ not in objects:
            raise error(EPIPE, 'Broken pipe')
        self.w_wait_with_timeout(timeout)
        self.s.sendto(data, addr)

    def read(self, size, timeout):
        return self.r_apply(self._read,
            timeout, [size], {})

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
                self.r_wait()
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

    def readline(self, size, timeout):
        return self.r_apply(self._readline,
            timeout, [size], {})

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
                self.r_wait()
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

    def write(self, data, timeout):
        cli = self.cli
        assert not cli.w_tm.active, 'write conflict'
        self.w_co = getcurrent()
        cli.w_tm.at = timeout
        ev_timer_start(EV_DEFAULT_UC, byref(cli.w_tm))
        try:
            pos  = 0
            left = len(data)
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
                        if EWOULDBLOCK != e[0]:
                            self.close()
                            raise
                finally:
                    ev_io_stop(EV_DEFAULT_UC, byref(cli.w_io))
        finally:
            ev_timer_stop(EV_DEFAULT_UC, byref(cli.w_tm))
            self.w_co = None

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

    code = '''def %(type)s_wait(self):
    ev_io_start(EV_DEFAULT_UC, byref(self.cli.%(type)s_io))
    try:
        self.%(type)s_co.parent.switch()
    finally:
        ev_io_stop(EV_DEFAULT_UC,
            byref(self.cli.%(type)s_io))

def %(type)s_apply(self, func, timeout, args=[], kwargs={}):
    cli = self.cli
    assert not cli.%(type)s_tm.active, '%(name)s conflict'
    self.%(type)s_co = getcurrent()
    cli.%(type)s_tm.at = timeout
    ev_timer_start(EV_DEFAULT_UC, byref(cli.%(type)s_tm))
    try:
        return func(*args, **kwargs)
    finally:
        ev_timer_stop(EV_DEFAULT_UC, byref(cli.%(type)s_tm))
        self.%(type)s_co = None

def %(type)s_wait_with_timeout(self, timeout):
    cli = self.cli
    assert not cli.%(type)s_tm.active, '%(name)s conflict'
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

class Client(socket_wrapper):
    def __init__(self, address, timeout):
        family, addr = addrinfo(address)
        if isinstance(addr, int):
            s = _socket.fromfd(addr, family,
                _socket.SOCK_STREAM)
            s.setblocking(0)
        else:
            s = _socket.socket(family, sock_type,
                _socket.SOCK_STREAM)
            s.setblocking(0)
            self.connect(addr)

def mainloop():
    ev_loop(EV_DEFAULT_UC, 0)

def serve_forever():
    ev_loop(EV_DEFAULT_UC, 0)

def exit():
    ev_unloop(EV_DEFAULT_UC, EVUNLOOP_ALL)

def bind(address, sock_type):
    family, addr = addrinfo(address)
    if isinstance(addr, int):
        s = _socket.fromfd(
            addr, family, sock_type)
        s.setblocking(0)
        activated = 1
    else:
        s = _socket.socket(family, sock_type)
        s.setblocking(0)
        activated = 0
        if _socket.AF_INET6 == family and \
                       '::' == addr[0]:
            s.setsockopt(
                _socket.IPPROTO_IPV6,
                _socket.IPV6_V6ONLY, 0)
        s.setsockopt(
            _socket.SOL_SOCKET,
            _socket.SO_REUSEADDR, 1)
        s.bind(addr)
    server_address = s.getsockname()
    if isinstance(server_address, tuple):
        host, server_port = server_address
        server_name = getfqdn(host)
    else:
        server_port = server_name = None
    return {'server_address': server_address,
            'server_name'   : server_name,
            'server_port'   : server_port,
            'sock_family'   : family,
            'sock_type'     : sock_type,
            'activated'     : activated,
            's'             : s}

def addrinfo(address):
    if isinstance(address, str):
        _ = is_ipv4_with_port(address)
        if _:
            host, port = _.groups()
            return _socket.AF_INET , (host, int(port))
        _ = is_ipv6_with_port(address)
        if _:
            host, port = _.groups()
            return _socket.AF_INET6, (host, int(port))
        _ = is_domain_with_port(address)
        if _:
            host, port = _.groups()
            return _socket.AF_INET , (host, int(port))
        raise ValueError(address)
    family, addr = address
    if _socket.AF_INET == family:
        if isinstance(addr, tuple):
            host, port = addr
            port = int(port)
            if not ((is_ipv4  (host)   or \
                     is_domain(host)) and \
                  0 <= port < 65536):
                raise ValueError(address)
            return _socket.AF_INET, (host, port)
        else:
            return _socket.AF_INET,  addr
    if _socket.AF_INET6 == family:
        if isinstance(addr, tuple):
            host, port = addr
            port = int(port)
            if not ((is_ipv6  (host)   or \
                     is_domain(host)) and \
                  0 <= port < 65536):
                raise ValueError(address)
            return _socket.AF_INET6, (host, port)
        else:
            return _socket.AF_INET6,  addr
        if _socket.AF_UNIX == family:
            if isinstance(addr_0, int):
                return _socket.AF_UNIX, addr
            elif isinstance(addr, str):
                return _socket.AF_UNIX, addr
            else:
                raise ValueError(address)
        raise ValueError(address)

def handle_request(l, w, e):
    id_ = w.contents.data
    srv = objects[id_]()
    sock, addr = srv.s.accept()
    sock.setblocking(0)
    greenlet(srv.handler).switch(socket_wrapper(sock), addr)

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

def idle_cb(l, w, e):
    id_ = w.contents.data
    idle = objects[id_]()
    if idle is not None and idle.co is not None:
        try:
            idle.co.switch()
        except:
            print_exc(file=sys.stderr)

def sleep_cb(l, w, e):
    id_ = w.contents.data
    timer = objects[id_]()
    if timer is not None and timer.co is not None:
        try:
            timer.co.switch()
        except:
            print_exc(file=sys.stderr)

def keyboard_interrupt_cb(l, w, e):
    ev_unloop(EV_DEFAULT_UC, EVUNLOOP_ALL)

def get_srv0():
    io, buf = ev_io(), create_string_buffer(sizeof_io)
    memset(byref(io), 0, sizeof_io)
    io.events = EV__IOFDSET | EV_READ
    io.cb = c_handle_request
    memmove(buf, byref(io), sizeof(ev_io))
    return buf

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

def get_idle0():
    idle, buf = ev_idle(), create_string_buffer(sizeof_idle)
    memset(byref(idle), 0, sizeof_idle)
    idle.cb = c_idle_cb
    memmove(buf, byref(idle), sizeof_idle)
    return buf

def get_sleep0():
    timer = ev_timer()
    buf = create_string_buffer(sizeof_timer)
    memset(byref(timer), 0, sizeof_timer)
    timer.cb = c_sleep_cb
    memmove(buf, byref(timer), sizeof_timer)
    return buf

def find_cb(type_):
    for k, v in type_._fields_:
        if 'cb' == k:
            return v

import re
import sys
from errno import *
from os import strerror
from weakref import ref
from signal import SIGINT
from traceback import print_exc
from socket import error, getfqdn
from greenlet  import greenlet, getcurrent
if 3 == sys.version_info[0]:
    import socket as  _socket
    from io import BytesIO as StringIO
    NEWLINE = bytes('\n', 'ascii')
else:
    import _socket
    from cStringIO import StringIO
    NEWLINE = '\n'
ev_tstamp, ev_loop_p = c_double, c_void_p
EV_UNDEF, EV_NONE, EV_READ, EV_WRITE, EV__IOFDSET = \
            -1, 0x00, 0x01, 0x02, 0x80
def EV_CB_DECLARE(type_):
    return CFUNCTYPE(None, c_void_p, POINTER(type_), c_int)

def EV_WATCHER(type_):
    return [('active'  , c_int), ('pending', c_int),
            ('priority', c_int), ('data', c_void_p),
            ('cb', EV_CB_DECLARE(type_))]

def EV_WATCHER_LIST(type_):
    return EV_WATCHER(type_) + [('next', ev_watcher_list_p)]

def EV_WATCHER_TIME(type_):
    return EV_WATCHER(type_) + [('at', ev_tstamp)]

class ev_watcher_list(Structure):
    pass

ev_watcher_list_p = POINTER(ev_watcher_list)
ev_watcher_list._fields_ = EV_WATCHER_LIST(ev_watcher_list)

class ev_io(Structure):
    pass

ev_io_p = POINTER(ev_io)
ev_io._fields_ = EV_WATCHER_LIST(ev_io) + \
    [('fd', c_int), ('events', c_int)]

class ev_timer(Structure):
    pass

ev_timer_p = POINTER(ev_timer)
ev_timer._fields_ = EV_WATCHER_TIME(ev_timer) + \
    [('repeat', ev_tstamp)]

class ev_signal(Structure):
    pass

ev_signal_p = POINTER(ev_signal)
ev_signal._fields_ = EV_WATCHER_LIST(ev_signal) + \
    [('signum', c_int)]

class ev_idle(Structure):
    pass

ev_idle_p = POINTER(ev_idle)
ev_idle._fields_ = EV_WATCHER(ev_idle)

def interface(name, restype, *argtypes):
    func = getattr(libev, name)
    func.restype, func.argtypes = restype, argtypes
    globals()[name] = func

if hasattr(libev, 'ev_default_loop_init'):
    interface('ev_default_loop_init', ev_loop_p, c_uint)
    ev_default_loop = ev_default_loop_init
else:
    interface('ev_default_loop', ev_loop_p, c_uint)
    ev_default_loop_init = ev_default_loop
EVLOOP_NONBLOCK, EVLOOP_ONESHOT, EVUNLOOP_CANCEL, \
    EVUNLOOP_ONE, EVUNLOOP_ALL = 1, 2, 0, 1, 2
EVRUN_NOWAIT   ,    EVRUN_ONCE ,  EVBREAK_CANCEL, \
    EVBREAK_ONE ,  EVBREAK_ALL = 1, 2, 0, 1, 2
if hasattr(libev, 'ev_loop'):
    interface('ev_loop'  , None, ev_loop_p, c_int)
    interface('ev_unloop', None, ev_loop_p, c_int)
    ev_run, ev_break = ev_loop, ev_unloop
else:
    interface('ev_run'  , None, ev_loop_p, c_int)
    interface('ev_break', None, ev_loop_p, c_int)
    ev_loop, ev_unloop = ev_run, ev_break
interface('ev_io_start', None, ev_loop_p, ev_io_p)
interface('ev_io_stop' , None, ev_loop_p, ev_io_p)
interface('ev_timer_start', None, ev_loop_p, ev_timer_p)
interface('ev_timer_stop' , None, ev_loop_p, ev_timer_p)
interface('ev_signal_start', None, ev_loop_p, ev_signal_p)
interface('ev_signal_stop' , None, ev_loop_p, ev_signal_p)
if hasattr(libev, 'ev_idle_start'):
    interface('ev_idle_start', None, ev_loop_p, ev_idle_p)
    interface('ev_idle_stop' , None, ev_loop_p, ev_idle_p)

class Cli(Structure):
    _fields_ = [('r_io', ev_io), ('r_tm', ev_timer),
                ('w_io', ev_io), ('w_tm', ev_timer),
                ('x_io', ev_io), ('x_tm', ev_timer)]

class Timeout(_socket.timeout):
    num_sent = 0

for type_ in 'rwx':
    exec(('c_%s_io_cb = find_cb(ev_io   )(%s_io_cb)\n'
          'c_%s_tm_cb = find_cb(ev_timer)(%s_tm_cb)'
    ) % tuple([type_] * 4))
del type_
c_idle_cb        = find_cb(ev_idle )(  idle_cb     )
c_sleep_cb       = find_cb(ev_timer)( sleep_cb     )
c_handle_request = find_cb(ev_io   )(handle_request)
c_keyboard_interrupt_cb = find_cb(ev_signal)(
        keyboard_interrupt_cb)
sizeof_io, sizeof_cli, sizeof_idle, sizeof_timer = (
    sizeof(ev_io), sizeof(Cli), sizeof(ev_idle),
                sizeof(ev_timer))
objects, srv0, cli0, idle0, sleep0 = \
    {}, get_srv0(), get_cli0(), get_idle0(), get_sleep0()
port = (r'6553[0-5]|655[0-2]\d|65[0-4]\d{2}|6[0-4]\d{3}|[1-5'
r']\d{4}|[1-9]\d{0,3}|0')
ipv4 = (r'(?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-4]'
r'|2[0-4]\d|1\d\d|[1-9]?\d)){3}')
ipv6 = (r'(?!.*::.*::)(?:(?!:)|:(?=:))(?:[0-9a-f]{0,4}(?:(?<'
r'=::)|(?<!::):)){6}(?:[0-9a-f]{0,4}(?:(?<=::)|(?<!::):)[0-9'
r'a-f]{0,4}(?:(?<=::)|(?<!:)|(?<=:)(?<!::):))')
domain = (r'(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z'
r']{2,6}')
is_ipv4   = re.compile(r'^\s*(%s)\s*$' % ipv4  ).match
is_ipv6   = re.compile(r'^\s*(%s)\s*$' % ipv6  ).match
is_domain = re.compile(r'^\s*(%s)\s*$' % domain).match
is_ipv4_with_port   = re.compile(
    r'^\s*(%s)\s*:\s*(%s)\s*$' % (ipv4, port)).match
is_ipv6_with_port   = re.compile(
    r'^\s*\[\s*(%s)\s*]\s*:\s*(%s)\s*$' % (ipv6, port)).match
is_domain_with_port = re.compile(
    r'^\s*(%s)\s*:\s*(%s)\s*$' % (domain, port)).match
EV_DEFAULT_UC = ev_default_loop_init(0)
keyboard_interrupt = ev_signal(0, 0, 0, None,
    c_keyboard_interrupt_cb, None, SIGINT)
ev_signal_start(EV_DEFAULT_UC, byref(keyboard_interrupt))
