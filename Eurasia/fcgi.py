import os, re
import stackless
from socket2 import *
from _socket import fromfd
from sys import stdout, stderr
from struct import pack, unpack, calcsize

class FcgiClient(dict):
	def __init__(self):
		self.env = {}
		self._rbuf = ''
		self.tasklet = None
		self.read_channel = channel()
		self.write_channel = channel()
		self.handle_read = self.read4cache
		self.eof = self.overflow = self.closed = False

	@property
	def uid(self):
		try:
			return R_UID(self['Cookie']).groups()[0]
		except:
			return None

	def read(self, size=-1):
		if self.closed:
			raise Disconnect

		read = self.read4raw(size).send
		data = read(None)
		if data is None:
			self.handle_read = read
			data = self.read_channel.receive()
			self.handle_read = self.read4cache
			return data

		self.handle_read = self.read4cache
		return data

	def readline(self, size=-1):
		if self.closed:
			raise Disconnect

		read = self.read4line(size).send
		data = read(None)
		if data is None:
			self.handle_read = read
			data = self.read_channel.receive()
			self.handle_read = self.read4cache
			return data

		self.handle_read = self.read4cache
		return data

	def write(self, data):
		if self.closed:
			raise Disconnect

		l = len(data)
		while l:
			to_write = min(l, 8184)
			r = data[:to_write]
			data = data[to_write:]
			l -= to_write

			p = -to_write & 7
			r = pack('!BBHHBx', self.version, 6, self.request_id,
				to_write, p) + r
			if p:
				r += '\x00' * p

			self._write(r)

	def close(self):
		if self.closed:
			return

		p = -FCGI_ENDREQUESTBODY_LEN & 7
		r = pack('!BBHHBx', self.version, 3, self.request_id,
			FCGI_ENDREQUESTBODY_LEN, p) + pack('!LB3x', 0L, 0)
		if p:
			r += '\x00' * p

		self._write(r)
		self.shutdown()

	def shutdown(self):
		self.closed = True
		self._shutdown(self.request_id)

	def read4cache(self, data):
		if data:
			if len(self._rbuf) < max_size:
				self._rbuf += data
			else:
				self.eof = True
				self.overflow = True
		else:
			self.eof = True

	def read4raw(self, size=-1):
		data = self._rbuf
		if size < 0:
			self._rbuf = ''
			if self.eof:
				yield data
				raise StopIteration

			buffers = data and [data] or []
			data = yield
			while True:
				if not data:
					self.eof = True
					break

				buffers.append(data)
				data = yield

			self.read_channel.send(''.join(buffers))
		else:
			buf_len = len(data)
			if buf_len >= size:
				self._rbuf = data[size:]
				yield data[:size]
				raise StopIteration

			if self.eof:
				self._rbuf = ''
				yield data
				raise StopIteration

			buffers = data and [data] or []
			self._rbuf = ''
			data = yield
			while True:
				left = size - buf_len
				if not data:
					self.eof = True
					break

				buffers.append(data)
				n = len(data)
				if n >= left:
					self._rbuf = data[left:]
					buffers[-1] = data[:left]
					break

				buf_len += n
				data = yield

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

			if self.eof:
				self._rbuf = ''
				yield data
				raise StopIteration

			buffers = data and [data] or []
			self._rbuf = ''
			data = yield
			while True:
				if not data:
					self.eof = True
					break

				buffers.append(data)
				nl = data.find('\n')
				if nl >= 0:
					nl += 1
					self._rbuf = data[nl:]
					buffers[-1] = data[:nl]
					break

				data = yield

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

			if self.eof:
				self._rbuf = ''
				yield data
				raise StopIteration

			buffers = data and [data] or []
			self._rbuf = ''
			data = yield
			while True:
				if not data:
					self.eof = True
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
				data = yield

			self.read_channel.send(''.join(buffers))

def process_input(conn, addr):
	client = Client(conn, addr)
	pid = client.pid
	requests = {}

	while True:
		try:
			timeout = client.read(8)
			if len(timeout) != 8:
				print >> stderr, 'warning: fastcgi timeout, ignore'
				break

			version, msgtype, request_id, record_length, \
				padding_length = unpack('!BBHHBx', timeout)

			record = client.read(record_length)
			client.read(padding_length)

		except Disconnect:
			for request_id, request in requests.items():
				request.shutdown()
				if request.tasklet:
					request.tasklet.raise_exception(Disconnect)

			print >> stderr, 'warning: fastcgi connection down, ignore'
			break

		if msgtype == 5:
			request = requests[request_id]
			try:
				request.handle_read(record)
			except StopIteration:
				pass

		elif msgtype == 4:
			pos = 0
			request = requests[request_id]
			if record_length:
				while pos < record_length:
					pos, (name, value) = decode_pair(record, pos)
					name = name.upper()
					if name[:5] == 'HTTP_':
						request['-'.join(i.capitalize(
							) for i in name[5:].split('_'))] = value
					else:
						request.env[name] = value
			else:
				request.address = (
					request.env['REMOTE_ADDR'],
					int(request.env['REMOTE_PORT'] ) )

				request.path = request.env['REQUEST_URI']
				request.query_string = request.env['QUERY_STRING']
				request.method = request.env['REQUEST_METHOD'].upper()
				if request.method == 'POST':
					request['Content-Length'] = int(request.env['CONTENT_LENGTH'])

				ctrler = tasklet(controller)
				request.tasklet = ctrler
				try:
					ctrler(request)
				except:
					print_exc(file=stderr)

		elif msgtype == 9:
			pos = 0; s = ''
			while pos < record_length:
				pos, (name, value) = decode_pair(record, pos)
				try:
					s += encode_pair(name, str(capability[name]))
				except KeyError:
					pass

			l = len(s); p = -l & 7
			r = pack('!BBHHBx', version, 10, 0, l, p) + s
			if p:
				r += '\x00' * p

			client.write(r)

		elif msgtype == 1:
			request = FcgiClient()
			role, flags = unpack('!HB5x', record)
			if role != 1:
				print >> stderr, 'warning: fastcgi unknow role, ignore'
			else:
				request.role = role
				request.flags = flags
				request.version = version
				request._write = client.write
				requests[request_id] = request
				request.request_id = request_id
				request._shutdown = requests.__delitem__

		elif msgtype == 2:
			request = requests[request_id]
			request.shutdown()
			if request.tasklet:
				request.tasklet.raise_exception(Disconnect)

		elif msgtype == 8:
			print >> stderr, 'warning: fastcgi data record, ignore'

		elif request_id == 0:
			l = FCGI_UNKNOWNTYPEBODY_LEN; p = -l & 7
			r = pack('!BBHHBx', version, 11, 0, l, p) + '!B7x'
			if p:
				r += '\x00' * p

			client.write(r)

		else:
			print >> stderr, 'warning: fastcgi unknow record, ignore'

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

	def handle_read(self):
		ctrler = tasklet(process_input)
		try:
			conn, addr = server_socket.accept()
			try:
				ctrler(conn, addr)
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
	if args.has_key('controller'):
		global controller
		controller = args['controller']

	if not args.get('verbose', False):
		global stdout, stderr
		sys.stdout = sys.__stdout__ = stdout = args.get('stdout', nul)
		sys.stderr = sys.__stderr__ = stderr = args.get('stderr', nul)

def mainloop():
	while True:
		try:
			stackless.run()

		except KeyboardInterrupt:
			break
		except:
			print_exc(file=stderr)
			continue

R_UID = re.compile('(?:[^;]+;)* *uid=([^;\r\n]+)').search

FCGI_ENDREQUESTBODY_LEN  = calcsize('!LB3x')
FCGI_UNKNOWNTYPEBODY_LEN = calcsize('!B7x' )

max_size = 1073741824
address = os.environ.get('FCGI_WEB_SERVER_ADDRS')
if address:
	address = map(lambda x: x.strip(), address.split(','))

capability = {
	'FCGI_MAX_CONNS' : 4194304,
	'FCGI_MAX_REQS'  : 4194304,
	'FCGI_MPXS_CONNS': 4194304 }

multiprocessing = True
server_socket = serverpid = None
socket_map[serverpid] = Server()

try:
	m = getattr(__import__('Eurasia.x-request'), 'x-request')

except ImportError:
	pass
else:
	Form, SimpleUpload = m.Form, m.SimpleUpload

try:
	m = getattr(__import__('Eurasia.x-response'), 'x-response')

except ImportError:
	pass
else:
	m.T_RESPONSE = m.Template( (
		'Status: ${status} ${message}\r\n${headers}'
		) ).safe_substitute

	m.T_COMET_BEGIN = m.Template( (
		'Status: ${status} ${message}\r\n${headers}'
		'<html>\r\n<head>\r\n'
		'<META http-equiv="Content-Type" content="text/html">\r\n'
		'<meta http-equiv="Pragma" content="no-cache">\r\n'
		'<body>\r\n'
		'<script language="JavaScript">\r\n<!--\r\n'
		'if(!window.__comet__) window.__comet__ = window.parent?'
		'(window.parent.__comet__?parent.__comet__:parent):window;\r\n'
		'if(document.all) __comet__.escape("FUCK IE");\r\n'
		'//-->\r\n</script>\r\n<!--COMET BEGIN-->\r\n' ) ).safe_substitute

	Comet, Response = m.Comet, m.Response
