import os, sys
import stackless
from _weakref import proxy
from sys import stdout, stderr
from traceback import print_exc
from stackless import channel, getcurrent, schedule, tasklet
from errno import EWOULDBLOCK, ECONNRESET, ENOTCONN, ESHUTDOWN, EINTR
from _socket import socket as Socket, error as SocketError, \
	AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_REUSEADDR

try:
	from py.magic import greenlet
except ImportError:
	pass
else:
	class GWrap(greenlet):
		def raise_exception(self, e):
			self.throw(e)

	stackless.GWrap = GWrap
	del GWrap

try:
	from select import poll as Poll, error as SelectError, \
		POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL
except ImportError:
	from select import select, error as SelectError
	def poll(timeout):
		a, b, c = select(r.keys(), w.keys(), e.keys(), 0.0001)
		return [(i, R) for i in a] + [(i, W) for i in b] + [(i, E) for i in c]

	def register(pid, flag):
		if flag & R:
			e[pid] = r[pid] = None
			if flag & W:
				w[pid] = None
			else:
				try:
					del w[pid]
				except KeyError:
					pass
		elif flag & W:
			e[pid] = w[pid] = None
			try:
				del r[pid]
			except KeyError:
				pass
		elif flag & E:
			e[pid] = None
			try:
				del r[pid]
			except KeyError:
				pass
			try:
				del w[pid]
			except KeyError:
				pass

	def unregister(pid):
		try: del r[pid]
		except KeyError: pass
		try: del w[pid]
		except KeyError: pass
		try: del e[pid]
		except KeyError: pass

	Poll = lambda: type('poll', (), { 'poll': staticmethod(poll),
			'register'  : staticmethod(register  ),
			'unregister': staticmethod(unregister)})

	del poll, register, unregister

	r, w, e = {}, {}, {}
	POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL = 1, 2, 4, 8, 16, 32

class SocketFile:
	fileno = lambda self: self.pid

	def __init__(self, sock, addr):
		self.socket = sock
		self.address = addr
		self.pid = sock.fileno()
		self._rbuf = self._wbuf = ''
		self.read_channel = channel()
		self.write_channel = channel()
		socket_map[self.pid] = proxy(self)

	def __del__(self):
		if hasattr(self, 'pid'):
			try: pollster.unregister(self.pid)
			except KeyError: pass
			try: del socket_map[self.pid]
			except KeyError: pass
			self.socket.close()
			del self.pid

	def read(self, size=-1):
		if not hasattr(self, 'pid'):
			raise Disconnect

		read = self.read4raw(size).next
		data = read()
		if data is None:
			self.handle_read = read
			pollster.register(self.pid, RE)
			return self.read_channel.receive()

		return data

	def readline(self, size=-1):
		if not hasattr(self, 'pid'):
			raise Disconnect

		read = self.read4line(size).next
		data = read()
		if data is None:
			self.handle_read = read
			pollster.register(self.pid, RE)
			return self.read_channel.receive()

		return data

	def write(self, data):
		if not hasattr(self, 'pid'):
			raise Disconnect

		self._wbuf        = data
		self.tasklet      = getcurrent()
		self.handle_write = self.write4raw().next
		pollster.register(self.pid, WE)
		return self.write_channel.receive()

	def close(self):
		if hasattr(self, 'pid'):
			try: pollster.unregister(self.pid)
			except KeyError: pass
			try: del socket_map[self.pid]
			except KeyError: pass
			self.socket.close()
			del self.pid

	def shutdown(self):
		if hasattr(self, 'pid'):
			try: pollster.unregister(self.pid)
			except KeyError: pass
			try: del socket_map[self.pid]
			except KeyError: pass
			self.socket.close()
			del self.pid

	def read4raw(self, size=-1):
		data = self._rbuf
		if size < 0:
			buffers = data and [data] or []
			self._rbuf   = ''
			self.tasklet = getcurrent()
			yield

			while True:
				try:
					data = self.socket.recv(8192)
				except SocketError, why:
					if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
						data = ''
						self.close()
						break
					else:
						try: self.close()
						except: pass

						self.read_channel = channel()
						self.tasklet.raise_exception(Disconnect)
						raise StopIteration

				if not data:
					self.close()
					break

				buffers.append(data)
				yield

			try: pollster.unregister(self.pid)
			except (KeyError, AttributeError): pass

			self.tasklet = None
			self.read_channel.send(''.join(buffers))
		else:
			buf_len = len(data)
			if buf_len >= size:
				self._rbuf = data[size:]
				yield data[:size]
				raise StopIteration

			buffers = data and [data] or []
			self._rbuf   = ''
			self.tasklet = getcurrent()
			yield

			while True:
				left = size - buf_len
				try:
					data = self.socket.recv(max(8192, left))
				except SocketError, why:
					if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
						data = ''
						self.close()
						break
					else:
						try: self.close()
						except: pass

						self.read_channel = channel()
						self.tasklet.raise_exception(Disconnect)
						raise StopIteration

				if not data:
					self.close()
					break

				buffers.append(data)
				n = len(data)
				if n >= left:
					self._rbuf = data[left:]
					buffers[-1] = data[:left]
					break

				buf_len += n
				yield

			try: pollster.unregister(self.pid)
			except (KeyError, AttributeError): pass

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

			buffers = data and [data] or []
			self._rbuf   = ''
			self.tasklet = getcurrent()
			yield

			while True:
				try:
					data = self.socket.recv(8192)
				except SocketError, why:
					if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
						data = ''
						self.close()
						break
					else:
						try: self.close()
						except: pass

						self.read_channel = channel()
						self.tasklet.raise_exception(Disconnect)
						raise StopIteration
				if not data:
					self.close()
					break

				buffers.append(data)
				nl = data.find('\n')
				if nl >= 0:
					nl += 1
					self._rbuf = data[nl:]
					buffers[-1] = data[:nl]
					break
				yield

			try: pollster.unregister(self.pid)
			except (KeyError, AttributeError): pass

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

			buffers = data and [data] or []
			self._rbuf   = ''
			self.tasklet = getcurrent()
			yield

			while True:
				try:
					data = self.socket.recv(8192)
				except SocketError, why:
					if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
						data = ''
						self.close()
						break
					else:
						try: self.close()
						except: pass

						self.read_channel = channel()
						self.tasklet.raise_exception(Disconnect)
						raise StopIteration
				if not data:
					self.close()
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
				yield

			try: pollster.unregister(self.pid)
			except (KeyError, AttributeError): pass

			self.tasklet = None
			self.read_channel.send(''.join(buffers))

	def write4raw(self):
		while self._wbuf:
			try:
				num_sent = self.socket.send(self._wbuf[:8192])

			except SocketError, why:
				if why[0] == EWOULDBLOCK:
					num_sent = 0
				else:
					try: self.close()
					except: pass

					self.write_channel = channel()
					self.tasklet.raise_exception(Disconnect)
					raise StopIteration
			if num_sent:
				self._wbuf = self._wbuf[num_sent:]

			yield

		try: pollster.unregister(self.pid)
		except (KeyError, AttributeError): pass

		self.tasklet = None
		self.write_channel.send(None)

	def handle_error(self):
		self.close()
		self.tasklet and self.tasklet.raise_exception(Disconnect)

def TcpHandler(controller):
	def handler(sock, addr):
		try:
			controller(SocketFile(sock, addr))
		except:
			print_exc(file=stderr)

	return handler

def TcpServerSocket(address):
	sock = Socket(AF_INET, SOCK_STREAM)
	sock.setblocking(0)
	try:
		sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, sock.getsockopt(
		                SOL_SOCKET, SO_REUSEADDR)|1)
	except SocketError:
		pass

	sock.bind(address)
	sock.listen(4194304)
	return sock

class TcpServer:
	def __init__(self, sock, handler):
		self.socket  = sock
		self.handler = handler
		self.pid     = sock.fileno()
		self.address = sock.getsockname()
		socket_map[self.pid] = self
		pollster.register(self.pid, RE)

	def handle_read(self):
		try:
			conn, addr = self.socket.accept()

		except SocketError, why:
			if why[0] == EWOULDBLOCK:
				return

		except TypeError:
			pass
		else:
			tasklet(self.handler)(conn, addr)

	def handle_error(self):
		pass

def config(**args):
	handler = None
	for name in ('controller' , 'handler' , 'tcphandler'):
		if name in args:
			if handler is not None:
				raise TypeError('too many handlers')

			handler = name

	if not handler:
		raise TypeError('handler is required')

	if 'bind' in args:
		if 'port' in args:
			raise TypeError('too many addresses')

		for ip in [i for i in args['bind'].split(',') if i.strip()]:
			ip = ip.split(':')
			if len(ip) == 1:
				ip, port = ip[0].strip(), 80

			elif len(ip) == 2:
				try:
					ip, port = ip[0].strip(), int(ip[1].strip())
				except (ValueError, TypeError):
					raise ValueError('can\' bind to address %s' %ip.strip())

			return TcpServer(TcpServerSocket((ip, port)), TcpHandler(args[handler]))
	else:
		return TcpServer(TcpServerSocket(('0.0.0.0', args.get('port', 8080))),
		                 TcpHandler(args[handler]))

def mainloop(cpus=False):
	if isinstance(cpus, bool):
		cpus = cpu_count() if cpus else 1

	if cpus < 2:
		return mainloop0()

	try:
		from os import fork
	except ImportError:
		return mainloop0()

	for i in '\x00' * (cpus - 1):
		if fork() == 0:
			mainloop0()
			sys.exit(0)

	mainloop0()

def poll():
	while True:
		try:
			r = pollster.poll(1)
		except SelectError, e:
			if e[0] != EINTR:
				raise
			r = []

		for fd, flags in r:
			try: obj = socket_map[fd]
			except KeyError: continue

			if flags & R:
				try: obj.handle_read()
				except StopIteration: pass
				except: print_exc(file=stderr)

			if flags & W:
				try: obj.handle_write()
				except StopIteration: pass
				except: print_exc(file=stderr)

			if flags & E:
				try: obj.handle_error()
				except: print_exc(file=stderr)

		schedule()

def mainloop0():
	while True:
		try:
			stackless.run()
		except KeyboardInterrupt:
			break
		except:
			print_exc(file=stderr)
			continue

def cpu_count():
	if sys.platform == 'win32':
		try:
			return int(os.environ['NUMBER_OF_PROCESSORS'])
		except (ValueError, KeyError):
			return 0

	elif sys.platform == 'darwin':
		try:
			return int(os.popen('sysctl -n hw.ncpu').read())
		except ValueError:
			return 0
	else:
		try:
			return os.sysconf('SC_NPROCESSORS_ONLN')
		except (ValueError, OSError, AttributeError):
			return 0

R, W, E = POLLIN|POLLPRI, POLLOUT, POLLERR|POLLHUP|POLLNVAL
RE, WE, RWE = R|E, W|E, R|W|E

socket_map, pollster, Disconnect = {}, Poll(), type('Disconnect', (IOError, ), {})
tasklet(poll)()
