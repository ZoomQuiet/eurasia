import sys
from traceback import print_exc
from stackless import channel, getcurrent, schedule, tasklet
from select import poll as Poll, error as SelectError, \
	POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
	ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode
from _socket import socket as Socket, error as SocketError, \
	AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_REUSEADDR

class Disconnect(IOError):
	pass

class Client:
	def __init__(self, sock, addr):
		self.socket = sock
		self.address = addr
		self.pid = sock.fileno()
		self.tasklet = getcurrent()
		self._rbuf = self._wbuf = ''
		self.read_channel = channel()
		self.write_channel = channel()
		socket_map[self.pid] = self

	def read(self, size=-1):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		read = self.read4raw(size).next
		data = read()
		if data is None:
			self.handle_read = read
			pollster.register(self.pid, RE)
			return self.read_channel.receive()

		return data

	def readline(self, size=-1):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		read = self.read4line(size).next
		data = read()
		if data is None:
			self.handle_read = read
			pollster.register(self.pid, RE)
			return self.read_channel.receive()

		return data

	def write(self, data):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		self._wbuf = data
		self.handle_write = self.write4raw().next
		pollster.register(self.pid, WE)
		return self.write_channel.receive()

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

	def read4raw(self, size=-1):
		data = self._rbuf
		if size < 0:
			buffers = data and [data] or []
			self._rbuf = ''
			yield

			while True:
				try:
					data = self.socket.recv(8192)
				except SocketError, why:
					if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
						data = ''
						self.shutdown()
					else:
						print >> sys.stderr, 'error: socket error, client down'
						try:
							self.shutdown()
						except:
							pass

						self.read_channel = channel()
						self.tasklet.raise_exception(Disconnect)
						raise StopIteration

				if not data:
					break

				buffers.append(data)
				yield

			pollster.unregister(self.pid)
			self.read_channel.send(''.join(buffers))
		else:
			buf_len = len(data)
			if buf_len >= size:
				self._rbuf = data[size:]
				yield data[:size]
				raise StopIteration

			buffers = data and [data] or []
			self._rbuf = ''
			yield
			while True:
				left = size - buf_len
				try:
					data = self.socket.recv(max(8192, left))
				except SocketError, why:
					if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
						data = ''
						self.shutdown()
					else:
						print >> sys.stderr, 'error: socket error, client down'
						try:
							self.shutdown()
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

			pollster.unregister(self.pid)
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
			self._rbuf = ''
			yield
			while True:
				try:
					data = self.socket.recv(8192)
				except SocketError, why:
					if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
						data = ''
						self.shutdown()
					else:
						print >> sys.stderr, 'error: socket error, client down'
						try:
							self.shutdown()
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

			pollster.unregister(self.pid)
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
			self._rbuf = ''
			yield
			while True:
				try:
					data = self.socket.recv(8192)
				except SocketError, why:
					if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
						data = ''
						self.shutdown()
					else:
						print >> sys.stderr, 'error: socket error, client down'
						try:
							self.shutdown()
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

			pollster.unregister(self.pid)
			self.read_channel.send(''.join(buffers))

	def write4raw(self):
		while self._wbuf:
			try:
				num_sent = self.socket.send(self._wbuf[:8192])

			except SocketError, why:
				if why[0] == EWOULDBLOCK:
					num_sent = 0
				else:
					print >> sys.stderr, 'error: socket error, client down'
					try:
						self.shutdown()
					except:
						pass

					self.write_channel = channel()
					self.tasklet.raise_exception(Disconnect)
					raise StopIteration

			if num_sent:
				self._wbuf = self._wbuf[num_sent:]

			yield

		pollster.unregister(self.pid)
		self.write_channel.send(None)

	def handle_error(self):
		print >> sys.stderr, 'error: fatal error, client down'
		self.shutdown()
		self.tasklet.raise_exception(Disconnect)

	def __del__(self):
		if socket_map.has_key(self.pid):
			self.shutdown()

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
					print_exc(file=sys.stderr)
			if flags & W:
				try:
					obj.handle_write()
				except StopIteration:
					pass
				except:
					print_exc(file=sys.stderr)
			if flags & E:
				try:
					obj.handle_error()
				except:
					print_exc(file=sys.stderr)

		schedule()

R = POLLIN | POLLPRI; W = POLLOUT
E = POLLERR | POLLHUP | POLLNVAL
RE = R | E; WE = W | E; RWE = R | W | E

socket_map = {}
pollster = Poll()
tasklet(poll)()
