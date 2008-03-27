import stackless
import os, re, sys
from sys import stderr, stdout
from traceback import print_exc
from time import gmtime, strftime, time, sleep
from stackless import tasklet, schedule, channel
from select import poll as Poll, error as SelectError, \
	POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
	ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode
from socket import socket as Socket, error as SocketError, \
	AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_REUSEADDR

try:
	from Eurasia import Disconnect
except ImportError:
	class Disconnect(IOError): pass

class Client:
	def __init__(self, owner, sock, addr):
		self.pid = sock.fileno()
		self.controller = owner
		self.socket = sock
		self.address = addr

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

class Server:
	def __init__(self):
		global server_socket, serverpid
		server_socket = Socket(AF_INET, SOCK_STREAM)
		server_socket.setblocking(0)
		try:
			server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR,
				server_socket.getsockopt(SOL_SOCKET, SO_REUSEADDR) | 1)
		except SocketError:
			pass

		serverpid = server_socket.fileno()
		pollster.register(serverpid, RE)

	@staticmethod
	def handle_read():
		thread = tasklet(controller0)
		try:
			conn, addr = server_socket.accept()
			try:
				thread(Client(thread, conn, addr))
			except:
				print_exc(file=stderr)

		except SocketError, why:
			if why[0] == EWOULDBLOCK:
				pass
			else:
				print >> stderr, 'warning: server socket exception, ignore'
		except TypeError:
			pass

	@staticmethod
	def handle_error():
		print >> stderr, 'warning: server socket exception, ignore'

class DefaultClient(dict):
	def __init__(self, client):
		first = client.readline(8192)
		if first[-2:] != '\r\n':
			client.shutdown()
			raise IOError

		l = first[:-2].split(None, 2)
		if len(l) == 3:
			[method, self.path, version] = l
			self.version = version.upper()
			if self.version[:5] != 'HTTP/':
				client.shutdown()
				raise IOError

		elif len(l) == 2:
			[method, self.path] = l
			self.version = 'HTTP/1.0'
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

		self.method = method.upper()
		if self.method == 'GET':
			self.left = 0
		else:
			self.left = int(self['Content-Length'])

		self.address = client.address
		self.pid     = client.pid
		self.write   = client.write
		self.close   = client.shutdown
		self.client  = client

	@property
	def uid(self):
		try:
			return R_UID(self['Cookie']).groups()[0]
		except:
			return None

	def read(self, size=-1):
		if size == -1 or size >= self.left:
			data = self.client.read(self.left)
			self.left = 0
			return data
		else:
			data = self.client.read(size)
			self.left -= len(data)
			return data

	def readline(self, size=-1):
		if size == -1 or size >= self.left:
			data = self.client.readline(self.left)
		else:
			data = self.client.readline(size)

		self.left -= len(data)
		return data

def default0(client):
	try:
		client = DefaultClient(client)
	except IOError:
		return

	try:
		controller(client)
	except:
		print_exc(file=stderr)

def poll():
	while True:
		try:
			r = pollster.poll(1)
		except SelectError, e:
			if e[0] != EINTR:
				raise
			r = []

		for fd, flags in r:
			try:
				obj = socket_map[fd]
			except KeyError:
				continue

			if flags & R:
				obj.handle_read()
			if flags & W:
				obj.handle_write()
			if flags & E:
				obj.handle_error()

		schedule()

class nul:
	write = staticmethod(lambda s: None)
	flush = staticmethod(lambda  : None)
	read  = staticmethod(lambda n: ''  )

def config(**args):
	if not args.get('verbose', False):
		global stdout, stderr
		sys.stdout = sys.__stdout__ = stdout = args.get('stdout', nul)
		sys.stderr = sys.__stderr__ = stderr = args.get('stderr', nul)

	if args.has_key('controller0'):
		global controller0
		controller0 = args['controller0']

	elif args.has_key('controller'):
		global controller
		controller = args['controller']

	if args.has_key('address'):
		server_socket.bind(args['address'])
		server_socket.listen(4194304)

	elif args.has_key('port'):
		server_socket.bind((
			args.get('host', '0.0.0.0'),
			args.get('port', 8080)))

		server_socket.listen(4194304)

def mainloop():
	while True:
		try:
			stackless.run()

		except KeyboardInterrupt:
			break
		except:
			print_exc(file=stderr)
			continue

R = POLLIN | POLLPRI; W = POLLOUT
E = POLLERR | POLLHUP | POLLNVAL
RE = R | E; WE = W | E; RWE = R | W | E

R_UID = re.compile('(?:[^;]+;)* *uid=([^;\r\n]+)').search

controller0 = default0
pollster = Poll(); tasklet(poll)()
controller = server_socket = serverpid = None
socket_map = { serverpid: Server() }


try:
	import Eurasia

except ImportError:
	pass
else:
	for name, value in (('pollster', pollster), ('socket_map', socket_map),
		('response', '${version} ${status} ${message}')):

		setattr(Eurasia, name, value)

	for x in ('x-hypnus', 'x-aisarue'):
		try:
			__import__('Eurasia.%s' %x)
		except ImportError:
			pass

	try:
		m = getattr(__import__('Eurasia.x-request'), 'x-request')
	except ImportError:
		pass
	else:
		Form = m.Form
		SimpleUpload = m.SimpleUpload

	try:
		m = getattr(__import__('Eurasia.x-response'), 'x-response')
	except ImportError:
		pass
	else:
		Pushlet  = m.Pushlet
		Response = m.Response
