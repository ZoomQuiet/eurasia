import socket as socket_module
from copy import copy
from httplib import FakeSocket
from stackless import tasklet, schedule, channel
from mimetools import Message
from urlparse import urlparse
from cStringIO import StringIO
from web import stderr, stdout, pollster, socket_map, \
	OverLimit, Disconnect, RE, WE
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
     ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode
from socket import fromfd, socket as Socket, error as SocketError, \
	AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_REUSEADDR

class ProtocolError(IOError): pass

class Aisarue:
	def __init__(self, url, data='', headers={},
		max_size=1048576, version='HTTP/1.0'):

		(scm, netloc, path, params, query,
			fragment) = urlparse(url)

		scm = scm.lower()
		if scm == 'https':
			https = True
		elif scm == 'http':
			https = False
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

		if https and hasattr(socket_module, 'ssl'):
			err = sock.connect_ex((host, 80))
			if err not in (EINPROGRESS, EALREADY, EWOULDBLOCK,
				0, EISCONN):
				raise SocketError, (err, errorcode[err])

			ssl = socket_module.ssl(sock, None, None)
			sock = FakeSocket(sock, ssl)
		else:
			err = sock.connect_ex((host, port))
			if err not in (EINPROGRESS, EALREADY, EWOULDBLOCK,
				0, EISCONN):
				raise SocketError, (err, errorcode[err])

		self.req = req = Client(sock, (host, port))

		path = path or '/'
		path = query and '%s?%s' %(path, query) or path

		method = 'POST'
		headers = copy(headers)
		if isinstance(data, str):
			if data:
				headers['Content-Length'] = str(len(data))
			else:
				method = 'GET'

			data = StringIO(data)

		headers = '\r\n'.join('%s: %s' %('-'.join(i.capitalize(
			) for i in key.split('-')), value
			) for key, value in headers.items() )
		headers = headers and headers + '\r\n' or ''

		req.wfile = '%s %s %s\r\n%s\r\n' %(
			method, path, version, headers)

		pollster.register(req.pid, WE)

		req.wfile += data.read(8192)
		while req.wfile:
			while req.wfile:
				schedule()
			req.wfile += data.read(8192)

		self.max_size = max_size
		pollster.register(req.pid, RE)
		while not hasattr(req, 'headers'):
			schedule()

		self.__getitem__ = req.headers.__getitem__
		self.keys = req.headers.keys

	@property
	def content_length(self):
		try:
			length = int(req['content_length'])
			if length > self.max_size:
				self.shutdown()
				raise OverLimit
		except:
			length = self.max_size

		return length

	def read(self, size=None):
		req = self.req
		pid = req.pid

		if req.closed:
			return ''
		if not socket_map.has_key(pid):
			raise Disconnect

		try:
			left = self.left
		except AttributeError:
			self.left = left = self.content_length

		data = req.rfile
		bufl = len(data)
		if bufl > left:
			req.shutdown()
			raise OverLimit

		if not size or size > left:
			size = left

		if bufl >= size:
			req.rfile = data[size:]
			self.left = left - size
			return data[:size]

		buff = []
		while bufl < size:
			req.rfile = ''
			buff.append(data)

			if not socket_map.has_key(pid):
				if req.closed:
					break
				raise Disconnect

			pollster.register(pid, RE)
			schedule()

			data = req.rfile
			bufl += len(data)
			if bufl > left:
				req.shutdown()
				raise OverLimit

		n = size - bufl
		if n == 0:
			buff.append(data)
			req.rfile = ''
		else:
			buff.append(data[:n])
			req.rfile = data[n:]

		self.left = left - size
		return ''.join(buff)

	def readline(self, size=None):
		req = self.req
		pid = req.pid

		if not socket_map.has_key(pid):
			raise Disconnect

		try:
			left = self.left
		except AttributeError:
			self.left = left = self.content_length

		data = req.rfile
		bufl = len(data)
		if bufl > left:
			req.shutdown()
			raise OverLimit

		nl = data.find('\n', 0, size)
		if nl >= 0:
			nl += 1
			req.rfile = data[nl:]
			self.left = left - nl
			return data[:nl]

		if not size or size > left:
			size = left

		if bufl >= size:
			req.rfile = data[size:]
			self.left = left - size
			return data[:size]

		buff = []
		while bufl < size:
			req.rfile = ''
			buff.append(data)

			if not socket_map.has_key(pid):
				if req.closed:
					break
				raise Disconnect

			pollster.register(pid, RE)
			schedule()

			data = req.rfile
			p = size - bufl
			bufl += len(data)
			if bufl > left:
				req.shutdown()
				raise OverLimit

			nl = data.find('\n', 0, p)
			if nl >= 0:
				nl += 1
				rfile = data[nl:]
				req.rfile = rfile
				buff.append(data[:nl])
				self.left = left + len(rfile) - bufl 
				return ''.join(buff)

		n = size - bufl
		if n == 0:
			buff.append(data)
			req.rfile = ''
		else:
			buff.append(data[:n])
			req.rfile = data[n:]

		self.left = left - size
		return ''.join(buff)

class Client:
	def __init__(self, sock, addr):
		self.socket  = sock
		self.address = addr
		self.pid = sock.fileno()

		socket_map[self.pid] = self
		pollster.register(self.pid, RE)

		self.closed = False
		self.rbuff = self.rfile = self.wfile = ''
		self.handle_read = self.handle_read_header

	def mk_header(self):
		rfile = StringIO(self.rfile)
		requestline = rfile.readline()[:-2]
		if not requestline:
			self.shutdown()
			return

		words = requestline.split()
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

		self.headers, self.rfile = Message(rfile, 0), ''
		self.__getitem__ = self.headers.getheader

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
				data = ''
				self.closed = True
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
		if self.wfile:
			try:
				num_sent = self.socket.send(self.wfile[:8192])
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
				self.wfile = self.wfile[num_sent:]

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

urlopen = Aisarue
