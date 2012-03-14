import sys
import kbint
import _socket
from pyev import *
from weakref import ref
from greenlet import greenlet
from scheduler import Idle, Sleep
from sockwrap import SocketWrapper
from addrinfo import addrinfo, bind

class ServerWrapper:
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

class Server(ServerWrapper):
    def __init__(self, address, handler):
        attrs = bind(address, _socket.SOCK_STREAM)
        self.__dict__.update(attrs)
        ServerWrapper.__init__(self, self.s, handler)

    def start(self, request_queue_size=-1):
        if -1 == request_queue_size:
            request_queue_size = self.request_queue_size
        if not self.activated:
            self.s.listen(request_queue_size)
            self.activated = 1
        ServerWrapper.start(self)

    request_queue_size, activated = 8192, 0

class Socket(SocketWrapper):
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

if 3 == sys.version_info[0]:
    from _socket import socket as realsocket
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

def get_srv0():
    io, buf = ev_io(), create_string_buffer(sizeof_io)
    memset(byref(io), 0, sizeof_io)
    io.events = EV__IOFDSET | EV_READ
    io.cb = c_handle_request
    memmove(buf, byref(io), sizeof(ev_io))
    return buf

for field, cb in ev_io._fields_:
    if 'cb' == field:
        c_handle_request = cb(handle_request)

sizeof_io = sizeof(ev_io)
objects, srv0 = {}, get_srv0()

TCPServer = Server
TCPSocket = Client = Socket

exit = break_
mainloop = serve_forever = run
