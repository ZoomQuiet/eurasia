import stackless
import os, re, sys
from string import Template
from cgi import parse_header
from mimetools import Message
from sys import stderr, stdout
from cStringIO import StringIO
from urllib import unquote_plus
from traceback import print_exc
from struct import pack, unpack, calcsize
from time import gmtime, strftime, time, sleep
from stackless import tasklet, schedule, channel
from select import poll as Poll, error as SelectError, \
	POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
	ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode
from socket import fromfd, socket as Socket, error as SocketError, \
	AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_REUSEADDR

class OverLimit(IOError): pass
class Disconnect(IOError): pass

def Form(client, max_size=1048576):
	content = client.query_string
	if client.method == 'post':
		content = content and '%s&%s' %(client.read(max_size), content
			) or client.read(max_size)

	if client.rfile:
		raise OverLimit
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
	return d

def SimpleUpload(client):
	global next, last
	try:
		next = '--' + parse_header(client.headers['content-type'])[1]['boundary']
	except:
		raise IOError

	last = next + '--'
	def _preadline():
		l = client.readline(65536)
		if not l: raise IOError
		if l[:2] == '--':
			sl = l.strip()
			if sl == next or sl == last:
				raise IOError

		el = l[-2:] == '\r\n' and '\r\n' or (
			l[-1] == '\n' and '\n' or '')

		while True:
			l2 = client.readline(65536)
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
				if not l: return ''.join(d)
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
					if not t: return s
					s += t
					return s
		fp = CGIFile()
		fp.read = _read; fp.readline = _readline
		return fp
	c = 0
	while True:
		l = client.readline(65536)
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
			l = client.readline(65536)
			c += len(l); l = l.strip()
			if not l:
				if not name: raise IOError
				if filename:
					fp = _fp()
					fp.filename = filename
					fp.form = d
					try: size = int(req['content-length'])
					except: return fp
					fp.size = size - c - c1 - len(last)
					return fp

				s = _fp().read()
				c += cnext + len(s)
				try: d[name].append(s)
				except KeyError: d[name] = s
				except AttributeError: d[name] = [d[name], s]
				break

			t1, t2 = l.split(':', 1)
			if t1.lower() != 'content-disposition':
				continue
 			t1, t2 = parse_header(t2)
			if t1.lower() != 'form-data':
				raise IOError
			try: name = t2['name']
			except KeyError: raise IOError
			try: filename = t2['filename']
			except KeyError: continue

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

class Client(dict):
	disconnected = property(lambda self: not socket_map.has_key(self.pid))

	def __init__(self, sock, addr):
		self.socket  = sock
		self.address = addr
		self.pid = sock.fileno()

		self.closed = self.eof = False
		self.rbuff = self.rfile = self.wfile = self.wbuff= ''
		self.message_length = None
		self.env = {}; self.headers = {}

		socket_map[self.pid] = self
		pollster.register(self.pid, RE)

	@property
	def uid(self):
		try: return R_UID(self.headers['cookie']).groups()[0]
		except: return None

	def read(self, size=None):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		if size is None:
			buff = []
			data = self.rfile; self.rfile = ''
			if data: buff.append(data)
			while not self.eof:
				if not socket_map.has_key(self.pid):
					raise Disconnect
				pollster.register(self.pid, RE)
				schedule()
				data = self.rfile; self.rfile = ''
				if data: buff.append(data)

			return ''.join(buff)

		data = self.rfile; bufl = len(data)
		if bufl >= size:
			self.rfile = data[size:]
			return data[:size]

		buff = []
		while bufl < size:
			self.rfile = ''; buff.append(data)
			if self.eof: break
			if not socket_map.has_key(self.pid):
				raise Disconnect
			pollster.register(self.pid, RE)
			schedule()
			data = self.rfile; bufl += len(data)

		n = size - bufl
		if n == 0:
			buff.append(data)
			self.rfile = ''
		else:
			buff.append(data[:n])
			self.rfile = data[n:]

		return ''.join(buff)

	def readline(self, size=None):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		if size is None:
			nl = self.rfile.find('\n')
			if nl >= 0:
				nl += 1; self.rfile = self.rfile[nl:]
				return self.rfile[:nl]

			buff = [self.rfile]; self.rfile = ''
			while not self.eof:
				if not socket_map.has_key(self.pid):
					raise Disconnect
				pollster.register(self.pid, RE)
				schedule()

				data = self.rfile
				nl = data.find('\n')
				if nl >= 0:
					nl += 1; self.rfile = data[nl:]
					buff.append(data[:nl])
					return ''.join(buff)

				self.rfile = ''; buff.append(data)
			return ''.join(buff)

		data = self.rfile; bufl = len(data)
		nl = data.find('\n', 0, size)
		if nl >= 0:
			nl += 1; self.rfile = data[nl:]
			return data[:nl]
		if bufl >= size:
			self.rfile = data[size:]
			return data[:size]

		buff = []
		while bufl < size:
			self.rfile = ''; buff.append(data)
			if self.eof: break
			if not socket_map.has_key(self.pid):
				raise Disconnect
			pollster.register(self.pid, RE)
			schedule()

			data = self.rfile
			p = size - bufl; bufl += len(data)
			nl = data.find('\n', 0, p)
			if nl >= 0:
				nl += 1; self.rfile = data[nl:]
				buff.append(data[:nl])
				return ''.join(buff)

		n = size - bufl
		if n == 0:
			buff.append(data)
			self.rfile = ''
		else:
			buff.append(data[:n])
			self.rfile = data[n:]

		return ''.join(buff)

	def handle_read(self):
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
		while self.process_input():
			pass

	def handle_write(self):
		if len(self.wbuff) < 8192 and self.wfile:
			self.filwbuff()

		if self.wbuff:
			try:
				num_sent = self.socket.send(self.wbuff[:8192])

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
				self.wbuff = self.wbuff[num_sent:]

			if not self.wbuff:
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

	def process_input(self):
		if not self.message_length:
			if len(self.rbuff) < 8:
				pollster.register(self.pid, RE)
				return False

			self.version, self.msgtype, self.request_id, \
			record_length, padding_length = unpack(
				'!BBHHBx', self.rbuff[:8])

			self.message_length = 8 + record_length + padding_length

		if len(self.rbuff) < self.message_length:
			pollster.register(self.pid, RE)
			return False

		record = self.rbuff[8:8+record_length]
		self.rbuff = self.rbuff[self.message_length:]
		self.message_length = None

		if self.msgtype == 5:
			if record:
				self.rfile += record
				if len(self.rfile) > 30720:
					try:
						pollster.unregister(self.pid)
					except KeyError:
						pass
			else:
				self.eof = True

		elif self.msgtype == 4:
			pos = 0
			if record_length:
				while pos < record_length:
					pos, (name, value) = decode_pair(record, pos)
					name = name.lower()
					if name[:5] == 'http_':
						self.headers[name[5:].replace('_', '-')] = value
					else:
						self.env[name] = value
			else:
				self.address = (self.env['remote_addr'], int(self.env['remote_port']))
				self.method = self.env['request_method'].lower()
				self.query_string = qs = self.env['query_string']
				self.path = qs and '%s?%s' %(self.env['request_uri'], qs
					) or self.env['request_uri']

				try:
					tasklet(controller)(self)
				except:
					print_exc(file=stderr)

		elif self.msgtype == 8:
			self.shutdown()
			raise NotImplemented('fastcgi data record')

		elif self.msgtype == 9:
			pos = 0; s = ''
			while pos < record_length:
				pos, (name, value) = decode_pair(record, pos)
				try:
					s += encode_pair(name, str(capability[name]))
				except KeyError:
					pass

			l = len(s); p = -l & 7
			r = pack('!BBHHBx', self.version, 10, 0, l, p) + s
			if p:
				r += '\x00' * p

			self.wbuff += r

		elif self.msgtype == 1:
			role, self.flags = unpack('!HB5x', record)
			if role != 1:
				self.shutdown()
				raise NotImplemented('fastcgi unknow role')

			self.role = role

		elif self.msgtype == 2:
			self.shutdown()

		elif self.request_id == 0:
			l = FCGI_UNKNOWNTYPEBODY_LEN; p = -l & 7
			r = pack('!BBHHBx', self.version, 11, 0, l, p) + '!B7x'
			if p:
				r += '\x00' * p

			self.wbuff += r
		else:
			self.shutdown()
			raise NotImplemented('fastcgi unknow record')

		return True

	def filwbuff(self):
		l = len(self.wfile)
		while l:
			to_write = min(l, 8184)
			r = self.wfile[:to_write]
			self.wfile = self.wfile[to_write:]
			l -= to_write

			p = -to_write & 7
			r = pack('!BBHHBx', self.version, 6, self.request_id,
				to_write, p) + r
			if p:
				r += '\x00' * p

			self.wbuff += r

		if self.closed:
			p = -FCGI_ENDREQUESTBODY_LEN & 7
			r = pack('!BBHHBx', self.version, 3, self.request_id,
				FCGI_ENDREQUESTBODY_LEN, p) + pack('!LB3x', 0L, 0)
			if p:
				r += '\x00' * p
			self.wbuff += r

class Server:
	def __init__(self):
		global server_socket, serverpid
		server_socket = fromfd(0, AF_INET, SOCK_STREAM)
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

def decode_pair(s, pos=0):
	name_length = ord(s[pos])
	if name_length & 128:
		name_length = unpack('!L', s[pos:pos+4])[0] & 0x7fffffff
		pos += 4
	else:
		pos += 1

	value_length = ord(s[pos])
	if value_length & 128:
		value_length = unpack('!L', s[pos:pos+4])[0] & 0x7fffffff
		pos += 4
	else:
		pos += 1

	name = s[pos:pos+name_length]
	pos += name_length
	value = s[pos:pos+value_length]
	pos += value_length

	return (pos, (name, value))

def encode_pair(name, value):
	name_length = len(name)
	if name_length < 128:
		s = chr(name_length)
	else:
		s = pack('!L', name_length | 0x80000000L)

	value_length = len(value)
	if value_length < 128:
		s += chr(value_length)
	else:
		s += pack('!L', value_length | 0x80000000L)

	return s + name + value

def config(**args):
	if not args.get('verbose', False):
		global stdout, stderr
		sys.stdout = sys.__stdout__ = stdout = args.get('stdout', nul)
		sys.stderr = sys.__stderr__ = stderr = args.get('stderr', nul)

	global controller, socket_map
	controller = args['controller']

def mainloop():
	while True:
		try:
			stackless.run()

		except KeyboardInterrupt:
			break
		except:
			print_exc(file=stderr)
			continue

FCGI_ENDREQUESTBODY_LEN  = calcsize('!LB3x')
FCGI_UNKNOWNTYPEBODY_LEN = calcsize('!B7x' )

address = os.environ.get('FCGI_WEB_SERVER_ADDRS')
if address:
	address = map(lambda x: x.strip(), address.split(','))

capability = {
	'FCGI_MAX_CONNS' : 4194304,
	'FCGI_MAX_REQS'  : 4194304,
	'FCGI_MPXS_CONNS': 0 }

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

R = POLLIN | POLLPRI; W = POLLOUT
E = POLLERR | POLLHUP | POLLNVAL
RE = R | E; WE = W | E; RWE = R | W | E

R_UPLOAD = re.compile(r'([^\\/]+)$').search
R_UID = re.compile('(?:[^;]+;)* *uid=([^;\r\n]+)').search
T_UID = Template('Set-Cookie: uid=${uid}; path=/; expires=${expires}').safe_substitute
T_CONTENT_LENGTH = Template('Content-Length: ${content_length}').safe_substitute
T_RESPONSE = Template(
	'Status: 200 OK\r\n'
	'Cache-Control:no-cache, must-revalidate\r\n'
	'Pragma: no-cache\r\n'
	'Expires: Mon, 26 Jul 1997 05:00:00 GMT\r\n'
	'${header}\r\n'
	).safe_substitute
T_PUSHLET_BEGIN = Template(
	'Status: 200 OK\r\n'
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
socket_map = { serverpid: Server() }

try:
	import aisarue
	aisarue.config(pollster = pollster, socket_map = socket_map)

	import urllib as patch
	patch.urlopen = aisarue.urlopen
except ImportError:
	pass
