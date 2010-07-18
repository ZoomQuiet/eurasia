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

	if 'fcgihandler' in args or args.get('fcgi', False) or (
	          'port' not in args and 'bind' not in args):

		if handler in ('tcphandler', 'httphandler'):
			raise ValueError('%s handler not support fcgi mode, need address' %handler)

		import fcgi
		globals()['fcgi_mainloop'] = fcgi.mainloop
		return fcgi.config(**args)

	if handler in ('handler', 'controller', 'httphandler', 'wsgihandler',
	        'application', 'wsgi', 'app', 'wsgi_app', 'wsgi_application'):

		import web
		return web.config(**args)

	if handler == 'tcphandler':
		import socket2
		return socket2.config(**args)

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

def WsgiServer(application, bind=None, port=None, bindAddress=None, fcgi=False, verbose=True):
	addresses = len([i for i in bind, port, bindAddress if i is not None])
	if addresses > 1:
		raise TypeError('too many addresses')

	if   bind:
		args = dict(app=application, fcgi=fcgi, bind=bind)
	elif port:
		args = dict(app=application, fcgi=fcgi, port=port)
	elif bindAddress:
		args = dict(app=application, fcgi=fcgi, bind=[bindAddress])
	else:
		args = dict(app=application, fcgi=fcgi)

	config(**args)

	if not verbose:
		import utility
		utility.dummy()

	return type('WsgiServer', (), dict(run=staticmethod(mainloop),
	                         serve_forever=staticmethod(mainloop)))()

WSGIServer = WsgiServer
