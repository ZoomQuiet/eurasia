from cgietc import wsgi, json, Form, SimpleUpload, Browser, Comet
from socket2 import mainloop0, mainloop, SSL, Disconnect, SocketFile, \
	Sockets, TcpHandler, TcpServer

import re, sys
from _weakref import proxy
from stackless import channel, tasklet
from time import gmtime, strftime, time
from BaseHTTPServer import BaseHTTPRequestHandler
RESPONSES = dict((key, '%d %s' %(key, value[0]))
              for key, value in BaseHTTPRequestHandler.responses.items())

del BaseHTTPRequestHandler, sys.modules['BaseHTTPServer']

class HttpFile(object):
	def __init__(self, sockfile, **environ):
		first  = sockfile.readline(8192)
		try:
			method, uri, version = R_FIRST(first).groups()
		except AttributeError:
			sockfile.close()
			raise IOError

		self.version = version.upper()
		self.method  = method =  method.upper()

		line = sockfile.readline(8192)
		counter = len(first) + len(line)
		while True:
			try:
				key, value = R_HEADER(line).groups()
			except AttributeError:
				if line in ('\r\n', '\n'):
					break

				sockfile.close()
				raise IOError

			environ['HTTP_' + key.upper().replace('-', '_')] = value
			line = sockfile.readline(8192)
			counter += len(line)
			if counter > 10240:
				sockfile.close()
				raise IOError

		if method == 'GET':
			self.left = 0
			environ['CONTENT_LENGTH'] = environ['HTTP_CONTENT_LENGTH'] = '0'
		else:
			try:
				left = environ['CONTENT_LENGTH'] = environ['HTTP_CONTENT_LENGTH']
			except:
				sockfile.close()
				raise IOError
			else:
				n = left.strip()
				if len(n) > 16:
					raise IOError

				n = int(n)
				if n < 0:
					raise IOError

				self.left = n

		p = uri.find('?')
		if p != -1:
			environ['PATH_INFO'] = uri[:p]
			environ['QUERY_STRING'] = uri[p+1:]
		else:
			environ['PATH_INFO'] = uri
			environ['QUERY_STRING'] = ''

		environ['REQUEST_METHOD' ] = method
		environ['SERVER_PROTOCOL'] = self.version

		environ['SCRIPT_NAME'] = ''
		environ['REQUEST_URI'] = uri

		sockaddr = sockfile.address

		if sockaddr:
			environ['REMOTE_ADDR'] = sockaddr[0]
			environ['REMOTE_PORT'] = sockaddr[1]
		else:
			environ['REMOTE_ADDR'] = environ['REMOTE_PORT'] = ''

		environ.setdefault('CONTENT_TYPE',
		environ.setdefault('HTTP_CONTENT_TYPE', ''))

		self.content = []
		self.headers = {}
		self.headers_set = []
		self.environ = environ
		self.sockfile = sockfile
		self.path = self.uri = uri
		self.keep_alive = channel()
		self.write = self.content.append

	def __iter__(self):
		data = self.readline()
		while data:
			yield data
			data = self.readline()

	def __del__(self):
		if hasattr(self, 'keep_alive'):
			return self.keep_alive and self.keep_alive.send(0)

	def __len__(self):
		return int(self.environ['HTTP_CONTENT_LENGTH'])

	def __getitem__(self, key):
		return self.environ['HTTP_' + key.upper().replace('-', '_')]

	def __setitem__(self, key, value):
		self.headers['-'.join(i.capitalize() for i in key.split('-'))] = value

	def __contains__(self, key):
		return 'HTTP_' + key.upper().replace('-', '_') in self.environ

	@property
	def pid(self):
		return self.sockfile.pid

	@property
	def address(self):
		return self.sockfile.address

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
			environ['REQUEST_URI'] = \
				'%s%s?%s' %(script_name , path_info, query) if query \
				else        script_name + path_info

			environ['PATH_INFO'   ] = path_info
			environ['SCRIPT_NAME' ] = script_name
			environ['QUERY_STRING'] = query

	request_uri = property(get_request_uri, set_request_uri)
	del get_request_uri, set_request_uri

	def get_script_name(self):
		return self.environ['SCRIPT_NAME']

	def set_script_name(self, script_name):
		environ = self.environ
		environ['SCRIPT_NAME'] = script_name

		query = environ['QUERY_STRING']
		environ['REQUEST_URI'] = \
			'%s%s?%s' %(script_name , environ['PATH_INFO'], query) if query \
			else        script_name + environ['PATH_INFO']

	script_name = property(get_script_name, set_script_name)
	del get_script_name, set_script_name

	def get_path_info(self):
		return self.environ['PATH_INFO']

	def set_path_info(self, path_info):
		environ = self.environ
		environ['PATH_INFO'] = path_info

		query = environ['QUERY_STRING']
		environ['REQUEST_URI'] = \
			'%s%s?%s' %(environ['SCRIPT_NAME'] , path_info, query) if query \
			else        environ['SCRIPT_NAME'] + path_info

	path_info = property(get_path_info, set_path_info)
	del get_path_info, set_path_info

	def get_query_string(self):
		return self.environ['QUERY_STRING']

	def set_query_string(self, query):
		environ = self.environ
		environ['QUERY_STRING'] = query
		environ['REQUEST_URI' ] = \
			'%s%s?%s' %(environ['SCRIPT_NAME'] , environ['PATH_INFO'], query) if query \
			else        environ['SCRIPT_NAME'] + environ['PATH_INFO']

	query_string = property(get_query_string, set_query_string)
	del get_query_string, set_query_string

	def getuid(self):
		try:
			return R_UID(self['Cookie']).groups()[0]
		except:
			return None

	def setuid(self, uid):
		self.headers['Set-Cookie'] = 'uid=%s; path=/; expires=%s' %(
			uid, strftime('%a, %d-%b-%Y %H:%M:%S GMT', gmtime(time() + 157679616)))

	uid = property(getuid, setuid)
	del getuid, setuid

	def getstatus(self):
		return self._status

	def setstatus(self, status):
		self._status = status if isinstance(status, basestring) else RESPONSES[status]

	status, _status = property(getstatus, setstatus), RESPONSES[200]
	del getstatus, setstatus

	def fileno(self):
		return self.sockfile.pid

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

	def read(self, size=-1):
		if size == -1 or size >= self.left:
			try:
				data = self.sockfile.read(self.left)
			except Disconnect:
				self.keep_alive = self.keep_alive and self.keep_alive.send(0)
				raise

			self.left = 0
			return data
		else:
			try:
				data = self.sockfile.read(size)
			except Disconnect:
				self.keep_alive = self.keep_alive and self.keep_alive.send(0)
				raise

			self.left -= len(data)
			return data

	def readline(self, size=-1):
		if size == -1 or size >= self.left:
			try:
				data = self.sockfile.readline(self.left)
			except Disconnect:
				self.keep_alive = self.keep_alive and self.keep_alive.send(0)
				raise
		else:
			try:
				data = self.sockfile.readline(size)
			except Disconnect:
				self.keep_alive = self.keep_alive and self.keep_alive.send(0)
				raise

		self.left -= len(data)
		return data

	def writelines(self, seq):
		for line in seq:
			self.write(line)

	def flush(self):
		pass

	def begin(self):
		self.keep_alive = self.keep_alive and self.keep_alive.send(0)
		headers_set = ['%s: %s' %(key, value)
		                      for key, value in self.headers.items()] + [
		               '%s: %s' %(key, value)
		                      for key, value in self.headers_set]

		headers_set.insert(0, '%s %s' %(self.version, self._status))
		headers_set.append('\r\n')

		self.write = self.sockfile.write
		self.write('\r\n'.join(headers_set))
		self.close = self.end = self.sockfile.close
		del self.headers, self.headers_set

	def wbegin(self, data=''):
		self.keep_alive = self.keep_alive and self.keep_alive.send(0)
		headers_set = ['%s: %s' %(key, value)
		                      for key, value in self.headers.items()] + [
		               '%s: %s' %(key, value)
		                      for key, value in self.headers_set]

		headers_set.insert(0, '%s %s' %(self.version, self._status))
		headers_set.append('\r\n')

		self.write = self.sockfile.write
		self.write('\r\n'.join(headers_set) + data)
		self.close = self.end = self.sockfile.close
		del self.headers, self.headers_set

	def close(self):
		if not self.keep_alive:
			raise Disconnect

		data = ''.join(self.content)
		self.headers['Content-Length'] = str(len(data))
		headers_set = ['%s: %s' %(key, value)
		                     for key, value in self.headers.items()] + [
		               '%s: %s' %(key, value)
		                      for key, value in self.headers_set]

		headers_set.insert(0, '%s %s' %(self.version, self._status))
		headers_set.append('\r\n')

		data = '\r\n'.join(headers_set) + data
		try:
			self.sockfile.write(data)
		except Disconnect:
			self.keep_alive = self.keep_alive and self.keep_alive.send(0)
			raise

		self.keep_alive = self.keep_alive.send(1) \
			if self.environ.get('HTTP_CONNECTION', '').lower() == 'keep-alive' \
			else self.sockfile.close() or self.keep_alive.send(0)

	def shutdown(self):
		self.sockfile.close()
		self.keep_alive = self.keep_alive and self.keep_alive.send(0)

def HttpHandler(controller, **environ):
	def handler(sock, addr):
		sockfile = SocketFile(sock, addr)
		try:
			httpfile = HttpFile(sockfile, **environ)

		except IOError:
			return

		tasklet(controller)(httpfile)
		receive = httpfile.keep_alive.receive
		del httpfile

		while receive():
			try:
				httpfile = HttpFile(sockfile, **environ)

			except IOError:
				return

			tasklet(controller)(httpfile)
			receive = httpfile.keep_alive.receive
			del httpfile

	return handler

def WsgiServer(application, bind=None, port=None, bindAddress=None):
	idx = None
	for i, j in enumerate((bind, port, bindAddress)):
		if j is not None:
			if idx is not None:
				raise TypeError('too many addresses')

			idx = i
	if idx is None:
		server = config(wsgi=application, port=8080)

	elif idx == 0:
		server = config(wsgi=application, bind=bind)

	elif idx == 1:
		server = config(wsgi=application, port=int(port))

	else:
		server = config(wsgi=application, bind=[bindAddress])

	return type('WsgiServer', (), dict(run=staticmethod(mainloop),
	                         serve_forever=staticmethod(mainloop)))()

def config(**args):
	handler = None
	for name in ('application', 'wsgi', 'app', 'wsgi_app', 'wsgi_application',
	 'httphandler', 'controller' , 'handler' , 'tcphandler', 'wsgihandler'):

		if name in args:
			if handler:
				raise TypeError('web.config(): too many handlers')

			handler = name

	if not handler:
		raise TypeError('web.config(): handler is required')

	elif handler in ('wsgi', 'app', 'application', 'wsgihandler',
	                     'wsgi_app'   , 'wsgi_application'):

		handler = wsgi(args[handler])
	else:
		handler = args[handler]

	if 'port' in args and 'bind' in args:
		raise TypeError('too many addresses')

	if   'port' in args:
		sockets = Sockets([('0.0.0.0', int(args['port']))], **args)
	elif 'bind' in args:
		sockets = Sockets(args['bind'], **args)
	else:
		sockets = Sockets([('0.0.0.0', 8080)], **args)

	if 'tcphandler' in args:
		for sock, environ in sockets:
			TcpServer(sock,  TcpHandler(handler))
	else:
		for sock, environ in sockets:
			TcpServer(sock, HttpHandler(handler, **environ))

WSGIServer = WsgiServer

NOCACHEHEADERS = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
	'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT' }

R_UID    = re.compile(r'(?:[^;]+;)* *uid=([^;\r\n]+)').search
R_FIRST  = re.compile(r'^(GET|POST)[\s\t]+([^\r\n]+)[\s\t]+(HTTP/1\.[0-9])\r?\n$', re.I).match
R_HEADER = re.compile(r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*\r?\n$', re.I).match
