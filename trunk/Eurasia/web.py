import re, stackless
from socket2 import *
from sys import stdout, stderr

class DefaultClient(dict):
	def __init__(self, conn, addr):
		client = Client(conn, addr)

		first = client.readline(8192)
		if first[-2:] != '\r\n':
			client.shutdown()
			raise IOError

		l = first[:-2].split(None, 2)
		if len(l) == 3:
			method, self.path, version = l
			self.version = version.upper()
			if self.version[:5] != 'HTTP/':
				client.shutdown()
				raise IOError

		elif len(l) == 2:
			method, self.path = l
			self.version = 'HTTP/1.0'
		else:
			client.shutdown()
			raise IOError

		counter = len(first)
		line = client.readline(8192)
		while line != '\r\n':
			if line[-2:] != '\r\n':
				client.shutdown()
				raise IOError

			counter += len(line)
			if counter > 10240:
				client.shutdown()
				raise IOError

			try: key, value = line[:-2].split(':', 1)
			except ValueError:
				continue

			self['-'.join(i.capitalize() for i in key.split('-'))] = value.strip()
			line = client.readline(8192)

		self.method = method.upper()
		if self.method == 'GET':
			self.left = 0
		else:
			self.left = int(self['Content-Length'])

		self.address  = client.address
		self.pid      = client.pid
		self.write    = client.write
		self.close    = client.shutdown
		self.shutdown = client.shutdown
		self.client   = client

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

	def __del__(self):
		if socket_map.has_key(self.pid):
			self.shutdown()

def default0(conn, addr):
	try:
		client = DefaultClient(conn, addr)
	except IOError:
		return

	try:
		controller(client)
	except:
		print_exc(file=stderr)

class Server:
	def __init__(self):
		global server_socket, serverpid
		server_socket = Socket(AF_INET, SOCK_STREAM)
		server_socket.setblocking(0)
		try:
			server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR,
				server_socket.getsockopt(
					SOL_SOCKET, SO_REUSEADDR) | 1)
		except SocketError:
			pass

		serverpid = server_socket.fileno()
		pollster.register(serverpid, RE)

	def handle_read(self):
		ctrler = tasklet(controller0)
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

def config(**args):
	if not args.get('verbose', False):
		global stdout, stderr
		sys.stdout = sys.__stdout__ = stdout = args.get('stdout', nul)
		sys.stderr = sys.__stderr__ = stderr = args.get('stderr', nul)

	if args.has_key('controller0'):
		global controller0
		controller0 = args['controller0']

	elif args.has_key('controller'):
		global controller
		controller = args['controller']

	if args.has_key('address'):
		server_socket.bind(args['address'])
		server_socket.listen(4194304)

	elif args.has_key('port'):
		server_socket.bind((
			args.get('host', '0.0.0.0'),
			args.get('port', 8080)))

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

R_UID = re.compile('(?:[^;]+;)* *uid=([^;\r\n]+)').search

controller0 = default0
server_socket = serverpid = None
socket_map[serverpid] = Server()

for x in ('x-hypnus', 'x-aisarue'):
	try:
		__import__('Eurasia.%s' %x)
	except ImportError:
		pass

try:
	m = getattr(__import__('Eurasia.x-request'), 'x-request')
except ImportError:
	pass
else:
	Form = m.Form
	SimpleUpload = m.SimpleUpload

try:
	m = getattr(__import__('Eurasia.x-response'), 'x-response')
except ImportError:
	pass
else:
	Comet    = m.Comet
	Response = m.Response

try:
	m = getattr(__import__('Eurasia.x-nonblocking'), 'x-nonblocking')
except ImportError:
	pass
else:
	nonblocking = m.nonblocking
