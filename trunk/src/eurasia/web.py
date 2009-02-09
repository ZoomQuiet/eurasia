import stackless
import re, sys, copy
from _weakref import proxy
from string import Template
from cgi import parse_header
from sys import stdout, stderr
from urllib import unquote_plus
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
					else:
						print >> stderr, 'error: socket error, client down'
						try: self.close()
						except: pass

						self.read_channel = channel()
						self.tasklet.raise_exception(Disconnect)
						raise StopIteration

				if not data:
					break

				buffers.append(data)
				yield

			try: pollster.unregister(self.pid)
			except (KeyError, AttributeError): pass

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
						try: self.close()
						except: pass

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

			try: pollster.unregister(self.pid)
			except (KeyError, AttributeError): pass

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
						try: self.close()
						except: pass

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

			try: pollster.unregister(self.pid)
			except (KeyError, AttributeError): pass

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
						try: self.close()
						except: pass

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

			try: pollster.unregister(self.pid)
			except (KeyError, AttributeError): pass

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
		self.keep_alive = channel()
		self.write = self.content.append

	def __del__(self):
		if hasattr(self, 'keep_alive'):
			return self.keep_alive and self.keep_alive.send(0)

	def __setitem__(self, key, value):
		self.respader['-'.join(i.capitalize() for i in key.split('-'))] = value

	pid     = property(lambda self: self.sockfile.pid)
	address = property(lambda self: self.sockfile.address)

	fileno  = lambda self: self.sockfile.pid
	nocache = lambda self: self.respader.update(NOCACHEHEADERS)

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

	def setstatus(self, status):
		self._status  = status
		self._message = RESPONSES[status]

	getstatus = lambda self: self._status
	status, _status, _message = property(getstatus, setstatus), 200, RESPONSES[200]
	del getstatus, setstatus

	def read(self, size=-1):
		if size == -1 or size >= self.left:
			try:
				data = self.sockfile.read(self.left)
			except Disconnect:
				self.keep_alive = self.keep_alive and self.keep_alive.send(0)
				raise

			self.left = 0
			return data
		else:
			try:
				data = self.sockfile.read(size)
			except Disconnect:
				self.keep_alive = self.keep_alive and self.keep_alive.send(0)
				raise

			self.left -= len(data)
			return data

	def readline(self, size=-1):
		if size == -1 or size >= self.left:
			try:
				data = self.sockfile.readline(self.left)
			except Disconnect:
				self.keep_alive = self.keep_alive and self.keep_alive.send(0)
				raise
		else:
			try:
				data = self.sockfile.readline(size)
			except Disconnect:
				self.keep_alive = self.keep_alive and self.keep_alive.send(0)
				raise

		self.left -= len(data)
		return data

	def begin(self):
		self.keep_alive = self.keep_alive and self.keep_alive.send(0)
		data = ['%s: %s' %(key, value) for key, value in self.respader.items()]
		data.insert(0, '%s %s %s' %(self.version, self._status, self._message))
		data.append('\r\n')

		self.write = self.sockfile.write
		self.write('\r\n'.join(data))
		self.close = self.end = self.sockfile.close

	def wbegin(self, data=''):
		self.keep_alive = self.keep_alive and self.keep_alive.send(0)
		respader = ['%s: %s' %(key, value) for key, value in self.respader.items()]
		respader.insert(0, '%s %s %s' %(self.version, self._status, self._message))
		respader.append('\r\n')

		self.write = self.sockfile.write
		self.write('\r\n'.join(respader) + data)
		self.close = self.end = self.sockfile.close

	def close(self):
		if not self.keep_alive:
			raise Disconnect

		data = ''.join(self.content)
		self.respader['Content-Length'] = str(len(data))
		respader = ['%s: %s' %(key, value) for key, value in self.respader.items()]
		respader.insert(0, '%s %s %s' %(self.version, self._status, self._message))
		respader.append('\r\n')

		data = '\r\n'.join(respader) + data
		try:
			self.sockfile.write(data)
		except Disconnect:
			self.keep_alive = self.keep_alive and self.keep_alive.send(0)
			raise

		self.keep_alive = self.keep_alive.send(1) if self.get('Connection', '').lower() == 'keep-alive' \
			else self.sockfile.close() or self.keep_alive.send(0)

	def wshutdown(self, data=''):
		try:
			self.sockfile.write(data)
		except Disconnect:
			self.keep_alive = self.keep_alive and self.keep_alive.send(0)
			raise

		self.sockfile.close()
		self.keep_alive = self.keep_alive and self.keep_alive.send(0)

	def shutdown(self):
		self.sockfile.close()
		self.keep_alive = self.keep_alive and self.keep_alive.send(0)

class Comet(object):
	def __init__(self, httpfile):
		self.httpfile = httpfile
		httpfile.respader.update(COMETHEADERS)

	def __getattr__(self, name):
		return RemoteCall(self.httpfile, name)

	def __getitem__(self, key):
		return self.httpfile[key]

	def __setitem__(self, key, value):
		self.httpfile.respader['-'.join(i.capitalize() for i in key.split('-'))] = value

	pid     = property(lambda self: self.httpfile.pid)
	address = property(lambda self: self.httpfile.address)
	uid     = property(lambda self: self.httpfile.uid, \
		lambda self, uid: setattr(self.httpfile, 'uid', uid))

	def fileno(self):
		return self.httpfile.sockfile.pid

	def begin(self):
		self.httpfile.wbegin(COMET_BEGIN)

	def end(self):
		self.httpfile.wshutdown(COMET_END)

	def close(self):
		self.httpfile.wshutdown(COMET_END)

	def shutdown(self):
		self.httpfile.shutdown()

class RemoteCall(object):
	def __init__(self, httpfile, name):
		self._name    = name
		self.httpfile = httpfile

	def __call__(self, *args):
		self.httpfile._write(T_REMOTECALL(function = self._name,
			arguments = args and ', '.join([json(arg) for arg in args]) or ''))

	def __getattr__(self, name):
		return RemoteCall(self.httpfile, '%s.%s' %(self._name, name))

	def __getitem__(self, name):
		if isinstance(unicode):
			return RemoteCall(self.httpfile, '%s[%s]' %(self._name, repr(name)[1:]))

		return RemoteCall(self.httpfile, '%s[%s]' %(self._name, repr(name)))

def Form(httpfile, max_size=1048576):
	if httpfile.method == 'POST':
		length = httpfile['Content-Length']
		if int(length) > max_size:
			httpfile.close()
			raise IOError('overload')

		data = httpfile.read(length)
	else:
		data = ''

	p = httpfile.path.find('?')
	if p != -1:
		data = '%s&%s' %(httpfile.path[p+1:], data)

	d = {}
	for item in data.split('&'):
		try:
			key, value = item.split('=', 1)
			value = unquote_plus(value)
			try:
				if isinstance(d[key], list):
					d[key].append(value)
				else:
					d[key] = [d[key], value]
			except KeyError:
				d[key] = value
		except ValueError:
			continue
	return d

class SimpleUpload(dict):
	def __init__(self, httpfile):
		try: next = '--' + parse_header(httpfile['Content-Type'])[1]['boundary']
		except: raise IOError

		last, c = next + '--', 0
		while True:
			line = httpfile.readline(65536)
			c += len(line)
			if not line:
				raise IOError

			if line[:2] == '--':
				strpln = line.strip()
				if strpln == next:
					c1 = (line[-2:] == '\r\n' and 2 or 1) << 1
					c_next = c1 + len(next)
					break

				if strpln == last:
					raise IOError
		filename = None
		while True:
			name = None
			for i in xrange(32):
				line = httpfile.readline(65536)
				c += len(line)
				line = line.strip()
				if not line:
					if not name: raise IOError
					if filename:
						self.buff      = ''
						self.httpfile  = httpfile
						self.filename  = filename
						self._readline = self._readline(next, last).next
						try: size = int(httpfile['Content-Length'])
						except:
							return

						self.size = size - c - c1 - len(last)
						return

					data = self.read()
					c += c_next + len(data)
					try: self[name].append(data)
					except KeyError: self[name] = data
					except AttributeError: self[name] = [self[name], data]
					break

				t1, t2 = line.split(':', 1)
				if t1.lower() != 'content-disposition': continue
	 			t1, t2 = parse_header(t2)
				if t1.lower() != 'form-data': raise IOError
				try: name = t2['name']
				except KeyError: raise IOError
				try: filename = t2['filename']
				except KeyError: continue
				m = R_UPLOAD(filename)
				if not m: raise IOError
				filename = m.groups()[0]

	def _readline(self, next, last):
		httpfile = self.httpfile
		line = httpfile.readline(65536)
		if not line:
			raise IOError

		if line[:2] == '--':
			strpln = line.strip()
			if strpln == next or strpln == last:
				raise IOError

		el = line[-2:] == '\r\n' and '\r\n' or (line[-1] == '\n' and '\n' or '')
		while True:
			line2 = httpfile.readline(65536)
			if not line2: raise IOError
			if line2[:2] == '--' and el:
				strpln = line2.strip()
				if strpln == next or strpln == last:
					yield line[:-len(el)]
					break
			yield line
			line = line2
			el = line[-2:] == '\r\n' and '\r\n' or (line[-1] == '\n' and '\n' or '')

		while True:
			yield None

	def read(size=None):
		buff = self.buff
		if size:
			while len(buff) < size:
				line = self._readline()
				if not line:
					self.buff = ''
					return buff

				buff += line

			self.buff = buff[size:]
			return buff[:size]

		d, self.buff = [buff], ''
		while True:
			line = self._readline()
			if not line:
				return ''.join(d)

			d.append(line)

	def readline(size=None):
		buff = self.buff
		if size:
			nl = buff.find('\n', 0, size)
			if nl >= 0:
				nl += 1
				self.buff = buff[nl:]
				return buff[:nl]

			elif len(buff) > size:
				self.buff = buff[size:]
				return buff[:size]

			t = self._readline()
			if not t:
				self.buff = ''
				return buff

			buff = buff + t
			if len(buff) > size:
				self.buff = buff[size:]
				return buff[:size]

			self.buff = ''
			return buff

		nl = buff.find('\n')
		if nl >= 0:
			nl += 1
			self.buff = buff[nl:]
			return buff[:nl]

		t = self._readline()
		self.buff = ''
		return buff + t if t else buff

def HttpHandler(controller):
	def handler(sock, addr):
		sockfile = SocketFile(sock, addr)
		try:
			httpfile = HttpFile(sockfile)
		except IOError:
			return

		tasklet(controller)(httpfile)

		while httpfile.keep_alive.receive():
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

def json(obj):
	if isinstance(obj, str): return repr(obj)
	elif isinstance(obj, unicode): return repr(obj)[1:]
	elif obj is None: return 'null'
	elif obj is True: return 'true'
	elif obj is False: return 'false'
	elif isinstance(obj, (int, long)): return str(obj)
	elif isinstance(obj, float): return _json_float(obj)
	elif isinstance(obj, (list, tuple)): return '[%s]' %', '.join(_json_array(obj))
	elif isinstance(obj, dict): return '{%s}' %', '.join(_json_object(obj))
	elif isinstance(obj, RemoteCall): return '__comet__.' + obj.function
	raise ValueError
def _json_array(l):
	for item in l: yield json(item)
def _json_object(d):
	for key in d: yield '"%s":%s' %(key, json(d[key]))
def _json_float(o):
	s = str(o)
	if (o < 0.0 and s[1].isdigit()) or s[0].isdigit(): return s
	if s == 'nan': return 'NaN'
	if s == 'inf': return 'Infinity'
	if s == '-inf': return '-Infinity'
	if o != o or o == 0.0: return 'NaN'
	if o < 0: return '-Infinity'
	return 'Infinity'

R, W, E = POLLIN|POLLPRI, POLLOUT, POLLERR|POLLHUP|POLLNVAL
RE, WE, RWE = R|E, W|E, R|W|E

socket_map, pollster, Disconnect = {}, Poll(), type('Disconnect', (IOError, ), {})
tasklet(poll)()

T_REMOTECALL = Template(
	'<script language="JavaScript">\r\n<!--\r\n'
	'__comet__.${function}(${arguments});\r\n'
	'//-->\r\n</script>\r\n' ).safe_substitute

COMET_BEGIN = (
	'<html>\r\n<head>\r\n'
	'<meta http-equiv="Pragma" content="no-cache">\r\n'
	'<meta http-equiv="Content-Type" content="text/html">\r\n'
	'<body>\r\n'
	'<script language="JavaScript">\r\n<!--\r\n'
	'if(!window.__comet__) window.__comet__ = window.parent?'
	'(window.parent.__comet__?parent.__comet__:parent):window;\r\n'
	'if(document.all) __comet__.escape("FUCK IE");\r\n'
	'//-->\r\n</script>\r\n<!--COMET BEGIN-->\r\n')
COMET_END = '<!--COMET END-->\r\n</body>\r\n</html>'

NOCACHEHEADERS = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
	'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT' }
COMETHEADERS   = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
	'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT', 'Content-Type': 'text/html; charset=UTF-8' }

R_UPLOAD = re.compile(r'([^\\/]+)$').search
R_UID    = re.compile(r'(?:[^;]+;)* *uid=([^;\r\n]+)').search
R_FIRST  = re.compile(r'^(GET|POST)[\s\t]+([^\r\n]+)[\s\t]+(HTTP/1\.[0-9])\r?\n$', re.I).match
R_HEADER = re.compile(r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*\r?\n$', re.I).match
