import socket_, re
from time import time
from urllib import unquote
from errno  import ETIMEDOUT
from exceptions_ import Timeout
from scheduler import idle_switch
from greenlet import getcurrent, greenlet, GreenletExit
from socket_ import serve_forever, exit, run, break_, mainloop

class httpfile:
    def __init__(self, s, reuse, **environ):
        tstamp = time()
        while 1:
            data = s.readline(4096, 20.)
            if '' == data:
                raise GreenletExit
            _ = is_first(data)
            if _ is None:
                raise ValueError('invalid http header %r' % data)
            method, uri, version = _.groups()
            if method:
                break
            if time() - tstamp > 20.:
                raise Timeout(ETIMEDOUT, 'read time out')
        self.bgenv = environ
        environ = dict(environ)
        data = s.readline(2048, 10.)
        size = len(data)
        while 1:
            _ = is_header(data)
            if _ is None:
                if '\r\n' == data or '\n' == data:
                    break
                raise ValueError('invalid http header %r' % data)
            key, value = _.groups()
            environ['HTTP_' + key.upper().replace('-', '_')] = value
            data  = s.readline(2048, 10.)
            size += len(data)
            if size > 8192:
                raise ValueError('request header is too large')
        if 'POST' == method or \
           'HTTP_CONTENT_LENGTH' in environ:
            environ['CONTENT_LENGTH'] = environ['HTTP_CONTENT_LENGTH']
            left = environ['HTTP_CONTENT_LENGTH'].strip()
            if len(left) > 10:
                raise ValueError('content-length %r is too large' % left)
            left = int(left)
            if left < 0 or left > 0xffffffff:
                raise ValueError('invalid content-length %r' % left)
            self.left = left
        else:
            self.left = 0
        p = uri.find('?')
        if p != -1:
            environ['PATH_INFO'] = '%2F'.join(
                unquote(x) for x in quoted_slash_split(uri[:p]))
            environ['QUERY_STRING'] = uri[p+1:]
        else:
            environ['PATH_INFO'] = '%2F'.join(
                unquote(x) for x in quoted_slash_split(uri))
            environ['QUERY_STRING'] = ''
        environ['SCRIPT_NAME'] = ''
        environ['REQUEST_URI'] = uri
        environ['REQUEST_METHOD' ] = method
        environ['SERVER_PROTOCOL'] = version
        environ.setdefault('CONTENT_TYPE',
        environ.setdefault('HTTP_CONTENT_TYPE', ''))
        self.closed = 0
        self.socket = s
        self.reuse = reuse
        self.headers_sent = 0
        self.environ = environ
        self.owner = getcurrent()

    def fileno(self):
        return self.socket.fileno()

    def read(self, size, timeout=-1):
        if size > self.left:
            if -1 == timeout:
                timeout = 16. + (self.left >> 10)
            data = self.socket.read(self.left, timeout)
            self.left = 0
            return data
        else:
            if -1 == timeout:
                timeout = 16. + (size >> 10)
            data = self.socket.read(size, timeout)
            self.left -= len(data)
            return data

    def readline(self, size, timeout=-1):
        if size > self.left:
            if -1 == timeout:
                timeout = 16. + (self.left >> 10)
            data = self.socket.readline(self.left, timeout)
        else:
            if -1 == timeout:
                timeout = 16. + (size >> 10)
            data = self.socket.readline(size, timeout)
        self.left -= len(data)
        return data

    def write(self, data, timeout=-1):
        assert self.headers_sent
        data = '%x\r\n%s\r\n' %(len(data), data)
        if -1 == timeout:
            timeout = 16. + (len(data) >> 10)
        self.socket.write(data, timeout)

    def flush(self, timeout=-1):
        pass

    def start_response(self, status ='200 OK',
        response_headers=[], timeout=-1):
        headers = ['%s: %s' % i for i in response_headers]
        headers.insert(0, '%s %s' %(self.environ['SERVER_PROTOCOL'], status))
        headers.append('Transfer-Encoding: chunked')
        headers.append('\r\n')
        headers = '\r\n'.join(headers)
        if -1 == timeout:
            timeout = 16. + (len(headers) >> 10)
        self.socket.write(headers, timeout)
        self.headers_sent = 1

    def close(self, keep_alive=300., timeout=-1):
        if self.closed:
            return
        self.closed = 1
        if 0 == keep_alive:
            return self.socket.close()
        if -1 == timeout:
            timeout = 16.
        if self.headers_sent:
            self.socket.write('0\r\n\r\n', timeout)
        environ = self.environ
        if 'HTTP_KEEP_ALIVE'  in  environ or environ.get(
           'HTTP_CONNECTION', '').lower() == 'keep-alive':
            seconds = environ.get('HTTP_KEEP_ALIVE', '300')
            if is_seconds(seconds):
                seconds = float(seconds)
                if -1 == keep_alive or keep_alive > seconds:
                    keep_alive = seconds
                back_ = getcurrent()
                goto_ = greenlet(self._reuse, back_.parent)
                idle_switch(back_, goto_, (keep_alive, ))
            else:
                return self.socket.close()
        else:
            return self.socket.close()

    def _reuse(self, keep_alive):
        s = self.socket
        reuse = self.reuse
        try:
            s.r_wait(keep_alive)
        except Timeout:
            return
        try:
            http = httpfile(s, reuse, **self.bgenv)
        except Timeout:
            return
        reuse(http)

    closed = headers_sent = 0

def httphandler(handler, **environ):
    def wrapper(s, addr):
        if isinstance(addr, tuple):
            try:
                http = httpfile(s, handler,
                    REMOTE_ADDR=addr[0],
                    REMOTE_PORT=addr[1], **environ)
            except:
                return
            handler(http)
        else:
            try:
                http = httpfile(s, handler, **environ)
            except:
                return
            handler(http)
    return wrapper

class Server(socket_.TCPServer):
    def __init__(self, address, handler, **environ):
        handler = httphandler(handler, **environ)
        socket_.TCPServer.__init__(self, address, handler)
        environ.setdefault('SERVER_NAME', self.server_name)
        environ.setdefault('SERVER_PORT', self.server_port)

server = HTTPServer = Server

is_seconds = re.compile((r'^\s*[1-9][0-9]{0,6}\s*$')).match
is_header  = re.compile((r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*'
r'\r?\n$')).match
is_first   = re.compile((r'^(?:[ \t]*(\w+)[ \t]+([^\r\n]+)[ \t]+(HTTP/[01]\.[0'
r'-9])[ \t]*|[ \t]*)\r?\n$'), re.I).match

quoted_slash_split = re.compile('(?i)%2F').split
RESPONSES = dict((int(i.split(None, 1)[0]), i) for i in ('100 Continue,101 Swi'
'tching Protocols,200 OK,201 Created,202 Accepted,203 Non-Authoritative Inform'
'ation,204 No Content,205 Reset Content,206 Partial Content,300 Multiple Choic'
'es,301 Moved Permanently,302 Found,303 See Other,304 Not Modified,305 Use Pro'
'xy,307 Temporary Redirect,400 Bad Request,401 Unauthorized,402 Payment Requir'
'ed,403 Forbidden,404 Not Found,405 Method Not Allowed,406 Not Acceptable,407 '
'Proxy Authentication Required,408 Request Timeout,409 Conflict,410 Gone,411 L'
'ength Required,412 Precondition Failed,413 Request Entity Too Large,414 Reque'
'st-URI Too Long,415 Unsupported Media Type,416 Requested Range Not Satisfiabl'
'e,417 Expectation Failed,500 Internal Server Error,501 Not Implemented,502 Ba'
'd Gateway,503 Service Unavailable,504 Gateway Timeout,505 HTTP Version Not Su'
'pported').split(','))
