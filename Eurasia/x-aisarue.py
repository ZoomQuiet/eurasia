import os.path
import re, urllib
from copy import copy
from urlparse import urlparse
from StringIO import StringIO
from sys import stdout, stderr
from Eurasia import pollster, socket_map
from stackless import tasklet, schedule, channel, getcurrent
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
     ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode
from socket import fromfd, socket as Socket, error as SocketError, \
	AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_REUSEADDR
from select import POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL

class Client:
	def __init__(self, owner, sock, addr):
		self.pid = sock.fileno()
		self.controller = owner
		self.socket = sock; self.address = addr

		self.eof = False
		self.rfile = channel()
		self.wlock = channel()
		self.rbuff = self.wfile = ''
		socket_map[self.pid] = self

	def read(self, size=-1):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		if size == -1:
			if self.eof:
				return ''
		else:
			if len(self.rbuff) >= size:
				data, self.rbuff = self.rbuff[:size], self.rbuff[size:]
				return data
			elif self.eof:
				data, self.rbuff = self.rbuff, ''
				return data

		self.to_read = size
		self.handle_read = self.read4raw
		pollster.register(self.pid, RE)
		return self.rfile.receive()

	def readline(self, size=-1):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		if size == -1:
			p = self.rbuff.find('\n')
			if p == -1:
				if self.eof:
					data, self.rbuff = self.rbuff, ''
					return data
			else:
				p += 1
				data, self.rbuff = self.rbuff[:p], self.rbuff[p:]
				return data
		else:
			p = self.rbuff.find('\n', 0, size)
			if p == -1:
				if len(self.rbuff) >= size:
					data, self.rbuff = self.rbuff[:size], self.rbuff[size:]
					return data
				if self.eof:
					data, self.rbuff = self.rbuff, ''
					return data
			else:
				p += 1
				data, self.rbuff = self.rbuff[:p], self.rbuff[p:]
				return data

		self.to_read = size
		data, self.rbuff = self.rbuff, ''
		self.buff = [data]; self.bufl = len(data)
		self.handle_read = self.read4line
		pollster.register(self.pid, RE)
		return self.rfile.receive()

	def write(self, data):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		self.wfile = data
		pollster.register(self.pid, WE)
		return self.wlock.receive()

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
						self.controller.raise_exception(Disconnect)
					except:
						pass
					return

			if num_sent:
				self.wfile = self.wfile[num_sent:]

			if not self.wfile:
				pollster.unregister(self.pid)
				self.wlock.send(None)

			return

		pollster.unregister(self.pid)
		self.wlock.send(None)

	def handle_error(self):
		print >> stderr, 'error: fatal error, client down'
		self.shutdown()
		self.controller.raise_exception(Disconnect)

	def read4raw(self):
		try:
			data = self.socket.recv(8192)

		except SocketError, why:
			if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
				data = ''
			else:
				print >> stderr, 'error: socket error, client down'
				self.shutdown()
				self.controller.raise_exception(Disconnect)
				return

		size = self.to_read
		if size == -1:
			if data:
				self.rbuff += data
			else:
				self.eof = True
				data, self.rbuff = self.rbuff, ''

				self.shutdown()
				self.rfile.send(data)

			return

		if data:
			self.rbuff += data
			if len(self.rbuff) >= size:
				data, self.rbuff = self.rbuff[:size], self.rbuff[size:]

				pollster.unregister(self.pid)
				self.rfile.send(data)
		else:
			self.eof = True
			data, self.rbuff = self.rbuff, ''

			self.shutdown()
			self.rfile.send(data)

	def read4line(self):
		try:
			data = self.socket.recv(8192)

		except SocketError, why:
			if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
				data = ''
			else:
				print >> stderr, 'error: socket error, client down'
				self.shutdown()
				self.controller.raise_exception(Disconnect)
				return

		size = self.to_read
		if size == -1:
			if data:
				p = data.find('\n')
				if p == -1:
					self.buff.append(data)
				else:
					p += 1
					self.buff.append(data[:p])
					self.rbuff = data[p:]

					pollster.unregister(self.pid)
					self.rfile.send(''.join(self.buff))
			else:
				self.eof = True
				self.rbuff = ''

				self.shutdown()
				self.rfile.send(''.join(self.buff))
		else:
			if data:
				left = size - self.bufl
				p = data.find('\n', 0, left)
				if p == -1:
					if len(data) - left >= 0:
						data, self.rbuff = data[:left], data[left:]
						self.buff.append(data)

						pollster.unregister(self.pid)
						self.rfile.send(''.join(self.buff))
					else:
						self.buff.append(data)
						self.bufl += len(data)
				else:
					p += 1
					self.buff.append(data[:p])
					self.rbuff = data[p:]

					pollster.unregister(self.pid)
					self.rfile.send(''.join(self.buff))
			else:
				self.eof = True
				self.rbuff = ''

				self.shutdown()
				self.rfile.send(''.join(self.buff))

def urlopen(url, data='', headers={}, **args):
	headers = dict(('-'.join(i.capitalize() for i in key.split('-')), value
		) for key, value in headers.items() )
	for key, value in args.items():
		headers['-'.join(i.capitalize() for i in key.split('_'))] = value

	scm, netloc, path, params, query, fragment = urlparse(url)
	https = scm.lower() == 'https'
	netloc = netloc.split(':')
	host = netloc[0]
	try:
		port = netloc[1]
	except IndexError:
		port = https and 443 or 80

	sock = Socket(AF_INET, SOCK_STREAM)
	sock.setblocking(0)
	try:
		sock.setsockopt(
			SOL_SOCKET, SO_REUSEADDR,
			sock.getsockopt(
				SOL_SOCKET, SO_REUSEADDR) | 1)
	except SocketError:
		pass

	if https and ssl:
		err = sock.connect_ex((host, 80))
		if err not in (EINPROGRESS, EALREADY, EWOULDBLOCK, 0, EISCONN):
			raise SocketError, (err, errorcode[err])

		sock = __import__('httplib').FakeSocket(
			sock, ssl(sock, None, None))
	else:
		err = sock.connect_ex((host, port))
		if err not in (EINPROGRESS, EALREADY, EWOULDBLOCK, 0, EISCONN):
			raise SocketError, (err, errorcode[err])

	path = path or '/'
	path = query and '%s?%s' %(path, query) or path

	if   isinstance(data, str):
		l = len(data)
		read = StringIO(data).read

	elif isinstance(data, file):
		l = int(os.path.getsize(data.name))
		read = data.read

	elif hasattr(data, 'read'):
		if not callable(data.read):
			raise ValueError('data type %r' %type(data))

		read = data.read
		if hasattr(data, 'len'):
			l = int(data.len)
		elif hasattr(data, '__len__') and callable(data, '__len__'):
			l = len(data)
		elif headers.has_key('Content-Length'):
			l = int(headers['Content-length'])
		else:
			data = read()
			l = len(data)
			read = StringIO(data).read

	if l:
		method = 'POST'
		headers['Content-Length'] = str(l)
	else:
		method = 'GET'

	if not headers.has_key('Host'): headers['Host'] = host
	headers = '\r\n'.join('%s: %s' %(key, value) for key, value in headers.items())

	client = Client(getcurrent(), sock, (host, port))
	client.write(headers and (
		'%s %s HTTP/1.0\r\n%s\r\n\r\n' %( method, path, headers
		)) or '%s %s HTTP/1.0\r\n\r\n' %( method, path ) )

	data = read(30720)
	while data:
		client.write(data)
		data = read(30720)

	return DefaultClient(client)

class DefaultClient(dict):
	def __init__(self, client):
		first = client.readline(8192)
		if first[-2:] != '\r\n':
			client.shutdown()
			raise IOError

		l = first[:-2].split(None, 2)
		if len(l) == 3:
			version, self.status, self.message = l
			self.version = version.upper()
			if self.version[:5] != 'HTTP/':
				client.shutdown()
				raise IOError

		elif len(l) == 2:
			version, self.status = l
			self.version = version.upper()
			self.message = ''
		else:
			client.shutdown()
			raise IOError

		counter = len(first)
		line = client.readline(8192)
		while line != '\r\n':
			if line[-2:] != '\r\n':
				client.shutdown()
				raise IOError

			counter += len(line)
			if counter > 10240:
				client.shutdown()
				raise IOError

			try: key, value = line[:-2].split(':', 1)
			except ValueError:
				continue

			self['-'.join(i.capitalize() for i in key.split('-'))] = value.strip()
			line = client.readline(8192)

		self.close = client.shutdown
		self.read  = client.read
		self.readline = client.readline
		self.client = client

	@property
	def uid(self):
		try:
			return R_UID(self['Cookie']).groups()[0]
		except:
			return None

R = POLLIN | POLLPRI; W = POLLOUT
E = POLLERR | POLLHUP | POLLNVAL
RE = R | E; WE = W | E; RWE = R | W | E

R_UID = re.compile('(?:[^;]+;)* *uid=([^;\r\n]+)').search
urllib.urlopen = urlopen
