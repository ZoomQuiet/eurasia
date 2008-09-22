import re, stackless
from socket2 import *
from sys import stdout, stderr

class DefaultClient(dict):
	def __init__(self, conn, addr):
		client = Client(conn, addr)
		first = client.readline(8192)
		try:
			method, self.path, version = R_FIRST(first).groups()
		except AttributeError:
			client.shutdown()
			raise IOError

		self.version = version.upper()
		line = client.readline(8192)
		counter = len(first) + len(line)
		while True:
			try:
				key, value = R_HEADER(line).groups()
			except AttributeError:
				if line in ('\r\n', '\n'):
					break

				client.shutdown()
				raise IOError

			self['-'.join(i.capitalize() for i in key.split('-'))] = value
			line = client.readline(8192)
			counter += len(line)
			if counter > 10240:
				client.shutdown()
				raise IOError

		self.method = method.upper()
		if self.method == 'GET':
			self.left = 0
		else:
			try:
				self.left = int(self['Content-Length'])
			except:
				client.shutdown()
				raise IOError

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
		try:
			client = self.client
		except AttributeError:
			pass
		else:
			client.shutdown()

def DefaultHandler(controller):
	def handler(conn, addr):
		try:
			client = DefaultClient(conn, addr)
		except IOError:
			return

		try:
			controller(client)
		except:
			print_exc(file=stderr)

	return handler

class Server:
	def __init__(self, handler):
		sock = Socket(AF_INET, SOCK_STREAM)
		sock.setblocking(0)
		try:
			sock.setsockopt(SOL_SOCKET, SO_REUSEADDR,
				sock.getsockopt(SOL_SOCKET, SO_REUSEADDR) | 1)
		except SocketError:
			pass

		self.socket  = sock
		self.handler = handler
		self.pid = sock.fileno()
		pollster.register(self.pid, RE)

	def handle_read(self):
		ctrler = tasklet(self.handler)
		try:
			conn, addr = self.socket.accept()
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
	for name, value in (('fcgi', False), ('multicore', True), ('verbose', False),
		('address', {}), ('server', {}), ('tcpserver', {})):

		setattr(config, name, value)

	if args.has_key('verbose'):
		config.verbose = bool(args['verbose'])

	if args.has_key('multicore'):
		multicore = args['multicore']
		if not isinstance(multicore, (int, bool)):
			raise ValueError('multicore')

		config.multicore = multicore

	if args.has_key('fcgi') or args.has_key('fastcgi'):
		controller = args['fcgi'] if args.has_key('fcgi'
			) else args['fastcgi']

		import fcgi
		fcgi.config(controller=controller, verbose=config.verbose)
		config.fcgi = fcgi.mainloop

		global Comet, Response
		if hasattr(fcgi, 'Comet'):
			Comet = fcgi.Comet
		if hasattr(fcgi, 'Response'):
			Response = fcgi.Response

		return

	def cfghandler(srvdct, name):
		if not args.has_key(name):
			return

		handler = args[name]
		if callable(handler):
			try:
				address = config.address
			except AttributeError:
				raise ValueError('%s' %name)
			else:
				for addr in address.keys():
					srvdct[addr] = handler
		else:
			for address, handler in args[name]:
				if isinstance(address, (int, basestring)) == 1:
					host, port = '0.0.0.0', address
				elif len(address) == 2:
					host, port = address
				else:
					raise ValueError('%s' %name)

				srvdct[(host, int(port))] = handler

	if args.has_key('address'):
		host, port = args['address']
		config.address[(host, int(port))] = None
	if args.has_key('port'):
		config.address[('0.0.0.0', int(args['port']))] = None

	for name, key in (
		('handler'    , config.server   ),
		('controller' , config.server   ),
		('tcphandler' , config.tcpserver),
		('controller0', config.tcpserver) ):

		cfghandler(key, name)

	for address, controller in config.server.items():
		server = Server(DefaultHandler(controller))
		socket_map[server.pid] = server
		server.socket.bind(address)
		server.socket.listen(4194304)

	for address, handler in config.tcpserver.items():
		server = Server(handler)
		socket_map[server.pid] = server
		server.socket.bind(address)
		server.socket.listen(4194304)

	if not config.verbose:
		global stdout, stderr
		sys.stdout = sys.__stdout__ = stdout = args.get('stdout', nul)
		sys.stderr = sys.__stderr__ = stderr = args.get('stderr', nul)

def mainloop():
	if config.fcgi:
		config.fcgi()
		return

	if config.multicore == True:
		try:
			import multiprocessing as processing
		except ImportError:
			import processing

		config.multicore = processing.cpuCount()
	elif config.multicore == False:
		config.multicore = 0

	if config.multicore > 1:
		try:
			import multiprocessing as processing
		except ImportError:
			import processing

		for i in xrange(config.multicore - 1):
			proc = processing.Process(target=mainloop0, args=())
			proc.start()

		mainloop0()
	else:
		mainloop0()

def mainloop0():
	while True:
		try:
			stackless.run()

		except KeyboardInterrupt:
			break
		except:
			print_exc(file=stderr)
			continue

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
	Comet, Response = m.Comet, m.Response

R_UID    = re.compile(r'(?:[^;]+;)* *uid=([^;\r\n]+)').search
R_FIRST  = re.compile(r'^(GET|POST)[\s\t]+([^\r\n]+)[\s\t]+(HTTP/1\.[0-9])\r?\n$', re.I).match
R_HEADER = re.compile(r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*\r?\n$', re.I).match
