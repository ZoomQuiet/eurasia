from cgietc import wsgi, json, Form, SimpleUpload, Browser, Comet
from socket2 import mainloop0, mainloop as mainloop1, SSL, Disconnect, \
	SocketFile, Sockets, TcpServer

import os, re, sys
from sys import stderr
from weakref import proxy
from time import gmtime, strftime, time
from struct import pack, unpack, calcsize
from stackless import channel, tasklet, getcurrent

from BaseHTTPServer import BaseHTTPRequestHandler
RESPONSES = dict((key, '%d %s' %(key, value[0]))
              for key, value in BaseHTTPRequestHandler.responses.items())

del BaseHTTPRequestHandler, sys.modules['BaseHTTPServer']

try:
	import resource
	c = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
	capability = {'FCGI_MAX_CONNS': c, 'FCGI_MAX_REQS': c, 'FCGI_MPXS_CONNS': 1 }
	del c, sys.modules['resource']

except ImportError:
	capability = {'FCGI_MAX_CONNS': 100, 'FCGI_MAX_REQS': 500, 'FCGI_MPXS_CONNS': 1 }

class FcgiFile(object):
	def __init__(self):
		self._rbuf = ''
		self.headers = {}
		self.environ = {}
		self.content = []
		self.headers_set = []
		self.working_channel = None
		self.read_channel  = channel()
		self.write_channel = channel()
		self.write = self.content.append
		self.eof   = self.overflow = False
		self.handle_read = self.read4cache

	def __iter__(self):
		data = self.readline()
		while data:
			yield data
			data = self.readline()

	def __del__(self):
		if hasattr(self, 'pid'):
			del self.requests[self.pid], self.pid

	def __len__(self):
		return int(self.environ['HTTP_CONTENT_LENGTH'])

	def __getitem__(self, key):
		return self.environ['HTTP_' + key.upper().replace('-', '_')]

	def __setitem__(self, key, value):
		self.headers['-'.join(i.capitalize() for i in key.split('-'))] = value

	def __contains__(self, key):
		return 'HTTP_' + key.upper().replace('-', '_') in self.environ

	@property
	def address(self):
		return self.environ['REMOTE_ADDR'], int(self.environ['REMOTE_PORT'])

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

	def writelines(self, seq):
		for line in seq:
			self.write(line)

	def flush(self):
		pass

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
			self.working_channel and self.working_channel.send_exception(Disconnect, Disconnect())
			del self.requests[self.pid], self.pid

			if not (self.flags & 1) and not self.requests:
				self.sockfile.close()

	def _run(self, controller):
		tasklet(controller)(self)

	def _shutdown(self):
		if hasattr(self, 'pid'):
			self.working_channel and self.working_channel.send_exception(Disconnect, Disconnect())
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
			self.working_channel = self.read_channel
			data = yield

			while True:
				if not data:
					self.eof = True
					break

				buffers.append(data)
				data = yield

			self.working_channel = None
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
			self.working_channel = self.read_channel
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

			self.working_channel = None
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
			self.working_channel = self.read_channel
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

			self.working_channel = None
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
			self.working_channel = self.read_channel
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

			self.working_channel = None
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
					setdefault      = environ.setdefault
					request.method  = environ['REQUEST_METHOD' ]
					request.version = environ['SERVER_PROTOCOL']
					request.uri     = request.path = environ['REQUEST_URI']

					setdefault('PATH_INFO', '')
					setdefault('HTTP_CONTENT_TYPE'  , setdefault('CONTENT_TYPE'  , '' ))
					setdefault('HTTP_CONTENT_LENGTH', setdefault('CONTENT_LENGTH', '0'))

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

def WsgiServer(application, bind=None, port=None, bindAddress=None):
	idx = None
	for i, j in enumerate((bind, port, bindAddress)):
		if j is not None:
			if idx is not None:
				raise TypeError('too many addresses')

			idx = i
	if idx is None:
		server = config(wsgi=application)

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

		handler = wsgi(args[handler])
	else:
		handler = args[handler]

	if 'port' not in args and 'bind' not in args:
		globals()['ignore_cpus'] = True
		sockets = Sockets('fromfd:0')

	elif 'port' in args:
		sockets = Sockets([('0.0.0.0', args['port'])])
	else:
		sockets = Sockets(args['bind'])

	for sock, environ in sockets:
		TcpServer(sock, FcgiHandler(handler))

def mainloop(cpus=False):
	if globals().get('ignore_cpus', False):
		return mainloop0()

	mainloop1(cpus)

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

R_SCRPTH = re.compile(r'/+$').split
R_UID    = re.compile(r'(?:[^;]+;)* *uid=([^;\r\n]+)').search
R_FIRST  = re.compile(r'^(GET|POST)[\s\t]+([^\r\n]+)[\s\t]+(HTTP/1\.[0-9])\r?\n$', re.I).match
R_HEADER = re.compile(r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*\r?\n$', re.I).match
