import stackless
import os, re, sys
import sha, sqlite3
from cgi import parse_header
from random import random
from sys import stderr, stdout
from stackless import tasklet, schedule, channel
from time import gmtime, strftime, time
from traceback import print_exc
from urllib import unquote_plus
from mimetools import Message
from string import Template
from sqlite3 import IntegrityError
from cStringIO import StringIO
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
     ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode
from socket import socket as Socket, error as SocketError, AF_INET, SOCK_STREAM, \
	SOL_SOCKET, SO_REUSEADDR, SO_REUSEADDR
from select import poll as Poll, error as SelectError, \
	POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL

class UidError(Exception ): pass
class OverLimit(IOError  ): pass
class Disconnect(IOError ): pass
class MethodError(IOError): pass

class UidGenerator:
	def __init__(self):
		cursor = sqlite3.connect(':memory:').cursor()
		cursor.execute( (
			'CREATE TABLE IF NOT EXISTS session '
			'(id TEXT PRIMARY KEY, timeout INTEGER NOT NULL)' ) )
		cursor.execute('CREATE INDEX idx_timeout on session(timeout)')

		self.items = {}
		self.has_key = self.items.has_key
		self.cursor = cursor
		self.timeout = 1800
		self.garbage_timeout = 900
		self.next_garbage_clean = int(time()) + self.garbage_timeout

	def __setitem__(self, uid, item):
		try:
			self.cursor.execute(
				'INSERT INTO session VALUES (?, ?)',
				(uid, int(time()) + self.timeout) )

		except IntegrityError:
			try:
				self.cursor.execute(
					'SELECT id FROM session WHERE id=? AND timeout>?',
					(uid, now) ).fetchone()[0]
				self.cursor.execute(
					'UPDATE session SET timeout=? WHERE id=?',
					(now + self.timeout, uid) )
			except TypeError:
				raise UidError

		self.items[uid] = item

	def __getitem__(self, uid):
		now = int(time())
		if self.next_garbage_clean < now:
			self.garbage_clean()
		try:
			self.cursor.execute(
				'SELECT id FROM session WHERE id=? AND timeout>?',
				(uid, now) ).fetchone()[0]
			self.cursor.execute(
				'UPDATE session SET timeout=? WHERE id=?',
				(now + self.timeout, uid) )
		except TypeError:
			raise UidError

		return self.items[uid]

	def __delitem__(self, uid):
		try:
			self.items[uid].exit()
		except AttributeError:
			pass
		except TypeError:
			pass
		del self.items[uid]

		self.cursor.execute('DELETE FROM session WHERE id=', (uid, ))

	def __call__(self):
		timeout = int(time()) + self.timeout
		while True:
			try:
				uid = sha.new('%s' % random()).hexdigest()
				self.cursor.execute(
					'INSERT INTO session VALUES (?, ?)',
					(uid, timeout) )
				return uid

			except IntegrityError:
				continue

	def __lshift__(self, item):
		uid = self()
		self.items[uid] = item
		return uid

	def garbage_clean(self):
		now = int(time())
		for uid in [i[0] for i in self.cursor.execute(
			'SELECT id FROM session WHERE timeout<?',
			(now, ) ).fetchall() ]:

			try:
				self.items[uid].exit()
			except AttributeError:
				pass
			except TypeError:
				pass
			del self.items[uid]

		self.cursor.execute('DELETE FROM session WHERE timeout<?', (now, ))
		self.next_garbage_clean = now + self.garbage_timeout

class Request:
	uid = property(lambda self: self.req.uid)

	def __init__(self, req, max_size=1048576):
		self.req = req
		self.pid = req.pid
		self.__getitem__ = req.headers.getheader

		if req.method == 'get':
			return

		try:
			length = int(req['content-length'])
			if length > max_size:
				req.shutdown()
				raise OverLimit
		except:
			length = max_size

		if length == 0:
			self.content_length = 0
			return

		self.content_length = length

	def read(self, size=None):
		req = self.req
		pid = req.pid

		if not socket_map.has_key(pid):
			raise Disconnect

		try:
			left = self.left
		except AttributeError:
			try:
				self.left = left = self.content_length
			except AttributeError:
				raise MethodError

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
			try:
				self.left = left = self.content_length
			except AttributeError:
				raise MethodError

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

class Form(dict):
	uid = property(lambda self: self.req.uid)

	def __init__(req, max_size=1048576):
		self.req = fi = Request(req, max_size)
		self.pid = req.pid

		p = req.path.find('?')
		if p == -1:
			content = ''
		else:
			content = req.path[p+1:]

		if req.method == 'post':
			if content:
				content = '%s&%s' %(fi.read(), content)
			else:
				content = fi.read()

		d = {}
		for ll in content.split('&'):
			try:
				k, v = ll.split('=', 1); v = unquote_plus(v)
				try:
					if isinstance(d[k], list):
						d[k].append(v)
					else:
						d[k] = [d[k], v]
				except KeyError:
					d[k] = v
			except ValueError:
				continue

def SimpleUpload(req, max_size=1048576):
	fi = Request(req, max_size)

	global next, last
	try:
		next = '--' + parse_header(req['content-type'])[1]['boundary']
	except:
		raise IOError

	last = next + '--'

	def _preadline():
		l = fi.readline(65536)
		if not l: raise IOError
		if l[:2] == '--':
			sl = l.strip()
			if sl == next or sl == last:
				raise IOError

		el = l[-2:] == '\r\n' and '\r\n' or (
			l[-1] == '\n' and '\n' or '')

		while True:
			l2 = fi.readline(65536)
			if not l2: raise IOError
			if l2[:2] == '--' and el:
				sl = l2.strip()
				if sl == next or sl == last:
					yield l[:-len(el)]
					break
			yield l

			l = l2
			el = l[-2:] == '\r\n' and '\r\n' or (
				l[-1] == '\n' and '\n' or '')

		while True:
			yield None

	class CGIFile:
		def __getitem__(self, k):
			return self.form[k]

	def _fp():
		rl = _preadline().next
		_fp.buff = ''

		def _read(size=None):
			buff = _fp.buff
			if size:
				while len(buff) < size:
					l = rl()
					if not l:
						_fp.buff = ''
						return buff
					buff += l
				_fp.buff = buff[size:]
				return buff[:size]

			d = [buff]; _fp.buff = ''
			while True:
				l = rl()
				if not l:
					return ''.join(d)

				d.append(l)

		def _readline(size=None):
			s = _fp.buff
			if size:
				nl = s.find('\n', 0, size)
				if nl >= 0:
					nl += 1
					_fp.buff = s[nl:]
					return s[:nl]
				elif len(s) > size:
					_fp.buff = s[size:]
					return s[:size]

				t = rl()
				if not t:
					_fp.buff = ''
					return s

				s = s + t
				if len(s) > size:
					_fp.buff = s[size:]
					return s[:size]

				_fp.buff = ''
				return s
			else:
				nl = s.find('\n')
				if nl >= 0:
					nl += 1
					_fp.buff = s[nl:]
					return s[:nl]
				else:
					t = rl()
					_fp.buff = ''
					if not t:
						return s

					s += t
					return s

		fp = CGIFile()
		fp.read = _read; fp.readline = _readline

		return fp

	c = 0
	while True:
		l = fi.readline(65536)
		c += len(l)

		if not l:
			raise IOError

		if l[:2] == '--':
			sl = l.strip()
			if sl == next:
				c1 = (l[-2:] == '\r\n' and 2 or 1) << 1
				cnext = c1 + len(next)
				break
			if sl == last:
				raise IOError

	filename = None; d = {}
	while True:
		name = None
		for i in xrange(10):
			l = fi.readline(65536)
			c += len(l); l = l.strip()
			if not l:
				if not name:
					raise IOError

				if filename:
					fp = _fp()
					fp.filename = filename
					fp.form = d

					try:
						size = int(req['content-length'])
					except:
						return fp
					fp.size = size - c - c1 - len(last)
					return fp

				s = _fp().read()
				c += cnext + len(s)
				try:
					d[name].append(s)
				except KeyError:
					d[name] = s
				except AttributeError:
					d[name] = [d[name], s]

				break

			t1, t2 = l.split(':', 1)
			if t1.lower() != 'content-disposition':
				continue

 			t1, t2 = parse_header(t2)
			if t1.lower() != 'form-data':
				raise IOError

			try:
				name = t2['name']
			except KeyError:
				raise IOError

			try:
				filename = t2['filename']
			except KeyError:
				continue

			m = R_UPLOAD(filename)
			if not m:
				raise IOError

			filename = m.groups()[0]

class Response(dict):
	def __init__(self, req):
		dict.__init__(self)
		self.req = req
		self.pid = req.pid
		self.uid = None
		self.content = ''

	def write(self, data):
		self.content += data

	def begin(self):
		if self.req.disconnected:
			raise Disconnect

		ll = ['%s: %s' %(k, self[k]) for k in self]
		if self.uid:
			ll.append( T_UID(uid=self.uid, expires=strftime(
				'%a, %d-%b-%Y %H:%M:%S GMT', gmtime(time() + 157679616) )
				) )
		self.req.wfile = T_RESPONSE(header=ll and '\r\n'.join(ll) + '\r\n' or '')

		pollster.register(self.pid, WE)

		self.write = self.req.write
		self.end   = self._end
		delattr(self, 'content')

	def _end(self):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		self.req.closed = True
		pollster.register(self.pid, WE)
		schedule()

	def close(self):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		ll = ['%s: %s' %(k, self[k]) for k in self]
		if self.uid:
			ll.append( T_UID(uid=self.uid, expires=strftime(
				'%a, %d-%b-%Y %H:%M:%S GMT', gmtime(time() + 157679616) )
				) )
		ll.append(T_CONTENT_LENGTH(content_length=len(self.content)))
		self.req.wfile = T_RESPONSE(header=ll and '\r\n'.join(ll) + '\r\n' or ''
			) + self.content

		self.req.closed   = True
		pollster.register(self.pid, WE)
		schedule()

class Pushlet(dict):
	def __init__(self, req):
		dict.__init__(self)
		self.req = req
		self.pid = req.pid
		self.uid = None

	def __getattr__(self, name):
		return RemoteCall(self.req, name)

	def begin(self):
		if self.req.disconnected:
			raise Disconnect

		ll = ['%s: %s' %(k, self[k]) for k in self]
		if self.uid:
			ll.append( T_UID(uid=self.uid, expires=strftime(
				'%a, %d-%b-%Y %H:%M:%S GMT', gmtime(time() + 157679616) )
				) )
		self.req.wfile = T_PUSHLET_BEGIN(header=ll and '\r\n'.join(ll) + '\r\n' or '')

		pollster.register(self.pid, WE)

	def end(self):
		if self.req.disconnected:
			raise Disconnect

		self.req.wfile += PUSHLET_END
		pollster.register(self.pid, WE)
		self.req.closed   = True

class RemoteCall:
	def __init__(self, req, function):
		self.req = req
		self.pid = req.pid
		self.function = function

	def __call__(self, *args):
		if self.req.disconnected:
			raise Disconnect

		self.req.wfile += T_REMOTECALL(
			function  = self.function,
			arguments = args and ', '.join([json(arg) for arg in args]) or '' )

		pollster.register(self.pid, WE)

	def __getattr__(self, name):
		return RemoteCall(self.req, '%s.%s' %(self.function, name))

	def __getitem__(self, name):
		if isinstance(unicode):
			return RemoteCall(self.req, '%s[%s]' %(self.function, repr(name)[1:]))

		return RemoteCall(self.req, '%s[%s]' %(self.function, repr(name)))

class Client:
	disconnected = property(lambda self: not socket_map.has_key(self.pid))

	def __init__(self, sock, addr):
		self.socket  = sock
		self.address = addr
		self.pid = sock.fileno()

		socket_map[self.pid] = self
		pollster.register(self.pid, RE)

		self.closed = False
		self.rbuff = self.rfile = self.wfile = ''

		self.handle_read = self._handle_read_header

	@property
	def uid(self):
		try: return R_UID(self.headers['cookie']).groups()[0]
		except: return None

	def write(self, s):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		self.wfile += s
		pollster.register(self.pid, WE)
		schedule()

	def mk_header(self):
		rfile = StringIO(self.rfile)
		requestline = rfile.readline()[:-2]
		if not requestline:
			self.shutdown()
			return

		words = requestline.split()
		if len(words) == 3:
			[method, self.path, self.version] = words
			if self.version[:5] != 'HTTP/':
				self.shutdown()
				return

		elif len(words) == 2:
			[method, self.path] = words

		else:
			self.shutdown()
			return

		self.method = method.lower()

		self.headers, self.rfile = Message(rfile, 0), ''
		self.__getitem__ = self.headers.getheader

		try:
			tasklet(controller)(self)
		except:
			print_exc(file=stderr)

	def _handle_read_header(self):
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

				self.handle_read = self._handle_read_content
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

	def _handle_read_content(self):
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

		self.rfile, self.rbuff = self.rfile + self.rbuff, ''
		if len(self.rfile) > 30720:
			try:
				pollster.unregister(self.pid)
			except KeyError:
				pass
		return

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

			if not self.wfile:
				if self.closed:
					self.shutdown()
				else:
					try:
						pollster.unregister(self.pid)
					except KeyError:
						pass
			return

		if self.closed:
			self.shutdown()
		else:
			try:
				pollster.unregister(self.pid)
			except KeyError:
				pass

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

class Server:
	def __init__(self):
		global server_socket, serverpid
		server_socket = Socket(AF_INET, SOCK_STREAM)
		server_socket.setblocking(0)
		try:
			server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR,
				server_socket.getsockopt(SOL_SOCKET, SO_REUSEADDR) | 1)
		except error:
			pass

		serverpid = server_socket.fileno()
		pollster.register(serverpid, RE)

	@staticmethod
	def handle_read():
		try:
			conn, addr = server_socket.accept()
			try:
				Client(conn, addr)
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

	global controller
	controller = args['controller']
	server_socket.bind( args.get('address', (
		args.get('host', '0.0.0.0'),
		args.get('port', 8080     )  ) ) )

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
	elif isinstance(obj, RemoteCall): return 'parent.' + obj.function
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

def sleep(sec):
	c = channel()
	while True:
		uid = sha.new('%s' % random()).hexdigest()

		try:
			hypnus_cursor.execute(
				'INSERT INTO hypnus VALUES (?, ?)',
				(uid, time() + sec) )
			break
		except IntegrityError:
			continue

	hypnus_channels[uid] = c
	c.receive()

def hypnus_tasklets():
	while True:
		now = time()
		l = hypnus_cursor.execute(
			'SELECT id FROM hypnus WHERE timeout<?',
			(now, ) ).fetchall()
		for i in l:
			uid = i[0]
			c = hypnus_channels[uid]
			del hypnus_channels[uid]

			c.send(None)
		if l:
			hypnus_cursor.execute(
				'DELETE FROM hypnus WHERE timeout<?',
				(now, ))
		schedule()

R = POLLIN | POLLPRI; W = POLLOUT
E = POLLERR | POLLHUP | POLLNVAL
RE = R | E; WE = W | E

R_UPLOAD = re.compile(r'([^\\/]+)$').search
R_UID = re.compile('(?:[^;]+;)* *uid=([^;\r\n]+)').search
T_UID = Template('Set-Cookie: uid=${uid}; path=/; expires=${expires}').safe_substitute
T_CONTENT_LENGTH = Template('Content-Length: ${content_length}').safe_substitute
T_RESPONSE = Template(
	'HTTP/1.1 200 OK\r\n'
	'Cache-Control:no-cache, must-revalidate\r\n'
	'Pragma: no-cache\r\n'
	'Expires: Mon, 26 Jul 1997 05:00:00 GMT\r\n'
	'${header}\r\n'
	).safe_substitute
T_PUSHLET_BEGIN = Template(
	'HTTP/1.1 200 OK\r\n'
	'Content-Type: text/html\r\n'
	'Cache-Control: no-cache, must-revalidate\r\n'
	'Pragma: no-cache\r\n'
	'Expires: Mon, 26 Jul 1997 05:00:00 GMT\r\n'
	'${header}\r\n'
	'<html>\r\n<head>\r\n'
	'<META http-equiv="Content-Type" content="text/html">\r\n'
	'<meta http-equiv="Pragma" content="no-cache">\r\n'
	'<body>\r\n'
	'<script language="JavaScript">\r\n'
	'if(document.all) parent.escape("FUCK IE");\r\n'
	'</script>\r\n' ).safe_substitute
PUSHLET_END = '</body>\r\n</html>'
T_REMOTECALL = Template(
	'<script language="JavaScript">\r\n'
	'parent.${function}(${arguments});\r\n'
	'</script>\r\n' ).safe_substitute

pollster = Poll(); tasklet(poll)()
controller = server_socket = serverpid = None
socket_map = {serverpid: Server()}

hypnus_cursor = sqlite3.connect(':memory:').cursor()
hypnus_cursor.execute( (
	'CREATE TABLE IF NOT EXISTS hypnus '
	'(id TEXT PRIMARY KEY, timeout FLOAT NOT NULL)' ) )
hypnus_cursor.execute('CREATE INDEX idx_timeout on hypnus(timeout)')
hypnus_channels = {}
tasklet(hypnus_tasklets)()
