from errno import EBADF
from _weakref import proxy
from Cookie import SimpleCookie
from server import server, Server
from re import compile as rcompile, I
from core import mainloop, exit, timeout
from socket2 import fakesocket, error as SocketError
from greenlet import greenlet, getcurrent, GreenletExit

class httpserver(server):
    def __init__(self, addr, handler, bind_and_activate=True, env={}, **environ):
        environ.update(env)
        self.setup(addr, bind_and_activate)
        self.RequestHandlerClass = httphandler(handler, servenv(self,  environ))

class wsgiserver(server):
    def __init__(self, addr, app, bind_and_activate=True, env={}, **environ):
        environ.update(env)
        self.setup(addr, bind_and_activate)
        self.RequestHandlerClass = wsgihandler(app, wsgienv(self,  environ))

class httpfile(object):
    def __init__(self, sock, addr, **environ):
        self.owner = getcurrent()
        sock._r_call(self._init, 300., sock, addr, environ)

    def _init(self, sock, addr, environ):
        data = sock._readline(4096)
        if data == '':
            raise GreenletExit
        m = first(data)
        if m:
            method, uri, self.version = m.groups()
        else:
            raise ValueError('invalid http header %r' %data)
        self.method = method = method.upper()
        data = sock._readline(2048)
        size = len(data)
        while 1:
            m = header(data)
            if m:
                key, value = m.groups()
            elif data == '\r\n' or data == '\n':
                break
            else:
                raise ValueError('invalid http header %r' %data)
            environ['HTTP_' + key.upper().replace('-', '_')] = value
            data  = sock._readline(2048)
            size += len(data)
            if size > 8192:
                raise ValueError('request header is too large')
        if method == 'POST' or 'HTTP_CONTENT_LENGTH' in environ:
            left = environ['CONTENT_LENGTH'] = environ['HTTP_CONTENT_LENGTH']
            left = left.strip()
            if len(left) > 16:
                raise ValueError('content-length %r is too large' %left)
            left = int(left)
            if left < 0:
                raise ValueError('invalid content-length %r' %left)
            self.left = left
        else:
            self.left = 0
        p = uri.find('?')
        if p != -1:
            environ['PATH_INFO'] = uri[:p]
            environ['QUERY_STRING'] = uri[p+1:]
        else:
            environ['PATH_INFO'] = uri
            environ['QUERY_STRING'] = ''
        if addr:
            environ['REMOTE_ADDR'] , environ['REMOTE_PORT'] = addr
        else:
            environ['REMOTE_ADDR'] = environ['REMOTE_PORT'] = ''
        environ['SCRIPT_NAME'] = ''
        environ['REQUEST_URI'] = uri
        environ['REQUEST_METHOD' ] = method
        environ['SERVER_PROTOCOL'] = self.version
        environ.setdefault('CONTENT_TYPE',
        environ.setdefault('HTTP_CONTENT_TYPE', ''))
        self.headers  = {}
        self.uri      = uri
        self.sockfile = sock
        self.environ  = environ
        self._r_call  = sock._r_call
        self._w_call  = sock._w_call

    def __iter__(self):
        data = self.readline(-1, 300.)
        while data:
            yield data
            data = self.readline(-1, 300.)

    def __del__(self):
        if self.closed:
            return
        self._keep_alive = 0

    def __len__(self):
        return int(self.environ['HTTP_CONTENT_LENGTH'])

    def __getitem__(self, key):
        return self.environ['HTTP_' + key.upper().replace('-', '_')]

    def __setitem__(self, key, value):
        self.headers['-'.join(i.capitalize() for i in key.split('-'))] = value

    def __contains__(self, key):
        return 'HTTP_' + key.upper().replace('-', '_') in self.environ

    def get_request_uri(self):
        return self.environ['REQUEST_URI']

    def set_request_uri(self, uri):
        environ = self.environ
        if isinstance(uri, basestring):
            environ['SCRIPT_NAME'] = ''
            environ['REQUEST_URI'] = uri
            p = uri.find('?')
            if p != -1:
                environ['PATH_INFO'] = uri[:p]
                environ['QUERY_STRING'] = uri[p+1:]
            else:
                environ['PATH_INFO'] = uri
                environ['QUERY_STRING'] = ''
        else:
            script_name, path_info, query = uri
            if query:
                environ['REQUEST_URI'] = '%s%s?%s' %(
                    script_name, path_info, query)
            else:
                environ['REQUEST_URI'] = script_name + path_info
            environ['PATH_INFO'   ] = path_info
            environ['SCRIPT_NAME' ] = script_name
            environ['QUERY_STRING'] = query

    request_uri = property(get_request_uri, set_request_uri, 'cgi uri')
    del get_request_uri, set_request_uri

    def get_script_name(self):
        return self.environ['SCRIPT_NAME']

    def set_script_name(self, script_name):
        environ = self.environ
        environ['SCRIPT_NAME'] = script_name
        query = environ['QUERY_STRING']
        if query:
            environ['REQUEST_URI'] = '%s%s?%s' %(
                script_name , environ['PATH_INFO'], query)
        else:
            environ['REQUEST_URI'] = \
                script_name + environ['PATH_INFO']

    script_name = property(get_script_name, set_script_name, 'cgi script name')
    del get_script_name, set_script_name

    def get_path_info(self):
        return self.environ['PATH_INFO']

    def set_path_info(self, path_info):
        environ = self.environ
        environ['PATH_INFO'] = path_info
        query = environ['QUERY_STRING']
        if query:
            environ['REQUEST_URI'] = '%s%s?%s' %(
                environ['SCRIPT_NAME'] , path_info, query)
        else:
            environ['REQUEST_URI'] = \
                environ['SCRIPT_NAME'] + path_info

    path_info = property(get_path_info, set_path_info, 'cgi path info')
    del get_path_info, set_path_info

    def get_query_string(self):
        return self.environ['QUERY_STRING']

    def set_query_string(self, query):
        environ = self.environ
        environ['QUERY_STRING'] = query
        if query:
            environ['REQUEST_URI' ] = '%s%s?%s' %(
                environ['SCRIPT_NAME'] , environ['PATH_INFO'], query)
        else:
            environ['REQUEST_URI' ] = \
                environ['SCRIPT_NAME'] + environ['PATH_INFO']

    query_string = property(get_query_string, set_query_string, 'cgi query string')
    del get_query_string, set_query_string

    def getstatus(self):
        return self._status

    def setstatus(self, status):
        if isinstance(status, basestring):
            self._status = status
        else:
            self._status = RESPONSES[status]

    status, _status = property(getstatus, setstatus, 'response status'), '200 OK'
    del getstatus, setstatus

    def get_cookie(self):
        if 'HTTP_COOKIE' in self.environ:
            return SimpleCookie(self.environ['HTTP_COOKIE'])

        return None

    def set_cookie(self, cookie):
        self._cookie = cookie

    cookie, _cookie = property(get_cookie, set_cookie), None
    del get_cookie, set_cookie

    def fileno(self):
        return self.sockfile.fileno()

    def nocache(self):
        self.headers.update(NOCACHEHEADERS)

    def items(self):
        return [('-'.join(i.capitalize() for i in key[5:].split('_')), value) \
           for key, value in self.environ.items() if key[:5] == 'HTTP_']

    def keys(self):
        return ['-'.join(i.capitalize() for i in key[5:].split('_')) \
           for key, value in self.environ.items() if key[:5] == 'HTTP_']

    def values(self):
        return [value for key, value in self.environ.items() if key[:5] == 'HTTP_']

    def get(self, key, default=None):
        key = 'HTTP_' + key.upper().replace('-', '_')
        if key in self.environ:
            return self.environ[key]
        return default

    def setdefault(self, key, value):
        key = '-'.join(i.capitalize() for i in key.split('-'))
        if key not in self.headers:
            self.headers[key] = value

    def update(self, *args, **kwargs):
        if args:
            if len(args) > 1:
                raise TypeError('update expected at most 1 argument, got %s' %len(args))
            items = args[0]
            if hasattr(items, 'items'):
                items = items.items()
            for key, value in items:
                key = '-'.join(i.capitalize() for i in key.split('-'))
                self.headers[key] = value
        for key, value in kwargs.items():
            key = '-'.join(i.capitalize() for i in key.split('-'))
            self.headers[key] = value

    def has_key(self, key):
        return 'HTTP_' + key.upper().replace('-', '_') in self.environ

    def read(self, size=-1, timeout=-1):
        return self._r_call(self._read, timeout, size)

    def _read(self, size=-1):
        if size == -1 or size >= self.left:
            data = self.sockfile._read(self.left)
            self.left = 0
            return data
        else:
            data = self.sockfile._read(size)
            self.left -= len(data)
            return data

    def readline(self, size=-1, timeout=-1):
        return self._r_call(self._readline, timeout, size)

    def _readline(self, size=-1):
        if size == -1 or size >= self.left:
            data = self.sockfile.readline(self.left)
        else:
            data = self.sockfile.readline(size)
        self.left -= len(data)
        return data

    def write(self, data, timeout=-1):
        return self._w_call(self._write, timeout, data)

    def _write(self, data):
        if not self.headers_sent:
            self._start_response(self._status, [])
        if data:
            self._sendall(data)

    def writelines(self, lst, timeout=-1):
        self.write(''.join(lst), timeout)

    def start_response(self, status=None, response_headers=[], timeout=-1):
        self._w_call(self._start_response, timeout, status, response_headers)

    def _start_response(self, status=None, response_headers=[]):
        if response_headers:
            lst = ['%s: %s' %(key, value) for key, value in \
                self.headers.items() + response_headers]
        else:
            lst = ['%s: %s' %(key, value) for key, value in \
                self.headers.items()]
        if status is not None:
            self.status = status
        lst.insert(0, '%s %s' %(self.version, self._status))
        if self._cookie is not None:
            lst.append(self._cookie.output())
        lst.append('Transfer-Encoding: chunked')
        lst.append('\r\n')
        self.sockfile._sendall('\r\n'.join(lst))
        self.headers_sent = True
    headers_sent = False

    def sendall(self, data, timeout=-1):
        return self._w_call(self._sendall, timeout, data)

    def _sendall(self, data):
        self.sockfile._sendall('%s\r\n%s\r\n' %(hex(len(data))[2:], data))

    def flush(self, timeout=-1):
        pass

    def shutdown(self):
        self.closed = True
        self.owner.switch(0)

    def close(self, keep_alive=-1, timeout=-1):
        self.sockfile.sendall('0\r\n\r\n', timeout)
        environ = self.environ
        if 'HTTP_KEEP_ALIVE'  in  environ or  environ.get(
           'HTTP_CONNECTION', '').lower() == 'keep-alive':
            try:
                seconds = int(environ.get('HTTP_KEEP_ALIVE', 300))
                if keep_alive == -1 or keep_alive > seconds:
                    keep_alive = float(seconds)
            except:
                keep_alive = 0
        else:
            keep_alive = 0
        self.closed = True
        self._keep_alive = keep_alive
        getcurrent().parent = self.owner
    closed, _keep_alive = False, 0

    def _close(self, keep_alive=-1):
        self.sockfile._sendall('0\r\n\r\n')
        environ = self.environ
        if 'HTTP_KEEP_ALIVE'  in  environ or  environ.get(
           'HTTP_CONNECTION', '').lower() == 'keep-alive':
            try:
                seconds = int(environ.get('HTTP_KEEP_ALIVE', 300))
                if keep_alive == -1 or keep_alive > seconds:
                    keep_alive = float(seconds)
            except:
                keep_alive = 0
        else:
            keep_alive = 0
        self.closed = True
        self._keep_alive = keep_alive
        getcurrent().parent = self.owner

def _bad_file_descriptor(*args):
    raise SocketError(EBADF, 'Bad file descriptor')

def servenv(serv, env={}, **environ):
    environ.update(env)
    setenv = environ.setdefault
    if hasattr(serv, 'server_name'):
        setenv('SERVER_NAME', serv.server_name)
    if hasattr(serv, 'server_port'):
        setenv('SERVER_PORT', serv.server_port)
    return environ

def wsgienv(serv, env={}, **environ):
    environ = servenv(serv, env, **environ)
    setenv  = environ.setdefault
    setenv('wsgi.version', (1, 0))
    setenv('wsgi.run_once', False)
    setenv('wsgi.multiprocess',  True )
    setenv('wsgi.multithread' ,  True )
    setenv('wsgi.url_scheme'  , 'HTTP')
    if 'wsgi.errors' not in environ:
        environ['wsgi.errors'] = __import__('sys').stderr
    return environ

def httphandler(controller, env={}, **environ):
    environ.update(env)
    def handler(sock, addr, serv):
        fd = httpfile(sock, addr, **environ)
        try:
            greenlet(controller).switch(fd)
        except GreenletExit:
            pass
        keep_alive = fd._keep_alive
        while keep_alive:
            sock.r_wait(keep_alive)
            fd = httpfile(sock, addr, **environ)
            try:
                greenlet(controller).switch(fd)
            except GreenletExit:
                pass
            keep_alive = fd._keep_alive
    return handler

def wsgihandler(app, env={}, **environ):
    def controller(httpfile):
        env = httpfile.environ
        env['wsgi.input'] = proxy(httpfile)
        def start_response(status, headers, exc_info=None):
            if exc_info:
                try:
                    if httpfile.headers_sent:
                        raise exc_info[0], exc_info[1], exc_info[2]
                finally:
                    exc_info = None
            elif httpfile.headers_sent:
                raise AssertionError('headers already set')
            httpfile._start_response(status, headers)
            return httpfile.sendall
        for data in app(env, start_response):
            if data:
                httpfile.sendall(data, 15.+(len(data)>>10))
        httpfile.close(15.)
    handler = httphandler(controller, env, **environ)
    return handler

RESPONSES = dict((int(i.split(None, 1)[0]), i) for i in ('100 Continue,101 Switching '
'Protocols,200 OK,201 Created,202 Accepted,203 Non-Authoritative Information,204 No C'
'ontent,205 Reset Content,206 Partial Content,300 Multiple Choices,301 Moved Permanen'
'tly,302 Found,303 See Other,304 Not Modified,305 Use Proxy,307 Temporary Redirect,40'
'0 Bad Request,401 Unauthorized,402 Payment Required,403 Forbidden,404 Not Found,405 '
'Method Not Allowed,406 Not Acceptable,407 Proxy Authentication Required,408 Request '
'Timeout,409 Conflict,410 Gone,411 Length Required,412 Precondition Failed,413 Reques'
't Entity Too Large,414 Request-URI Too Long,415 Unsupported Media Type,416 Requested'
' Range Not Satisfiable,417 Expectation Failed,500 Internal Server Error,501 Not Impl'
'emented,502 Bad Gateway,503 Service Unavailable,504 Gateway Timeout,505 HTTP Version'
' Not Supported').split(','))
NOCACHEHEADERS = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
    'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT'}
first  = rcompile(r'^(\w+)[\s\t]+([^\r\n]+)[\s\t]+(HTTP/[01]\.[0-9])\r?\n$', I).match
header = rcompile(r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*\r?\n$').match
WSGIServer = WsgiServer = wsgiserver
HTTPServer = HttpServer = httpserver
__all__    = ['mainloop', 'exit', 'timeout', 'httpserver', 'wsgiserver', 'HttpServer',
              'WsgiServer', 'HTTPServer', 'WSGIServer']
