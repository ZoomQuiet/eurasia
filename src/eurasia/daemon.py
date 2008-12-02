import os, sys
from urllib import urlopen
from sys import stderr, stdout
from httplib import HTTP, HTTPConnection
from SocketServer import UnixStreamServer
from signal import signal as setsignal, SIGCHLD, SIGTERM
from socket import socket, error as SocketError, \
	AF_UNIX, SOCK_STREAM
from SimpleXMLRPCServer import SimpleXMLRPCDispatcher, \
	SimpleXMLRPCRequestHandler, SimpleXMLRPCServer
from os import execv, chdir, chmod, dup2, fork, kill, umask, \
	unlink, waitpid, error as OSError, WNOHANG
from xmlrpclib import Fault, Transport, dumps as xmlrpc_dumps, \
	_Method as _XMLRPCMethod, ServerProxy as ServerProxy_N___G

class error(Exception): pass

class nul:
	write = staticmethod(lambda s: None)
	flush = staticmethod(lambda  : None)
	read  = staticmethod(lambda n: ''  )

class UnixStreamXMLRPCServer(UnixStreamServer, SimpleXMLRPCDispatcher):
	def __init__(self, address, requestHandler=SimpleXMLRPCRequestHandler,
		allow_none=False, encoding=None):

		self.logRequests = False

		SimpleXMLRPCDispatcher.__init__(self, allow_none, encoding)
		UnixStreamServer.__init__(self, address, requestHandler)

class Daemon:
	def __init__(self, **args):
		address      =           args[ 'address'             ]
		allow_none   =       args.get( 'allow_none', True    )
		encoding     =       args.get( 'encoding'  , 'utf-8' )

		self.verbose =       args.get( 'verbose'   , False   )
		self.stdout  =       args.get( 'stdout'    , nul     )
		self.stderr  =       args.get( 'stderr'    , nul     )

		try:
			ServerProxy(address).ping()
		except SocketError:
			pass
		else:
			raise error('another daemon is already up using socket %s' %repr(address))

		if isinstance(address, str):
			try:
				unlink(address)
			except OSError:
				pass

			self.manager = UnixStreamXMLRPCServer(address,
				allow_none=allow_none, encoding=encoding)

			self.pidfile = address
		else:
			self.manager = SimpleXMLRPCServer(address,
				allow_none=allow_none, encoding=encoding)

		self.pid     = None
		self.running = True

		self.program = args['program']

		SignalTools.setsignals(self)

		DaemonizeTools.daemonize(
			directory  = args.get( 'directory' , None    ),
			umask      = args.get( 'umask'     , 022     )  )

		self.register_function = lambda *args: (
			self.manager.register_function(*args) )

		self.register_function(lambda: self.stop()  , 'stop'  )
		self.register_function(lambda: self.status(), 'status')
		self.register_function(lambda: True         , 'ping'  )

	def __call__(self, *args):
		if not self.verbose:
			DaemonizeTools.close_files(self.stdout, self.stderr)
			del self.stdout, self.stderr

		pid = fork()

		if pid != 0:
			self.pid = pid
			while self.running:
				self.manager.handle_request()

			return pid

		else:
			try:
				for i in xrange(3, 100):
					try:
						os.close(i)
					except OSError:
						pass

				try:
					execv(sys.executable, tuple(
						[sys.executable, self.program] + list(args) ) )
				except OSError, err:
					print >> stderr, ( 'can\'t exec %r: %s\n'
						% (self.program, err) )

			finally:
				os._exit(127)

	def status(self):
		if not self.pid:
			return 'stopped'
		else:
			return 'running'

	def stop(self):
		if not self.pid:
			self.running = False
			if hasattr(self, 'pidfile'):
				try:
					unlink(self.pidfile)
				except OSError:
					pass

			raise error('no subprocess running')

		kill(self.pid, SIGTERM)
		self.running = False
		if hasattr(self, 'pidfile'):
			try:
				unlink(self.pidfile)
			except OSError:
				pass

class UnixStreamHTTPConnection(HTTPConnection):
	def connect(self):
		self.sock = socket(AF_UNIX, SOCK_STREAM)
		self.sock.connect(self.host)

class UnixStreamHTTP(HTTP):
	_connection_class = UnixStreamHTTPConnection

class UnixStreamTransport(Transport):
	def make_connection(self, host):
		return UnixStreamHTTP(host)

class UnixStreamServerProxy_NG:
	def __init__(self, uri, transport=None, encoding=None, verbose=0,
		allow_none=0, use_datetime=0):

		self.__host = uri
		self.__handler = '/RPC2'

		if not transport:
			self.__transport = UnixStreamTransport(use_datetime=use_datetime)

		self.__encoding = encoding
		self.__verbose = verbose
		self.__allow_none = allow_none

	def __request(self, methodname, params):
		request = xmlrpc_dumps(params, methodname, encoding=self.__encoding,
			allow_none=self.__allow_none)

		response = self.__transport.request(
			self.__host, self.__handler, request,
			verbose=self.__verbose )

		if len(response) == 1:
			response = response[0]

		return response

	def __getattr__(self, name):
		return _XMLRPCMethod(self.__request, name)

def ServerProxy(address, **args):
	if isinstance(address, str):
		return UnixStreamServerProxy_NG(address, **args)

	else:
		host, port = address
		host = (host, '127.0.0.1')[host == '0.0.0.0']
		return ServerProxy_N___G('http://%s:%d' %(host, port), **args)

class DaemonizeTools:
	@staticmethod
	def daemonize(**args):
		pid = fork()
		if pid != 0:
			os._exit(0)

		if args['directory']:
			try:
				chdir(args['directory'])
			except OSError, err:
				print >> stderr, ( 'can\'t chdir into %r: %s'
					% (args['directory'], err) )
			else:
				print >> stderr, ( 'set current directory: %r'
					% args['directory'] )

		os.setsid()
		umask(args['umask'])


	@staticmethod
	def close_files(stdout, stderr):
		devnull = hasattr(os, 'devnull') and os.devnull or '/dev/null'
		_stdin  = open(devnull, 'r'); _stdout = open(devnull, 'a+')
		_stderr = open(devnull, 'a+', 0)

		dup2(_stdin.fileno() , sys.stdin.fileno() )
		sys.stdin = sys.__stdin__ = nul
		dup2(_stdout.fileno(), sys.stdout.fileno())
		sys.stdout = sys.__stdout__ = stdout
		dup2(_stderr.fileno(), sys.stderr.fileno())
		sys.stderr = sys.__stderr__ = stderr

class SignalTools:
	daemon = None

	@staticmethod
	def setsignals(daemon):
		SignalTools.daemon = daemon
		setsignal(SIGCHLD, SignalTools.sigchild)

	@staticmethod
	def sigchild(sig, frame):
		try:
			pid, sts = waitpid(-1, WNOHANG)
			if pid == SignalTools.daemon.pid:
				SignalTools.daemon.pid = None

		except OSError:
			return
