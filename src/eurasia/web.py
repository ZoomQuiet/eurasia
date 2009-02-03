import re, sys, stackless
from _weakref import proxy
from string import Template
from sys import stdout, stderr
from traceback import print_exc
from time import gmtime, strftime, time
from stackless import channel, getcurrent, schedule, tasklet
from select import poll as Poll, error as SelectError, \
	POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
	ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode
from _socket import socket as Socket, error as SocketError, \
	AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_REUSEADDR

from BaseHTTPServer import BaseHTTPRequestHandler
RESPONSES = dict((key, value[0]) for key, value in BaseHTTPRequestHandler.responses.items())
del BaseHTTPRequestHandler, sys.modules['BaseHTTPServer']

class SocketFile:
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

	def fileno(self):
		return self.pid

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

	def shutdown(self):
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

class HttpFile(dict):
	def __init__(self, sockfile):
		first  = sockfile.readline(8192)
		try:
			method, self.path, version = R_FIRST(first).groups()
		except AttributeError:
			sockfile.close()
			raise IOError

		self.version = version.upper()
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

			dict.__setitem__(self, '-'.join(i.capitalize() for i in key.split('-')), value)
			line = sockfile.readline(8192)
			counter += len(line)
			if counter > 10240:
				sockfile.close()
				raise IOError

		self.method = method.upper()
		if self.method == 'GET':
			self.left = 0
		else:
			try:
				self.left = int(self['Content-Length'])
			except:
				sockfile.close()
				raise IOError

		self.content  = []
		self.respader = {}
		self.sockfile = sockfile
		self.closing  = channel()
		self.write = self.content.append

	def __del__(self):
		if hasattr(self, 'closing'):
			self.sockfile.close()
			self.closing.send(0)

	def __setitem__(self, key, value):
		self.respader['-'.join(i.capitalize() for i in key.split('-'))] = value

	@property
	def pid(self):
		return self.sockfile.pid

	@property
	def address(self):
		return self.sockfile.address

	def getuid(self):
		try:
			return R_UID(self['Cookie']).groups()[0]
		except:
			return None

	def setuid(self, uid):
		self.respader['Set-Cookie'] = 'uid=%s; path=/; expires=%s' %(
			uid, strftime('%a, %d-%b-%Y %H:%M:%S GMT', gmtime(time() + 157679616)))

	uid = property(getuid, setuid)
	del getuid, setuid

	def getstatus(self):
		return self._status

	def setstatus(self, status):
		self._status  = status
		self._message = RESPONSES[status]

	status, _status, _message = property(getstatus, setstatus), 200, RESPONSES[200]
	del getstatus, setstatus

	def fileno(self):
		return self.sockfile.pid

	def _write(self, data):
		if hasattr(self, 'closing'):
			try:
				self.sockfile.write(data)
			except Disconnect:
				self.closing.send(0)
				del self.closing
				raise
		else:
			raise Disconnect

	def begin(self):
		if not hasattr(self, 'closing'):
			raise Disconnect

		respader = ['%s: %s' %(key, value) for key, value in self.respader.items()]
		respader.insert(0, '%s %s %s' %(self.version, self._status, self._message))
		respader.append('\r\n')
		respader = '\r\n'.join(respader)

		self.write = self._write
		self.close = self.end

		try:
			self.sockfile.write(respader)
		except Disconnect:
			self.closing.send(0)
			del self.closing
			raise

	def end(self):
		if hasattr(self, 'closing'):
			self.sockfile.close()
			self.closing.send(0)
			del self.closing

	def close(self):
		if not hasattr(self, 'closing'):
			raise Disconnect

		data = ''.join(self.content)
		self.respader['Content-Length'] = str(len(data))

		respader = ['%s: %s' %(key, value) for key, value in self.respader.items()]
		respader.insert(0, '%s %s %s' %(self.version, self._status, self._message))
		respader.append('\r\n')
		respader = '\r\n'.join(respader)

		try:
			self.sockfile.write(respader + data)
		except Disconnect:
			self.closing.send(0)
			del self.closing
			raise

		if self.get('Connection', '').lower() == 'keep-alive':
			self.closing.send(1)
			del self.closing
		else:
			self.sockfile.close()
			self.closing.send(0)
			del self.closing

	def shutdown(self):
		if hasattr(self, 'closing'):
			self.sockfile.close()
			self.closing.send(0)
			del self.closing

def HttpHandler(controller):
	def handler(sock, addr):
		sockfile = SocketFile(sock, addr)
		try:
			httpfile = HttpFile(sockfile)
		except IOError:
			return

		tasklet(controller)(httpfile)

		while httpfile.closing.receive():
			try:
				httpfile = HttpFile(sockfile)
			except IOError:
				return

			tasklet(controller)(httpfile)

	return handler

def TcpHandler(controller):
	def handler(sock, addr):
		try:
			controller(SocketFile(sock, addr))
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
