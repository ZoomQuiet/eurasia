import re, stackless
from sys import stdout, stderr
from traceback import print_exc
from stackless import channel, getcurrent, schedule, tasklet
from select import poll as Poll, error as SelectError, \
	POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
	ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode
from _socket import socket as Socket, error as SocketError, \
	AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_REUSEADDR

class Client:
	def __init__(self, sock, addr):
		self.socket = sock
		self.address = addr
		self.pid = sock.fileno()
		self._rbuf = self._wbuf = ''
		self.read_channel = channel()
		self.write_channel = channel()
		socket_map[self.pid] = self

	def __del__(self):
		if hasattr(self, 'pid'):
			try:
				pollster.unregister(self.pid)
			except KeyError:
				pass

			try:
				del socket_map[self.pid]
			except KeyError:
				pass

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
			try:
				pollster.unregister(self.pid)
			except KeyError:
				pass

			try:
				del socket_map[self.pid]
			except KeyError:
				pass

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
					else:
						print >> stderr, 'error: socket error, client down'
						try:
							self.close()
						except:
							pass

						self.read_channel = channel()
						self.tasklet.raise_exception(Disconnect)
						raise StopIteration

				if not data:
					break

				buffers.append(data)
				yield

			try:
				pollster.unregister(self.pid)
			except (KeyError, AttributeError):
				pass

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
					else:
						print >> stderr, 'error: socket error, client down'
						try:
							self.close()
						except:
							pass

						self.read_channel = channel()
						self.tasklet.raise_exception(Disconnect)
						raise StopIteration

				if not data:
					break

				buffers.append(data)
				n = len(data)
				if n >= left:
					self._rbuf = data[left:]
					buffers[-1] = data[:left]
					break

				buf_len += n
				yield

			try:
				pollster.unregister(self.pid)
			except (KeyError, AttributeError):
				pass

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
					else:
						print >> stderr, 'error: socket error, client down'
						try:
							self.close()
						except:
							pass

						self.read_channel = channel()
						self.tasklet.raise_exception(Disconnect)
						raise StopIteration
				if not data:
					break

				buffers.append(data)
				nl = data.find('\n')
				if nl >= 0:
					nl += 1
					self._rbuf = data[nl:]
					buffers[-1] = data[:nl]
					break
				yield

			try:
				pollster.unregister(self.pid)
			except (KeyError, AttributeError):
				pass

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
					else:
						print >> stderr, 'error: socket error, client down'
						try:
							self.close()
						except:
							pass

						self.read_channel = channel()
						self.tasklet.raise_exception(Disconnect)
						raise StopIteration
				if not data:
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

			try:
				pollster.unregister(self.pid)
			except (KeyError, AttributeError):
				pass

			self.read_channel.send(''.join(buffers))

	def write4raw(self):
		while self._wbuf:
			try:
				num_sent = self.socket.send(self._wbuf[:8192])

			except SocketError, why:
				if why[0] == EWOULDBLOCK:
					num_sent = 0
				else:
					print >> stderr, 'error: socket error, client down'
					try:
						self.close()
					except:
						pass

					self.write_channel = channel()
					self.tasklet.raise_exception(Disconnect)
					raise StopIteration

			if num_sent:
				self._wbuf = self._wbuf[num_sent:]

			yield

		try:
			pollster.unregister(self.pid)
		except (KeyError, AttributeError):
			pass

		self.write_channel.send(None)

	def handle_error(self):
		print >> stderr, 'error: fatal error, client down'

		self.close()
		self.tasklet.raise_exception(Disconnect)

class HttpClient(dict):
	def __init__(self, conn, addr):
		self.client = client = Client(conn, addr)
		first  = client.readline(8192)
		try:
			method, self.path, version = R_FIRST(first).groups()
		except AttributeError:
			client.close()
			raise Disconnect

		self.version = version.upper()
		line = client.readline(8192)
		counter = len(first) + len(line)
		while True:
			try:
				key, value = R_HEADER(line).groups()
			except AttributeError:
				if line in ('\r\n', '\n'):
					break

				client.close()
				raise Disconnect

			self['-'.join(i.capitalize() for i in key.split('-'))] = value
			line = client.readline(8192)
			counter += len(line)
			if counter > 10240:
				client.close()
				raise Disconnect

		self.method = method.upper()
		if self.method == 'GET':
			self.left = 0
		else:
			try:
				self.left = int(self['Content-Length'])
			except:
				client.close()
				raise Disconnect

		self.address = client.address
		self.write   = client.write
		self.close   = client.close
		self.pid     = client.pid

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

	def close(self, shutdown=True):
		if shutdown:
			return self.client.close()

		self._initialize(self.client)

def HttpHandler(controller):
	def handler(conn, addr):
		try:
			client = HttpClient(conn, addr)
		except Disconnect:
			return

		try:
			controller(client)
		except:
			print_exc(file=stderr)

	return handler

def TcpHandler(controller):
	def handler(conn, addr):
		try:
			controller(Client(conn, addr))
		except:
			print_exc(file=stderr)

	return handler

class Server:
	def __init__(self, address, handler):
		sock = Socket(AF_INET, SOCK_STREAM)
		sock.setblocking(0)
		try:
			sock.setsockopt(SOL_SOCKET, SO_REUSEADDR,
				sock.getsockopt(SOL_SOCKET, SO_REUSEADDR)|1)
		except SocketError:
			pass

		sock.bind(address)
		sock.listen(4194304)

		self.socket  = sock
		self.handler = handler
		self.address = address
		self.pid = sock.fileno()
		socket_map[self.pid] = self
		pollster.register(self.pid, RE)

	def handle_read(self):
		handler = tasklet(self.handler)
		try:
			conn, addr = self.socket.accept()
			try:
				handler(conn, addr)
			except:
				print_exc(file=stderr)

		except SocketError, why:
			if why[0] == EWOULDBLOCK:
				pass
			else:
				print >> stderr, 'warning: server socket exception, ignore'
		except TypeError:
			pass

	def handle_error(self):
		print >> stderr, 'warning: server socket exception, ignore'

def mainloop():
	while True:
		try:
			stackless.run()

		except KeyboardInterrupt:
			break
		except:
			print_exc(file=stderr)
			continue

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
				try:
					obj.handle_read()
				except StopIteration:
					pass
				except:
					print_exc(file=stderr)
			if flags & W:
				try:
					obj.handle_write()
				except StopIteration:
					pass
				except:
					print_exc(file=stderr)
			if flags & E:
				try:
					obj.handle_error()
				except:
					print_exc(file=stderr)

		schedule()

R, W, E = POLLIN|POLLPRI, POLLOUT, POLLERR|POLLHUP|POLLNVAL
RE, WE, RWE = R|E, W|E, R|W|E

socket_map, pollster, Disconnect = {}, Poll(), type('Disconnect', (IOError, ), {})
tasklet(poll)()

R_UID    = re.compile(r'(?:[^;]+;)* *uid=([^;\r\n]+)').search
R_FIRST  = re.compile(r'^(GET|POST)[\s\t]+([^\r\n]+)[\s\t]+(HTTP/1\.[0-9])\r?\n$', re.I).match
R_HEADER = re.compile(r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*\r?\n$', re.I).match
