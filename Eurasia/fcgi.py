import web
from web import *
from struct import pack, unpack, calcsize

class Client(dict):
	disconnected = property(lambda self: not socket_map.has_key(self.pid))

	def __init__(self, sock, addr):
		self.socket  = sock
		self.address = addr
		self.pid = sock.fileno()

		socket_map[self.pid] = self
		pollster.register(self.pid, RE)

		self._closed = False; self.request_closed = False
		self.rbuff = self.rfile = self.wfile = self.wbuff= ''
		self.message_length = None

	@property
	def uid(self):
		try: return R_UID(self['http_cookie']).groups()[0]
		except: return None

	def write(self, s):
		if not socket_map.has_key(self.pid):
			raise Disconnect

		self.wfile += s
		pollster.register(self.pid, WE)
		schedule()

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
				if self._closed:
					self.shutdown()
				else:
					try:
						pollster.unregister(self.pid)
					except KeyError:
						pass
			return

		if self._closed:
			self.shutdown()
		else:
			try:
				pollster.unregister(self.pid)
			except KeyError:
				pass

	def close(self, closed=True):
		self._closed = closed
		if closed and not self.request_closed:
			p = -FCGI_ENDREQUESTBODY_LEN & 7
			r = pack('!BBHHBx', self.version, 3, self.request_id,
				FCGI_ENDREQUESTBODY_LEN, p) + pack('!LB3x', 0L, 0)
			if p:
				r += '\x00' * p
			self.wbuff += r
			self.request_closed = True
			pollster.register(self.pid, WE)

	closed = property(lambda self: self._closed, close)

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
			self.rfile += record
			if len(self.rfile) > 30720:
				try:
					pollster.unregister(self.pid)
				except KeyError:
					pass

		elif self.msgtype == 4:
			pos = 0
			if record_length:
				while pos < record_length:
					pos, (name, value) = decode_pair(record, pos)
					self[name.lower()] = value
			else:
				self.path = self['request_uri']
				self.query_string = self['query_string']
				self.method = self['request_method'].lower()

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

web.T_RESPONSE = Template(
	'Status: 200 OK\r\n'
	'Cache-Control:no-cache, must-revalidate\r\n'
	'Pragma: no-cache\r\n'
	'Expires: Mon, 26 Jul 1997 05:00:00 GMT\r\n'
	'${header}\r\n'
	).safe_substitute
web.T_PUSHLET_BEGIN = Template(
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

pollster.unregister(serverpid)
del socket_map[serverpid]
socket_map[serverpid] = Server()
