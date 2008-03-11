import os.path
from copy import copy
from urlparse import urlparse
from StringIO import StringIO
from mimetools import Message
from sys import stdout, stderr
from re import compile as re_compile
from stackless import tasklet, schedule, channel
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
     ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode
from socket import fromfd, socket as Socket, error as SocketError, \
	AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_REUSEADDR
from select import POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL

try: from socket import ssl
except ImportError: ssl = None

try:
	from Eurasia import OverLimit, Disconnect
except ImportError:
	class OverLimit(IOError): pass
	class Disconnect(IOError): pass
	class ProtocolError(IOError): pass

def urlopen(url, data='', headers={}):
	if not R_PROTOCOL(url):
		url = 'http://' + url

	(scm, netloc, path, params, query, fragment
		) = urlparse(url)

	scm = scm.lower()
	if   scm == 'https': https = True
	elif scm == 'http' : https = False
	else:
		raise ProtocolError(scm)

	l = netloc.split(':')
	if len(l) == 1:
		host = l[0]
		port = https and 443 or 80
	elif len(l) == 2:
		host, port = l
		port = int(port)
	else:
		raise ValueError(url)

	sock = Socket(AF_INET, SOCK_STREAM)
	sock.setblocking(0)
	try:
		sock.setsockopt(SOL_SOCKET, SO_REUSEADDR,
			sock.getsockopt(SOL_SOCKET, SO_REUSEADDR) | 1)
	except SocketError:
		pass

	if https and ssl:
		err = sock.connect_ex((host, 80))
		if err not in (EINPROGRESS, EALREADY, EWOULDBLOCK,
			0, EISCONN):
			raise SocketError, (err, errorcode[err])
		sock = __import__('httplib').FakeSocket(
			sock, ssl(sock, None, None))
	else:
		err = sock.connect_ex((host, port))
		if err not in (EINPROGRESS, EALREADY, EWOULDBLOCK,
			0, EISCONN):
			raise SocketError, (err, errorcode[err])

	client = Client(sock, (host, port))

	path = path or '/'
	path = query and '%s?%s' %(path, query) or path

	if   isinstance(data, str):
		lw = len(data)
		read = StringIO(data).read
	elif isinstance(data, file):
		lw = int(os.path.getsize(data.name))
		read = data.read
	elif isinstance(data, StringIO):
		lw = int(data.len)
		read = data.read
	else:
		raise ValueError('data type %r' %type(data))

	if lw:
		method = 'POST'
		headers['Content-Length'] = str(lw)
	else:
		method = 'GET'

	headers = '\r\n'.join('%s: %s' %('-'.join(i.capitalize(
		) for i in key.split('-')), value
		) for key, value in headers.items() )

	pollster.register(client.pid, WE)
	if headers:
		client.wfile.send('%s %s HTTP/1.0\r\n%s\r\n\r\n' %(
			method, path, headers))
	else:
		client.wfile.send('%s %s HTTP/1.0\r\n\r\n' %(method, path))

	s = read(30720)
	while s:
		client.wfile.send(s)
		s = read(30720)

	client.wfile.send(None)
	pollster.register(client.pid, RE)
	client.headers = client.wait_headers.receive()

	return client

class Client:
	def __init__(self, sock, addr):
		self.socket  = sock
		self.address = addr
		self.pid = sock.fileno()

		self.writable = True; self.eof = False
		self.rbuff = self.rfile = self.wbuff = ''

		self.wfile = channel()
		self.wait_headers = channel()

		self.handle_read = self.handle_read_header
		socket_map[self.pid] = self

	def read(self, size=None):
		if not socket_map.has_key(self.pid) and not self.eof:
			raise Disconnect

		if size is None:
			buff = []
			data = self.rfile; self.rfile = ''
			if data: buff.append(data)
			while not self.eof:
				if not socket_map.has_key(self.pid):
					raise Disconnect
				pollster.register(self.pid, RE)
				schedule()
				data = self.rfile; self.rfile = ''
				if data: buff.append(data)

			return ''.join(buff)

		data = self.rfile; bufl = len(data)
		if bufl >= size:
			self.rfile = data[size:]
			return data[:size]

		buff = []
		while bufl < size:
			self.rfile = ''; buff.append(data)
			if self.eof: break
			if not socket_map.has_key(self.pid):
				raise Disconnect
			pollster.register(self.pid, RE)
			schedule()
			data = self.rfile; bufl += len(data)

		n = size - bufl
		if n == 0:
			buff.append(data)
			self.rfile = ''
		else:
			buff.append(data[:n])
			self.rfile = data[n:]

		return ''.join(buff)

	def readline(self, size=None):
		if not socket_map.has_key(self.pid) and not self.eof:
			raise Disconnect

		if size is None:
			nl = self.rfile.find('\n')
			if nl >= 0:
				nl += 1; self.rfile = self.rfile[nl:]
				return self.rfile[:nl]

			buff = [self.rfile]; self.rfile = ''
			while not self.eof:
				if not socket_map.has_key(self.pid):
					raise Disconnect
				pollster.register(self.pid, RE)
				schedule()

				data = self.rfile
				nl = data.find('\n')
				if nl >= 0:
					nl += 1; self.rfile = data[nl:]
					buff.append(data[:nl])
					return ''.join(buff)

				self.rfile = ''; buff.append(data)
			return ''.join(buff)

		data = self.rfile; bufl = len(data)
		nl = data.find('\n', 0, size)
		if nl >= 0:
			nl += 1; self.rfile = data[nl:]
			return data[:nl]
		if bufl >= size:
			self.rfile = data[size:]
			return data[:size]

		buff = []
		while bufl < size:
			self.rfile = ''; buff.append(data)
			if self.eof: break
			if not socket_map.has_key(self.pid):
				raise Disconnect
			pollster.register(self.pid, RE)
			schedule()

			data = self.rfile
			p = size - bufl; bufl += len(data)
			nl = data.find('\n', 0, p)
			if nl >= 0:
				nl += 1; self.rfile = data[nl:]
				buff.append(data[:nl])
				return ''.join(buff)

		n = size - bufl
		if n == 0:
			buff.append(data)
			self.rfile = ''
		else:
			buff.append(data[:n])
			self.rfile = data[n:]

		return ''.join(buff)

	def mk_header(self):
		rfile = StringIO(self.rfile)
		requestline = rfile.readline()[:-2]
		if not requestline:
			self.shutdown()
			return

		words = requestline.split(None, 2)
		if len(words) == 3:
			self.version, self.status, self.message = words
			if self.version[:5] != 'HTTP/':
				self.shutdown()
				return

		elif len(words) == 2:
			self.version, self.status = words

		else:
			self.shutdown()
			return

		headers, self.rfile = Message(rfile, 0), ''
		self.wait_headers.send(headers)

	def handle_read_header(self):
		try:
			data = self.socket.recv(8192)
			if not data:
				data = ''
				self.shutdown()

		except SocketError, why:
			if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
				data = ''
				self.shutdown()
			else:
				print >> stderr, 'error: socket error, client down'
				self.shutdown()
				return

		self.rbuff += data

		while self.rbuff:
			lb = len(self.rbuff)
			index = self.rbuff.find('\r\n\r\n')
			if index != -1:
				if index > 0:
					self.rfile += self.rbuff[:index]
				self.rbuff = self.rbuff[index + 4:]
				self.mk_header()

				self.handle_read = self.handle_read_content
				self.rfile, self.rbuff = self.rbuff, ''
				return
			else:
				index = 3
				while index and not self.rbuff.endswith('\r\n\r\n'[:index]):
					index -= 1

				if index:
					if index != lb:
						self.rfile += self.rbuff[:-index]
						self.rbuff = self.rbuff[-index:]
					break
				else:
					self.rfile += self.rbuff
					self.rbuff = ''

				if len(self.rfile) > 10240:
					self.shutdown()
					return

	def handle_read_content(self):
		try:
			data = self.socket.recv(8192)
			if not data:
				data = ''; self.eof = True
				self.shutdown()

		except SocketError, why:
			if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
				data = ''
				self.shutdown()
			else:
				print >> stderr, 'error: socket error, client down'
				self.shutdown()
				return

		self.rbuff += data

		self.rfile, self.rbuff = self.rfile + self.rbuff, ''
		if len(self.rfile) > 30720:
			try:
				pollster.unregister(self.pid)
			except KeyError:
				pass

	def handle_write(self):
		while len(self.wbuff) < 8192 and self.writable:
			s = self.wfile.receive()
			if s: self.wbuff += s
			else: self.writable = False

		if self.wbuff:
			try:
				num_sent = self.socket.send(self.wbuff[:8192])
			except SocketError, why:
				if why[0] == EWOULDBLOCK:
					num_sent = 0
				else:
					print >> stderr, 'error: socket error, client down'
					try:
						self.shutdown()
					except:
						pass
					return

			if num_sent:
				self.wbuff = self.wbuff[num_sent:]

	def handle_error(self):
		print >> stderr, 'error: fatal error, client down'
		self.shutdown()

	def shutdown(self):
		try:
			pollster.unregister(self.pid)
		except KeyError:
			pass

		try:
			del socket_map[self.pid]
		except KeyError:
			pass
		self.socket.close()

def config(**args):
	global pollster, socket_map
	if args.has_key('pollster'):
		pollster = args['pollster']
	if args.has_key('socket_map'):
		socket_map = args['socket_map']

pollster = socket_map = None

R_PROTOCOL = re_compile('^([^:]+)://').search

R = POLLIN | POLLPRI; W = POLLOUT
E = POLLERR | POLLHUP | POLLNVAL
RE = R | E; WE = W | E; RWE = R | W | E

__import__('urllib').urlopen = urlopen
