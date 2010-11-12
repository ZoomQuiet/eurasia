from os import strerror
from core import file, exit, mainloop, timeout
from errno import EALREADY, EINPROGRESS, EISCONN, EWOULDBLOCK
from _socket import fromfd as realfromfd, socket as realsocket

import socket as stdsocket
from socket import __all__, _fileobject
for k, v in stdsocket.__dict__.items():
    if k in __all__:
        globals()[k] = v
try:
    import _ssl
    from _ssl import sslwrap as realsslwrap
except ImportError:
    _ssl = None

def install():
    stdsocket._realsocket = fakesocket
    if _ssl:
        _ssl.sslwrap = fakesslwrap

def uninstall():
    stdsocket._realsocket = realsocket
    if _ssl:
        _ssl.sslwrap = realsslwrap

def fromfd(fd, family=AF_INET, type=SOCK_STREAM, proto=0):
    '''fromfd(fd, family, type[, proto]) -> socket object

    Create a socket object from a duplicate of the given
    file descriptor.
    The remaining arguments are the same as for socket().
    '''
    return fakesocket(_sock=realfromfd(fd, family, type, proto))

def create_connection(address, timeout=-1):
    '''Connect to *address* and return the socket object.'''
    msg = 'getaddrinfo returns an empty list'
    host, port = address
    for res in getaddrinfo(host, port, 0, SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            sock = fakesocket(af, socktype, proto)
            sock.connect(sa, timeout)
            return sock
        except error, msg:
            if sock is not None:
                sock.close()
    raise msg

class fakesocket(file):

    __doc__ = realsocket.__doc__

    def __init__(self, family=AF_INET, type=SOCK_STREAM, proto=0, _sock=None):
        self._sock = sock = _sock or realsocket(family, type, proto)
        file.__init__(self, sock.fileno())
        self._recv  = sock.recv
        self._send  = sock.send
        self._close = sock.close

    def __iter__(self):
        return self

    def dup(self):
        '''dup() -> socket object

        Return a new socket object connected to the same system resource.'''
        return fakesocket(_sock=self._sock)

    def connect(self, addr, timeout=-1):
        e = self._sock.connect_ex(addr)
        if e in econn_noerr:
            self.ready(timeout)
            e = self._sock.connect_ex(addr)
        if e == 0 or e == EISCONN:
            return
        raise error(e, strerror(e))
    connect.__doc__ = realsocket.connect.__doc__

    def makefile(self, *args):
        '''makefile() -> file object

        Return a regular file object corresponding to the socket.
        '''
        obj = fakesocket(_sock=self._sock)
        obj.releasable = 1
        return obj
    releasable = 0

    def close(self):
        '''close()

        Close the socket.  It cannot be used after this call.
        '''
        if self.releasable:
            self._recv = self._send = self._close = _bad_file_descriptor
            self.closed = 1
            del self._sock
            self.f = -1
        elif not self.closed:
            self._close()
            self.closed = 1
            self.f = -1

    def writelines(self, lst, timeout=-1):
        self.sendall(''.join(lst), timeout)

    def flush(self, timeout=-1):
        pass

    def _not_implemented(self):
        raise NotImplementedError

    def next(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    type   = property(lambda self: self._sock.type  , doc='the socket type')
    family = property(lambda self: self._sock.family, doc='the socket family')
    proto  = property(lambda self: self._sock.proto , doc='the socket protocol')
    for nm in ('connect_ex,fileno,getpeername,getsockname,getsockopt,'
        'setsockopt,setblocking,settimeout,gettimeout,shutdown').split(','):
        exec ('def %s(self, *args): return self._sock.%s(*args)\n\n'
              '%s.__doc__ = realsocket.%s.__doc__') % (nm, nm, nm, nm)
    del nm
    write  = file.sendall
    accept = bind = listen = recvfrom = recv_into = \
        recvfrom_into = sendto = _not_implemented

class fakesslwrap(file):
    def __init__(self, sock, *args, **kwargs):
        sock = sock._sock
        file.__init__(self, sock.fileno())
        self._sock  = sock  = realsslwrap(sock, *args, **kwargs)
        self._send  = sock.write
        self._recv  = sock.read
        self._close = sock.close

    for nm in 'cipher,do_handshake,peer_certificate,pending,shutdown'.split(','):
        exec 'def %s(self, *args): return self._sock.%s(*args)\n\n' % (nm, nm)
    del nm
    read, write = file.recv, file.send

def _bad_file_descriptor(*args):
    raise error(EBADF, 'Bad file descriptor')

econn_noerr = {EALREADY: 0, EINPROGRESS: 0, EISCONN: 0, EWOULDBLOCK: 0}
__all__.extend('exit mainloop install timeout uninstall'.split())
socket = SocketType = fakesocket
