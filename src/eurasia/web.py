from cgietc import wsgi, json, Form, SimpleUpload, Browser, Comet
from socket2 import mainloop0, mainloop, Disconnect, \
	SocketFile, TcpServerSocket, TcpServer

import re, sys
from _weakref import proxy
from stackless import channel, tasklet
from time import gmtime, strftime, time
from BaseHTTPServer import BaseHTTPRequestHandler
RESPONSES = dict((key, '%d %s' %(key, value[0]))
              for key, value in BaseHTTPRequestHandler.responses.items())

del BaseHTTPRequestHandler, sys.modules['BaseHTTPServer']

class HttpFile(object):
	def __init__(self, sockfile):
		first  = sockfile.readline(8192)
		try:
			method, path, version = R_FIRST(first).groups()
		except AttributeError:
			sockfile.close()
			raise IOError

		self.version = version.upper()
		self.method  = method =  method.upper()
		environ = dict(
			REQUEST_URI     =  path,
			REQUEST_METHOD  =  method,
			SERVER_PROTOCOL =  self.version)

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
		else:
			try:
				self.left = environ['CONTENT_LENGTH'] = int(
				            environ['HTTP_CONTENT_LENGTH'])
			except:
				sockfile.close()
				raise IOError

		self.uri = self.path = path

		p = path.find('?')
		if p != -1:
			environ['SCRIPT_NAME' ] = path[:p]
			environ['QUERY_STRING'] = path[p+1:]
		else:
			environ['SCRIPT_NAME' ] = path
			environ['QUERY_STRING'] = ''

		environ['REMOTE_ADDR'] = sockfile.address[0]
		environ['REMOTE_PORT'] = sockfile.address[1]

		self.content = []
		self.headers = {}
		self.headers_set = []
		self.environ = environ
		self.sockfile = sockfile
		self.keep_alive = channel()
		self.write = self.content.append

	def __del__(self):
		if hasattr(self, 'keep_alive'):
			return self.keep_alive and self.keep_alive.send(0)

	def __getitem__(self, key):
		return self.environ['HTTP_' + key.upper().replace('-', '_')]

	def __setitem__(self, key, value):
		self.headers['-'.join(i.capitalize() for i in key.split('-'))] = value

	pid          = property(lambda self: self.sockfile.pid)
	address      = property(lambda self: self.sockfile.address)
	script_name  = property(lambda self: self.environ['SCRIPT_NAME'])
	request_uri  = property(lambda self: self.environ['REQUEST_URI'])
	query_string = property(lambda self: self.environ['QUERY_STRING'])

	fileno  = lambda self: self.sockfile.pid
	nocache = lambda self: self.headers.update(NOCACHEHEADERS)

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

	def setstatus(self, status):
		self._status = status if isinstance(status, basestring) else RESPONSES[status]

	getstatus = lambda self: self._status
	status, _status = property(getstatus, setstatus), RESPONSES[200]
	del getstatus, setstatus

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

def HttpHandler(controller):
	def handler(sock, addr):
		sockfile = SocketFile(sock, addr)
		try:
			httpfile = HttpFile(sockfile)
		except IOError:
			return

		tasklet(controller)(httpfile)

		while httpfile.keep_alive.receive():
			try:
				httpfile = HttpFile(sockfile)
			except IOError:
				return

			tasklet(controller)(httpfile)

	return handler

def WsgiServer(application, bind=None, port=None, bindAddress=None):
	idx = None
	for i, j in enumerate((bind, port, bindAddress)):
		if j is not None:
			if idx is not None:
				raise TypeError('too many addresses')

			idx = i
	if idx is None:
		raise TypeError('\'bind\' is required')

	elif idx == 0:
		server = config(wsgi=application, bind=bind)

	elif idx == 1:
		server = config(wsgi=application, port=port)

	else:
		server = config(wsgi=application, bind='%s:%d' %bindAddress)

	server.serve_forever = server.run = mainloop
	return server

def config(**args):
	handler = None
	for name in ('httphandler', 'controller' , 'handler' , 'tcphandler', 'wsgihandler',
	             'application', 'wsgi', 'app', 'wsgi_app', 'wsgi_application'):

		if name in args:
			if handler:
				raise TypeError('web.config(): too many handlers')

			handler = name

	if not handler:
		raise TypeError('web.config(): handler is required')

	elif handler in ('wsgi', 'app', 'application', 'wsgihandler',
	                 'wsgi_app'   , 'wsgi_application'):

		handler = HttpHandler(wsgi(args[handler]))

	elif handler in ('handler', 'httphandler', 'controller'):
		handler = HttpHandler(args[handler])

	else:
		handler = TcpHandler(args['tcphandler'])

	if 'bind' in args:
		if 'port' in args:
			raise TypeError('web.config(): conflict between \'port\' and \'bind\'')

		for ip in [i for i in args['bind'].split(',') if i.strip()]:
			ip = ip.split(':')
			if len(ip) == 1:
				ip, port = ip[0].strip(), 80

			elif len(ip) == 2:
				try:
					ip, port = ip[0].strip(), int(ip[1].strip())
				except (ValueError, TypeError):
					raise ValueError('can\' bind to address %s' %ip.strip())

			return TcpServer(TcpServerSocket((ip, port)), handler)
	else:
		return TcpServer(TcpServerSocket(('0.0.0.0', args.get('port', 8080))), handler)

WSGIServer = WsgiServer

NOCACHEHEADERS = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
	'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT' }

R_UID    = re.compile(r'(?:[^;]+;)* *uid=([^;\r\n]+)').search
R_FIRST  = re.compile(r'^(GET|POST)[\s\t]+([^\r\n]+)[\s\t]+(HTTP/1\.[0-9])\r?\n$', re.I).match
R_HEADER = re.compile(r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*\r?\n$', re.I).match