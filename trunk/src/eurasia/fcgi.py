from cgietc import wsgi, json, Form, SimpleUpload, Browser, Comet
from socket2 import mainloop0, mainloop0 as mainloop, Disconnect, \
	SocketFile, TcpHandler, TcpServerSocket, TcpServer

import os, re, sys
from sys import stderr
from weakref import proxy
from time import gmtime, strftime, time
from struct import pack, unpack, calcsize
from stackless import channel, tasklet, getcurrent
from _socket import fromfd, error as SocketError, AF_INET, SOCK_STREAM, \
	SOL_SOCKET, SO_REUSEADDR, SO_REUSEADDR

import resource
c = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
capability = {'FCGI_MAX_CONNS': c, 'FCGI_MAX_REQS': c, 'FCGI_MPXS_CONNS': 1 }
del c, sys.modules['resource']

from BaseHTTPServer import BaseHTTPRequestHandler
RESPONSES = dict((key, '%d %s' %(key, value[0]))
              for key, value in BaseHTTPRequestHandler.responses.items())

del BaseHTTPRequestHandler, sys.modules['BaseHTTPServer']

class FcgiFile(object):
	def __init__(self):
		self._rbuf = ''
		self.headers = {}
		self.environ = {}
		self.content = []
		self.tasklet = None
		self.headers_set = []
		self.read_channel  = channel()
		self.write_channel = channel()
		self.write = self.content.append
		self.eof   = self.overflow = False
		self.handle_read = self.read4cache

	def __getitem__(self, key):
		return self.environ['HTTP_' + key.upper().replace('-', '_')]

	def __setitem__(self, key, value):
		self.headers['-'.join(i.capitalize() for i in key.split('-'))] = value

	def __del__(self):
		if hasattr(self, 'pid'):
			del self.requests[self.pid], self.pid

	@property
	def address(self):
		return self.environ['REMOTE_ADDR'], int(self.environ['REMOTE_PORT'])

	def get_request_uri(self):
		return self.environ['REQUEST_URI']

	def set_request_uri(self, uri):
		environ = self.environ
		environ['REQUEST_URI'] = uri

		p = uri.find('?')
		if p != -1:
			environ['SCRIPT_NAME' ] = uri[:p]
			environ['QUERY_STRING'] = uri[p+1:]
		else:
			environ['SCRIPT_NAME' ] = uri
			environ['QUERY_STRING'] = ''

	request_uri = property(get_request_uri, set_request_uri)
	del get_request_uri, set_request_uri

	def get_script_name(self):
		return self.environ['SCRIPT_NAME']

	def set_script_name(self, name):
		environ = self.environ
		environ['SCRIPT_NAME'] = name

		query = environ['QUERY_STRING']
		environ['REQUEST_URI'] = '%s?%s' %(name, query) if query else name

	script_name = property(get_script_name, set_script_name)
	del get_script_name, set_script_name

	def get_query_string(self):
		return self.environ['QUERY_STRING']

	def set_query_string(self, query):
		environ = self.environ
		environ['QUERY_STRING'] = query
		environ['REQUEST_URI' ] = '%s?%s' %(environ['SCRIPT_NAME'], query) \
		                    if   query \
		                    else environ['SCRIPT_NAME']

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

	def read(self, size=-1):
		if not hasattr(self, 'pid'):
			raise Disconnect

		read = self.read4raw(size).send
		data = read()
		if data is None:
			self.handle_read = read
			data = self.read_channel.receive()
			self.handle_read = self.read4cache
			return data

		self.handle_read = self.read4cache
		return data

	def readline(self, size=-1):
		if not hasattr(self, 'pid'):
			raise Disconnect

		read = self.read4line(size).send
		data = read()
		if data is None:
			self.handle_read = read
			data = self.read_channel.receive()
			self.handle_read = self.read4cache
			return data

		self.handle_read = self.read4cache
		return data

	def begin(self):
		headers_set = ['%s: %s' %(key, value)
		                      for key, value in self.headers.items()] + [
		               '%s: %s' %(key, value)
		                      for key, value in self.headers_set]

		headers_set.insert(0, 'Status: %s' %self._status)
		headers_set.append('\r\n')

		self.write = self._write
		self.write('\r\n'.join(headers_set))
		self.close = self.end = self.shutdown
		del self.headers, self.headers_set

	def wbegin(self, data=''):
		headers_set = ['%s: %s' %(key, value)
		                      for key, value in self.headers.items()] + [
		               '%s: %s' %(key, value)
		                      for key, value in self.headers_set]

		headers_set.insert(0, 'Status: %s' %self._status)
		headers_set.append('\r\n')

		self.write = self._write
		self.close = self.end = self.shutdown
		self.write('\r\n'.join(headers_set) + data)
		del self.headers, self.headers_set

	def close(self):
		data = ''.join(self.content)
		self.headers['Content-Length'] = str(len(data))
		headers_set = ['%s: %s' %(key, value)
		                      for key, value in self.headers.items()] + [
		               '%s: %s' %(key, value)
		                      for key, value in self.headers_set]

		headers_set.insert(0, 'Status: %s' %self._status)
		headers_set.append('\r\n')

		data = '\r\n'.join(headers_set) + data
		self._write(data)
		self.shutdown()

	def shutdown(self):
		if hasattr(self, 'pid'):
			p = -FCGI_ENDREQUESTBODY_LEN & 7
			r = pack('!BBHHBx', self.fcgi_version, 3, self.pid,
				FCGI_ENDREQUESTBODY_LEN, p) + pack('!LB3x', 0L, 0)
			if p:
				r += '\x00' * p

			self.sockfile.write(r)
			self.tasklet and self.tasklet.raise_exception(Disconnect)
			del self.requests[self.pid], self.pid

			if not (self.flags & 1) and not self.requests:
				self.sockfile.close()

	def _run(self, controller):
		tasklet(controller)(self)

	def _shutdown(self):
		if hasattr(self, 'pid'):
			self.tasklet and self.tasklet.raise_exception(Disconnect)
			del self.requests[self.pid], self.pid

	def _write(self, data):
		if not hasattr(self, 'pid'):
			raise Disconnect

		n = len(data)
		while n:
			to_write = min(n, 8184)
			r = data[:to_write]
			data = data[to_write:]
			n -= to_write

			p = -to_write & 7
			r = pack('!BBHHBx', self.fcgi_version, 6, self.pid,
				to_write, p) + r
			if p:
				r += '\x00' * p

			self.sockfile.write(r)

	def read4cache(self, data):
		if data:
			if len(self._rbuf) < max_size:
				self._rbuf += data
			else:
				self.eof = True
				self.overflow = True
		else:
			self.eof = True

	def read4raw(self, size=-1):
		data = self._rbuf
		if size < 0:
			self._rbuf = ''
			if self.eof:
				yield data
				raise StopIteration

			buffers = data and [data] or []
			self.tasklet = getcurrent()
			data = yield

			while True:
				if not data:
					self.eof = True
					break

				buffers.append(data)
				data = yield

			self.tasklet = None
			self.read_channel.send(''.join(buffers))
		else:
			buf_len = len(data)
			if buf_len >= size:
				self._rbuf = data[size:]
				yield data[:size]
				raise StopIteration

			if self.eof:
				self._rbuf = ''
				yield data
				raise StopIteration

			buffers = data and [data] or []
			self._rbuf = ''
			self.tasklet = getcurrent()
			data = yield

			while True:
				left = size - buf_len
				if not data:
					self.eof = True
					break

				buffers.append(data)
				n = len(data)
				if n >= left:
					self._rbuf = data[left:]
					buffers[-1] = data[:left]
					break

				buf_len += n
				data = yield

			self.tasklet = None
			self.read_channel.send(''.join(buffers))

	def read4line(self, size=-1):
		data = self._rbuf
		if size < 0:
			nl = data.find('\n')
			if nl >= 0:
				nl += 1
				self._rbuf = data[nl:]
				yield data[:nl]
				raise StopIteration

			if self.eof:
				self._rbuf = ''
				yield data
				raise StopIteration

			buffers = data and [data] or []
			self._rbuf = ''
			self.tasklet = getcurrent()
			data = yield

			while True:
				if not data:
					self.eof = True
					break

				buffers.append(data)
				nl = data.find('\n')
				if nl >= 0:
					nl += 1
					self._rbuf = data[nl:]
					buffers[-1] = data[:nl]
					break

				data = yield

			self.tasklet = None
			self.read_channel.send(''.join(buffers))
		else:
			nl = data.find('\n', 0, size)
			if nl >= 0:
				nl += 1
				self._rbuf = data[nl:]
				yield data[:nl]
				raise StopIteration

			buf_len = len(data)
			if buf_len >= size:
				self._rbuf = data[size:]
				yield data[:size]
				raise StopIteration

			if self.eof:
				self._rbuf = ''
				yield data
				raise StopIteration

			buffers = data and [data] or []
			self._rbuf = ''
			self.tasklet = getcurrent()
			data = yield

			while True:
				if not data:
					self.eof = True
					break

				buffers.append(data)
				left = size - buf_len
				nl = data.find('\n', 0, left)
				if nl >= 0:
					nl += 1
					self._rbuf = data[nl:]
					buffers[-1] = data[:nl]
					break

				n = len(data)
				if n >= left:
					self._rbuf = data[left:]
					buffers[-1] = data[:left]
					break

				buf_len += n
				data = yield

			self.tasklet = None
			self.read_channel.send(''.join(buffers))

def FcgiHandler(controller):
	def handler(sock, addr):
		sockfile = SocketFile(sock, addr)
		requests = {}
		while True:
			try:
				timeout = sockfile.read(8)
				if len(timeout) != 8:
					break

				fcgi_version, msgtype, record_id, record_length, \
					padding_length = unpack('!BBHHBx', timeout)

				record = sockfile.read(record_length)
				sockfile.read(padding_length)

			except Disconnect:
				for record_id, get_request in requests.items():
					get_request()._shutdown()

				break

			if msgtype == 5:
				request = requests[record_id]
				try:
					request.handle_read(record)
				except StopIteration:
					pass

			elif msgtype == 4:
				pos = 0
				request = requests[record_id]
				if record_length:
					while pos < record_length:
						pos ,   (name, value) = decode_pair(record, pos)
						request.environ[name] = value
				else:
					environ         = request.environ
					request.method  = environ['REQUEST_METHOD' ]
					request.version = environ['SERVER_PROTOCOL']
					request.uri     = request.path = environ['REQUEST_URI']
					if request.method == 'POST':
						environ['CONTENT_LENGTH'] = int(environ['CONTENT_LENGTH'])

					request._run(controller)

			elif msgtype == 9:
				pos = 0; s = ''
				while pos < record_length:
					pos, (name, value) = decode_pair(record, pos)
					try:
						s += encode_pair(name, str(capability[name]))
					except KeyError:
						pass

				l = len(s); p = -l & 7
				r = pack('!BBHHBx', fcgi_version, 10, 0, l, p) + s
				if p:
					r += '\x00' * p

				sockfile.write(r)

			elif msgtype == 1:
				role, flags = unpack('!HB5x', record)
				if role != 1:
					print >> stderr, 'warning: fastcgi unknow role, ignore'
				else:
					request = FcgiFile()
					request.role  = role
					request.flags = flags
					request.pid = record_id
					request.requests = requests
					request.sockfile = proxy(sockfile)
					request.fcgi_version = fcgi_version
					requests[record_id] = proxy(request)

			elif msgtype == 2:
				requests[record_id]._shutdown()

			elif msgtype == 8:
				print >> stderr, 'warning: fastcgi data record, ignore'

			elif record_id == 0:
				l = FCGI_UNKNOWNTYPEBODY_LEN; p = -l & 7
				r = pack('!BBHHBx', fcgi_version, 11, 0, l, p) + '!B7x'
				if p:
					r += '\x00' * p

				sockfile.write(r)
			else:
				print >> stderr, 'warning: fastcgi unknow record, ignore'

	return handler

def FcgiServerSocket():
	sock = fromfd(0, AF_INET, SOCK_STREAM)
	sock.setblocking(0)
	try:
		sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, sock.getsockopt(
		                SOL_SOCKET, SO_REUSEADDR)|1)
	except SocketError:
		pass

	return sock

def WsgiServer(application):
	server = config(wsgi=application)
	server.serve_forever = server.run = mainloop
	return server

def config(**args):
	handler = None
	for name in ('fcgihandler', 'controller' , 'handler' , 'wsgihandler'
	             'application', 'wsgi', 'app', 'wsgi_app', 'wsgi_application'):

		if name in args:
			if handler:
				raise TypeError('fcgi.config(): too many handlers')

			handler = name

	if not handler:
		raise TypeError('fcgi.config(): handler is required')

	elif handler in ('wsgi', 'app', 'application', 'wsgihandler',
	                 'wsgi_app'   , 'wsgi_application'):

		handler = FcgiHandler(wsgi(args[handler]))
	else:
		handler = FcgiHandler(args[handler])

	return TcpServer(FcgiServerSocket(), handler)

def decode_pair(s, pos=0):
	name_length = ord(s[pos])
	if name_length & 128:
		name_length = unpack('!L', s[pos:pos+4])[0] & 0x7fffffff
		pos += 4
	else:
		pos += 1

	value_length = ord(s[pos])
	if value_length & 128:
		value_length = unpack('!L', s[pos:pos+4])[0] & 0x7fffffff
		pos += 4
	else:
		pos += 1

	name = s[pos:pos+name_length]
	pos += name_length
	value = s[pos:pos+value_length]
	pos += value_length

	return (pos, (name, value))

def encode_pair(name, value):
	name_length = len(name)
	if name_length < 128:
		s = chr(name_length)
	else:
		s = pack('!L', name_length | 0x80000000L)

	value_length = len(value)
	if value_length < 128:
		s += chr(value_length)
	else:
		s += pack('!L', value_length | 0x80000000L)

	return s + name + value

max_size = 1073741824

WSGIServer = WsgiServer

FCGI_ENDREQUESTBODY_LEN  = calcsize('!LB3x')
FCGI_UNKNOWNTYPEBODY_LEN = calcsize('!B7x' )

NOCACHEHEADERS = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
	'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT' }

R_UID    = re.compile(r'(?:[^;]+;)* *uid=([^;\r\n]+)').search
R_FIRST  = re.compile(r'^(GET|POST)[\s\t]+([^\r\n]+)[\s\t]+(HTTP/1\.[0-9])\r?\n$', re.I).match
R_HEADER = re.compile(r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*\r?\n$', re.I).match
