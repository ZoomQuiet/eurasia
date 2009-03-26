__version__ = '3.0.0'

def config(**args):
	handler = None
	for name in ('controller' , 'handler'    , 'tcphandler' ,
	             'httphandler', 'fcgihandler', 'wsgihandler',
	             'application', 'wsgi', 'app', 'wsgi_app', 'wsgi_application'):

		if name in args:
			if handler is not None:
				raise TypeError('too many handlers')

			handler = name

	bind = None
	if 'bind' in args:
		if 'port' in args:
			raise TypeError('too many addresses')

		bind = args['bind']

	elif 'port' in args:
		bind = '0.0.0.0:%d' %args['port']

	if handler is not None:
		if handler in ('controller', 'handler'):
			if bind is not None:
				import web
				web.config(handler=args[handler], bind=bind)
			else:
				import fcgi
				fcgi.config(handler=args[handler])
				globals()['fcgi_mainloop'] = fcgi.mainloop

		elif handler in ('wsgihandler', 'application', 'wsgi', 'app',
		                 'wsgi_app'   , 'wsgi_application'):

			if bind is not None:
				import web
				web.config(wsgi=args[handler], bind=bind)
			else:
				import fcgi
				fcgi.config(wsgi=args[handler])
				globals()['fcgi_mainloop'] = fcgi.mainloop

		elif handler == 'httphandler':
			import web
			if bind is None:
				web.config(handler=args['httphandler'])
			else:
				web.config(handler=args['httphandler'], bind=bind)

		elif handler == 'fcgihandler':
			if bind is not None:
				raise TypeError('fcgi can\' bind to address %r' %bind)

			import fcgi
			fcgi.config(handler=args['fcgihandler'])
			globals()['fcgi_mainloop'] = fcgi.mainloop

		elif handler == 'tcphandler':
			import socket2
			if bind is None:
				socket2.config(handler=args['tcphandler'])
			else:
				socket2.config(handler=args['tcphandler'], bind=bind)

def mainloop(cpus=False):
	gdct = globals()
	if 'procname' in gdct:
		import utility
		if 'libc' in gdct:
			utility.setprocname(gdct['procname'], libc=gdct['libc'])
		else:
			utility.setprocname(gdct['procname'])

	uid = gdct.get('uid', gdct.get('user'))
	if uid:
		import utility
		utility.setuid(uid)

	if 'verbose' in gdct:
		verbose = gdct['verbose']
		if isinstance(verbose , basestring) and str(
		              verbose ).lower() in ('off', 'false', 'no', 'n'):

			verbose = False

		if not verbose:
			import utility
			utility.dummy()

	if 'fcgi_mainloop' in gdct:
		return gdct['fcgi_mainloop']()

	import socket2
	socket2.mainloop(cpus)

def WsgiServer(application, bind=None, port=None, bindAddress=None, verbose=True):
	idx = None
	for i, j in enumerate((bind, port, bindAddress)):
		if j is not None:
			if idx is not None:
				raise TypeError('too many addresses')

			idx = i

	if idx is None:
		import fcgi
		server = fcgi.config(wsgi=application)
		globals()['fcgi_mainloop'] = fcgi.mainloop

	elif idx == 0:
		import web
		server = web.config(wsgi=application, bind=bind)

	elif idx == 1:
		import web
		server = web.config(wsgi=application, port=port)

	else:
		import web
		server = web.config(wsgi=application, bind='%s:%d' %bindAddress)

	if not verbose:
		import utility
		utility.dummy()

	server.serve_forever = server.run = mainloop
	return server

WSGIServer = WsgiServer
