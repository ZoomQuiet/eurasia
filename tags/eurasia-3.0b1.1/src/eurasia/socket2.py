import os, sys
import stackless
from time import time
from _weakref import proxy
from sys import stdout, stderr
from traceback import print_exc
from stackless import channel, getcurrent, schedule, tasklet
from errno import EWOULDBLOCK, ECONNRESET, ENOTCONN, ESHUTDOWN, EINTR
from _socket import socket as Socket, error as SocketError, timeout as SocketTimeout, \
	AF_INET, AF_INET6, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, IPPROTO_IPV6

import _socket
AF_UNIX, IPV6_V6ONLY = _socket.__dict__.get('AF_UNIX', -1), \
	_socket.__dict__.get('IPV6_V6ONLY', -1)

try:
	from _socket import fromfd
except ImportError:
	def fromfd(fileno, family, socktype):
		raise NotImplementedError('socket.fromfd not implemented')

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

	pollster = Poll()

except ImportError:
	from select import select, error as SelectError
	@staticmethod
	def poll(timeout):
		a, b, c = select(r.keys(), w.keys(), e.keys(), 0.0001)
		return [(i, R) for i in a] + [(i, W) for i in b] + [(i, E) for i in c]

	@staticmethod
	def register(fileno, flag):
		if flag & R:
			r[fileno] = None

		if flag & W:
			w[fileno] = None

		if flag & E:
			e[fileno] = None

	@staticmethod
	def unregister(fileno):
		if fileno in r:
			del r[fileno]

		if fileno in w:
			del w[fileno]

		if fileno in e:
			del e[fileno]

	pollster = type('poll', (), {'poll': poll, 'register': register,
	                'unregister': unregister})()

	r, w, e = {}, {}, {}
	POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL = 1, 2, 4, 8, 16, 32
	del poll, register, unregister

try:
	from OpenSSL.crypto import load_certificate, FILETYPE_PEM
	from OpenSSL.SSL import SSLv23_METHOD, Context as SSLContext, Connection as SSLConnection, \
		Error as SSLError, WantReadError, WantWriteError, ZeroReturnError, SysCallError
except ImportError:
	SSL = None
else:
	class SSL(object):
		def __init__(self, sock):
			self.ssl = sock

		def accept(self):
			conn, addr = self.ssl.accept()
			return SSL(conn), addr

		def recv(self, size):
			start = time()
			while True:
				try:
					return self.ssl.recv(size)

				except (WantReadError, WantWriteError):
					schedule()
					if time() - start > 3:
						raise SocketTimeout('time out')

					continue

				except SysCallError, e:
					if e.args == (-1, 'Unexpected EOF'):
						return ''

					raise SocketError(e.args[0])

				except SSLError, e:
					try:
						thirdarg = e.args[0][0][2]

					except IndexError:
						raise e
					else:
						if thirdarg == 'first num too large':
							schedule()
							if time() - start > 3:
								raise SocketTimeout('time out')

							continue
					raise

				except ZeroReturnError:
					return ''

		code = '\n'.join(line[2:] for line in '''\
		def %s(self, data):
			start = time()
			while True:
				try:
					return self.ssl.%s(data)

				except (WantWriteError, WantReadError):
					schedule()
					if time() - start > 3:
						raise SocketTimeout('time out')

					continue

				except SysCallError, e:
					raise SocketError(e.args[0])

				except SSLError, e:
					try:
						thirdarg = e.args[0][0][2]

					except IndexError:
						raise e
					else:
						if thirdarg == 'first num too large':
							return 0
					raise'''.split('\n'))

		for func in ('send', 'sendall'):
			exec code %(func, func)

		for func in ('bind,close,connect,connect_ex,fileno,get_app_data,get_cipher_list,get_'
		             'context,get_peer_certificate,getpeername,getsockname,getsockopt,listen'
		             ',makefile,pending,read,renegotiate,set_accept_state,set_app_data,set_c'
		             'onnect_state,setblocking,setsockopt,settimeout,shutdown,sock_shutdown,'
		             'state_string,want_read,want_write,write').split(','):

			exec 'def %s(self, *args):\n\treturn self.ssl.%s(*args)' % (func, func)

		del code, func

class SocketFile:
	fileno = lambda self: self.pid

	def __init__(self, sock, addr):
		self.socket = sock
		self.address = addr
		self.pid = sock.fileno()
		self._rbuf = self._wbuf = ''
		self.read_channel = channel()
		self.write_channel = channel()
		self.writing = self.reading = None
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

		if self.reading:
			raise ReadConflictError

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

		if self.reading:
			raise ReadConflictError

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

		if self.writing:
			raise WriteConflictError

		self._wbuf = data
		self.writing = self.write_channel
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
			self.reading = self.read_channel
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

						self.reading = None
						self.read_channel.send_exception(Disconnect, Disconnect())
						self.read_channel = channel()
						raise StopIteration
				except:
					try: self.close()
					except: pass

					self.reading = None
					self.read_channel.send_exception(Disconnect, Disconnect())
					self.read_channel = channel()
					raise StopIteration

				if not data:
					self.close()
					break

				buffers.append(data)
				yield

			try: pollster.unregister(self.pid)
			except (KeyError, AttributeError): pass
			self.writing and pollster.register(self.pid, WE)

			self.reading = None
			self.read_channel.send(''.join(buffers))
		else:
			buf_len = len(data)
			if buf_len >= size:
				self._rbuf = data[size:]
				yield data[:size]
				raise StopIteration

			buffers = data and [data] or []
			self._rbuf   = ''
			self.reading = self.read_channel
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

						self.reading = None
						self.read_channel.send_exception(Disconnect, Disconnect())
						self.read_channel = channel()
						raise StopIteration
				except:
					try: self.close()
					except: pass

					self.reading = None
					self.read_channel.send_exception(Disconnect, Disconnect())
					self.read_channel = channel()
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
			self.writing and pollster.register(self.pid, WE)

			self.reading = None
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
			self.reading = self.read_channel
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

						self.reading = None
						self.read_channel.send_exception(Disconnect, Disconnect())
						self.read_channel = channel()
						raise StopIteration
				except:
					try: self.close()
					except: pass

					self.reading = None
					self.read_channel.send_exception(Disconnect, Disconnect())
					self.read_channel = channel()
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
			self.writing and pollster.register(self.pid, WE)

			self.reading = None
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
			self.reading = self.read_channel
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

						self.reading = None
						self.read_channel.send_exception(Disconnect, Disconnect())
						self.read_channel = channel()
						raise StopIteration
				except:
					try: self.close()
					except: pass

					self.reading = None
					self.read_channel.send_exception(Disconnect, Disconnect())
					self.read_channel = channel()
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
			self.writing and pollster.register(self.pid, WE)

			self.reading = None
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

					self.writing = None
					self.write_channel.send_exception(Disconnect, Disconnect())
					self.write_channel = channel()
					raise StopIteration
			except:
				try: self.close()
				except: pass

				self.writing = None
				self.write_channel.send_exception(Disconnect, Disconnect())
				self.write_channel = channel()
				raise StopIteration

			if num_sent:
				self._wbuf = self._wbuf[num_sent:]

			yield

		try: pollster.unregister(self.pid)
		except (KeyError, AttributeError): pass
		self.reading and pollster.register(self.pid, RE)

		self.writing = None
		self.write_channel.send(None)

	def handle_error(self):
		if not self.reading and self.writing:
			try: self.close()
			except: pass

			self.writing = None
			self.write_channel.send_exception(Disconnect, Disconnect())
			self.write_channel = channel()

def Sockets(addresses, **args):
	ssl_private_key = args.get('ssl_private_key', args.get('key_file' ))
	ssl_certificate = args.get('ssl_certificate', args.get('cert_file'))

	ssl = ssl_certificate and ssl_private_key
	if ssl:
		if not SSL:
			raise ImportError('you must install pyOpenSSL to use https')

		ctx = SSLContext(SSLv23_METHOD)
		ctx.use_privatekey_file(ssl_private_key)
		ctx.use_certificate_file(ssl_certificate)

		cert = load_certificate(FILETYPE_PEM, open(ssl_certificate, 'rb').read())
		base_environ = dict(HTTPS='on', SSL_SERVER_M_SERIAL  = cert.get_serial_number(),
		                                SSL_SERVER_M_VERSION = cert.get_version())

		for prefix, dn in [("I", cert.get_issuer()), ("S", cert.get_subject())]:
			dnstr = str(dn)[18:-2]
			wsgikey = 'SSL_SERVER_%s_DN' %prefix
			base_environ[wsgikey] = dnstr
			while dnstr:
				pos = dnstr.rfind('=')
				dnstr, value = dnstr[:pos], dnstr[pos + 1:]
				pos = dnstr.rfind('/')
				dnstr, key = dnstr[:pos], dnstr[pos + 1:]
				if key and value:
					wsgikey = 'SSL_SERVER_%s_DN_%s' % (prefix, key)
					base_environ[wsgikey] = value

		socket_func = lambda family, socktype: \
			SSL(SSLConnection(ctx, Socket(family, socktype)))
		fromfd_func = lambda fileno, family, socktype: \
			SSL(SSLConnection(ctx, fromfd(fileno, family, socktype)))
	else:
		fromfd_func, socket_func, base_environ = fromfd, Socket, {}

	if isinstance(addresses, basestring):
		addresses, addrs = [], [i for i in str(addresses).split(',') if i.strip()]
		for addr in addrs:
			is_ipv6 = R_IPV6(addr)
			if is_ipv6:
				addresses.append((AF_INET6, is_ipv6.groups()))
				continue

			seq = [i.strip() for i in addr.split(':')]
			if len(seq) == 2:
				if seq[0].lower() in ('fromfd', 'fileno'):
					addresses.append((AF_INET, int(seq[1])))
					continue

				addresses.append((AF_INET, seq))
				continue

			if len(seq) == 3 and seq[0].lower() in ('fromfd', 'fileno'):
				family = seq[1].lower()
				if   family in ('inet', 'af_inet', 'ipv4'):
					addresses.append((AF_INET, int(seq[2])))
					continue

				elif family in ('inet6', 'af_inet6', 'ipv6', '6'):
					addresses.append((AF_INET, int(seq[2])))
					continue

				elif family in ('unix', 'af_unix', 's', 'socket',
				           'unix_socket', 'unixsocket', 'unixsock'):

					addresses.append((_socket.AF_UNIX, int(seq[2])))
					continue

			addresses.append((_socket.AF_UNIX, addr.strip()))
	else:
		addresses, addrs = [], addresses
		for addr in addrs:
			if isinstance(addr, (int, long)):
				addresses.append((AF_INET, addr))
				continue

			if isinstance(addr, (list, tuple)) and len(addr) == 2:
				if isinstance(addr[0], (int, long)):
					address.append(addr)
					continue

				if isinstance(addr[0], basestring):
					addresses.append((AF_INET6, addr) if ':' in addr[0] \
					            else (AF_INET , addr))
					continue

			if isinstance(addr, basestring):
				addresses.append((_socket.AF_UNIX, addr))
				continue

			raise ValueError('bad address %r' %addr)

	sockets = []
	for family, addr in addresses:
		if isinstance(addr, (int, long)):
			sock = fromfd_func(addr, family, SOCK_STREAM)
			sock.setblocking(0)

			environ = dict(SERVER_NAME='fileno:%d' %addr, SERVER_PORT='')
			environ.update(base_environ)

			sockets.append((sock, environ))
			continue

		if family == AF_UNIX:
			sock = socket_func(_socket.AF_UNIX, SOCK_STREAM)
			sock.setblocking(0)
			try:
				sock.bind(addr)

			except SocketError, address_already_in_use:
				if address_already_in_use.args[0] != 98:
					raise

				ping = socket_func(_socket.AF_UNIX, SOCK_STREAM)
				try:
					ping.connect(addr)
				except SocketError, e:
					if e.args[0] == 111:
						os.unlink(addr)
						sock.bind(addr)
				else:
					ping.close()
					raise address_already_in_use

			sock.listen(4194304)

			environ = dict(SERVER_NAME='s:%s' %addr, SERVER_PORT='')
			environ.update(base_environ)

			sockets.append((sock, environ))
			continue

		sock = socket_func(family, SOCK_STREAM)
		sock.setblocking(0)
		try:
			sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, sock.getsockopt(
			                SOL_SOCKET, SO_REUSEADDR)|1)
		except SocketError:
			pass

		if family == AF_INET6 and addr[0] == '::':
			try:
				socket.setsockopt(IPPROTO_IPV6, _socket.IPV6_V6ONLY, 0)
			except SocketError:
				pass

		sock.bind((addr[0], int(addr[1])))
		sock.listen(4194304)

		environ = dict(SERVER_NAME=addr[0], SERVER_PORT=str(addr[1]))
		environ.update(base_environ)

		sockets.append((sock, environ))

	return sockets

def TcpHandler(controller):
	def handler(sock, addr):
		try:
			controller(SocketFile(sock, addr))
		except:
			print_exc(file=stderr)

	return handler

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
		except:
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

			handler = args[name]

	if not handler:
		raise TypeError('handler is required')

	if 'port' in args and 'bind' in args:
		raise TypeError('too many addresses')

	if 'port' in args:
		sockets = Sockets([('0.0.0.0', int(args['port']))])
	else:
		sockets = Sockets(args['bind'], **args)

	for sock, environ in sockets:
		TcpServer(sock, TcpHandler(handler))

def mainloop(cpus=False):
	if isinstance(cpus, bool):
		cpus = cpu_count() if cpus else 1

	if cpus < 2:
		return mainloop0()

	try:
		from os import fork, kill
		from signal import signal, SIGTERM
	except ImportError:
		return mainloop0()

	pids = []
	for i in xrange(cpus - 1):
		pid = fork()
		if pid == 0:
			mainloop0()
			sys.exit(0)
		else:
			pids.append(pid)

	def term(sig, frame):
		for pid in pids:
			try:
				kill(pid, SIGTERM)
			except OSError:
				pass

		sys.exit(0)

	signal(SIGTERM, term)
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
			try:
				obj = socket_map[fd]
			except KeyError:
				continue

			if flags & R:
				try:
					obj.handle_read()
				except (ReferenceError, StopIteration):
					pass
				except:
					print_exc(file=stderr)

			if flags & W:
				try:
					obj.handle_write()
				except (ReferenceError, StopIteration):
					pass
				except:
					print_exc(file=stderr)

			if flags & E:
				try:
					obj.handle_error()
				except (ReferenceError, StopIteration):
					pass
				except:
					print_exc(file=stderr)

		schedule()

def mainloop0():
	while True:
		try:
			stackless.run()
		except (SystemExit, KeyboardInterrupt):
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

ConflictError      = type('ConflictError', (IOError, ), {})
ReadConflictError  = type('ReadConflictError' , (ConflictError, ), {})
WriteConflictError = type('WriteConflictError', (ConflictError, ), {})

R, W, E = POLLIN|POLLPRI, POLLOUT, POLLERR|POLLHUP|POLLNVAL
RE, WE, RWE = R|E, W|E, R|W|E
R_IPV6 = __import__('re').compile(r'^\s*\[([a-fA-F0-9:\s]+)]\s*:\s*([0-9]+)\s*$').match
socket_map, Disconnect = {}, type('Disconnect', (IOError, ), {})

tasklet(poll)()
