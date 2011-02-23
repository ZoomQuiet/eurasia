import re, _socket
from socket2 import *
from _socket import fromfd
from pyev import Io, EV_READ
from greenlet import greenlet
from core import loop, timeout, mainloop, exit
from socket2 import error, fakesocket, getfqdn, realsocket

def install():
    global SocketServer
    import SocketServer
    from SocketServer import TCPServer as  TCPServer_old, \
        StreamRequestHandler as StreamRequestHandler_old
    SocketServer.TCPServer = TCPServer
    SocketServer.StreamRequestHandler = StreamRequestHandler

def uninstall():
    assert SocketServer
    SocketServer.TCPServer = TCPServer_old
    SocketServer.StreamRequestHandler = StreamRequestHandler_old

class tcpserver:

    '''Classic server.'''

    allow_reuse_address = True

    request_queue_size  = 4194304

    address_family, socket_type = AF_INET, SOCK_STREAM

    def __init__(self, addr, handler, bind_and_activate=True):
        '''Constructor.  May be extended, do not override.'''
        self.setup(addr, bind_and_activate)
        self.RequestHandlerClass = handler

    def setup(self, addr, bind_and_activate=True):
        info = addrinfo(addr)
        if 'fileno' in info:
            self.socket = fromfd(info['fileno'], info['family'], SOCK_STREAM)
            self.require_bind_and_activate = False
            self.family = info['family']
            try:
                servaddr = self.socket.getsockname()
            except error:
                servaddr = None
            if servaddr:
                host, self.server_port = self.server_address = servaddr
                self.server_name = getfqdn(host)
        elif 'host' in info:
            self.socket = realsocket(info['family'], SOCK_STREAM)
            if info['family'] == AF_INET6 and info['host'] == '::':
                if hasattr(_socket, 'IPV6_V6ONLY'):
                    IPV6_V6ONLY = _socket.IPV6_V6ONLY
                    self.socket.setsockopt(IPPROTO_IPV6, IPV6_V6ONLY, 0)
            self.require_bind_and_activate = True
            self.server_address = (info['host'], info['port'])
            self.server_name = getfqdn(info['host'])
            self.server_port = info['port']
            self.family = info['family']
        else:
            self.socket = realsocket(info['family'], SOCK_STREAM)
            self.require_bind_and_activate = True
            self.server_address = info['addr']
            self.family = info['family']

        if bind_and_activate and self.require_bind_and_activate:
            self.server_bind()
            self.server_activate()
        self.r_event = Io(self.socket.fileno() , EV_READ , loop,
            self._handle_request, self)

    def _handle_request(self, w, revents):
        req, addr = self.get_request()
        if self.verify_request(req, addr):
            greenlet(self.process_request).switch(req, addr)

    def server_bind(self):
        '''Called by constructor to bind the socket.'''
        if self.require_bind_and_activate:
            if self.allow_reuse_address:
                self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            self.socket.bind(self.server_address)

    def server_activate(self):
        '''Called by constructor to activate the server.'''
        if self.require_bind_and_activate:
            self.socket.listen(self.request_queue_size)

    def fileno(self):
        '''Return socket file number.'''
        return self.socket.fileno()

    def serve_forever(self):
        '''Handle one request at a time until shutdown.'''
        self.r_event.start()
        mainloop()

    def start(self):
        '''Handle one request at a time until shutdown.'''
        self.r_event.start()

    def run(self):
        '''Handle one request at a time until shutdown.'''
        self.r_event.start()

    def shutdown(self):
        '''Stops the serve_forever loop.'''
        self.r_event.stop()
    stop = shutdown

    def process_request(self, req, addr):
        '''Call finish_request.'''
        try:
            self.finish_request(req, addr)
            self.close_request (req)
        except:
            self.handle_error  (req, addr)
            self.close_request (req)

    def verify_request(self, req, addr):
        '''Verify the request.  May be overridden.

        Return True if we should proceed with this request.

        '''
        return True

    def server_close(self):
        '''Called to clean-up the server.

        May be overridden.

        '''
        self.socket.close()

    def close_request(self, req):
        '''Called to clean up an individual request.'''
        req.close()

    def handle_error(self, req, addr):
        '''Handle an error gracefully.

        May be overridden.

        '''
        pass

    def get_request(self):
        '''Get the request and client address from the socket.'''
        sock, addr = self.socket.accept()
        return fakesocket(_sock=sock), addr

    def finish_request(self, req, addr):
        '''Finish one request by instantiating RequestHandlerClass.'''
        self.RequestHandlerClass(req, addr, self)

class StreamRequestHandler:

    '''Define self.rfile and self.wfile for stream sockets.'''

    def __init__(self, req, addr, serv):
        self.request = req
        self.server  = serv
        self.client_address = addr
        self.setup ()
        self.handle()
        self.finish()

    def handle(self):
        pass

    def setup(self):
        self.connection = self.request
        self.rfile = self.request.makefile('rb')
        self.wfile = self.request.makefile('wb')

    def finish(self):
        self.rfile.close()
        self.wfile.close()

class server(tcpserver):

    '''Standard server, simple and fast.'''

    def _handle_request(self, w, revents):
        sock, addr = self.socket.accept()
        greenlet(self.RequestHandlerClass).switch(
            fakesocket(_sock=sock), addr , self)

def addrinfo(addr):
    # String addr - "host:port"
    # Ipv4 example: '127.0.0.1:8080'
    # Ipv6 example: '[::1]:8080'
    if isinstance(addr, basestring):
        ipv6 = _is_ipv6(addr)
        if ipv6:
            host, port = ipv6.groups()
            return dict(host=host, port=int(port), family=AF_INET6)
        host, port = addr.split(':', 1)
        return dict(host=host.strip(), port=int(port), family=AF_INET)
    # Int addr - fromfd(fileno, AF_INET).
    # Example: 0
    elif isinstance(addr, int):
        return dict(fileno=addr, family=AF_INET)
    elif len(addr) == 2:
        if isinstance(addr[0], int):
            family, addr = addr
            # Tuple addr - fromfd(fileno, family).
            # Example: (AF_INET, 0)
            if isinstance(addr, int):
                return dict(fileno=addr, family=family)
            # Tuple addr - (host, port).
            # Example: ('127.0.0.1', 8080)
            if family == AF_INET or family == AF_INET6:
                host , port = addr[0], int(addr[1])
                return dict(host=host, port=port, family=family)
            # Tuple addr - (addr, family)
            # Example: (('127.0.0.1', 8080), AF_INET)
            return dict(addr=addr, family=family)
        # Tuple addr - (ipv6addr, port)
        # Example: ('::1', 8080)
        elif ':' in addr[0]:
            host , port = addr[0].strip(), int(addr[1])
            return dict(host=host, port=port, family=AF_INET6)
        # Tuple addr - (host, port)
        # Example: ('www.exam.ple', 8080)
        host , port = addr[0].strip(), int(addr[1])
        return dict(host=host, port=port, family=AF_INET)
    raise ValueError('invalid address %r' %addr)

TCPServer = TcpServer = tcpserver
SocketServer,  Server = None, server
__all__   = ('exit mainloop install uninstall timeout server Server '
             'TCPServer TcpServer StreamRequestHandler'      ).split()
_is_ipv6  = re.compile(r'^\s*\[([a-fA-F0-9:\s]+)]\s*:\s*([0-9]+)\s*$').match
