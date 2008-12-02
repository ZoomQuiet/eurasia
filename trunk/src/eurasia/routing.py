import re, os, sys
class error(Exception):
	pass

def install():
	import web
	for address, node in startup.items():
		if isinstance(node, dict):
			web.Server(address, web.HttpHandler(getctrl(node)))
		else:
			web.Server(address, web.TcpHandler(node))

def config(**args):
	alst, hlst = [], []
	if 'bind' in args:
		if 'port' in args:
			raise error('conflict between bind and port')

		for j in [i for i in args['bind'].split(',') if i.strip()]:
			l = j.split(':')
			if len(l) == 1:
				ip, port = l[0].strip(), 80

			elif len(l) == 2:
				try:
					ip, port = l[0].strip(), int(l[1].strip())
				except (ValueError, TypeError):
					raise error('can\' bind to address %s' %j.strip())

			alst.append((ip, port))
	else:
		if not 'port' in args:
			raise error('bind is required')

		try:
			alst.append(('0.0.0.0', int(args['port'])))
		except (ValueError, TypeError):
			raise error('can\'t bind to port %r' %port)

	controller = [args[i] for i in ['httpserver', 'handler', 'controller'
		] if args.has_key(i)]

	tcpserver = [args[i] for i in ['tcpserver', 'tcphandler', 'tcpcontroller'
		] if args.has_key(i)]

	if len(tcpserver) > 0 and len(controller) > 0:
		raise error('conflict between tcp server and http server')

	if len(tcpserver) > 0:
		controller = None
		if len(tcpserver) != 1:
			raise error('too many tcp servers')

		if args.has_key('host'):
			raise error('tcp server not support host')

		tcpserver = getproduct(tcpserver[0])

	if len(controller) > 0:
		tcpserver = None
		if len(controller) != 1:
			raise error('too many http servers')

		controller = getproduct(controller[0])

	if tcpserver:
		for key in alst:
			if startup.has_key(key):
				if isinstance(startup[key], dict):
					raise error('tcp server not support host')

				raise error('duplicate ip address %s:%d' %key)

			startup[key] = tcpserver

		return

	if not controller:
		raise error('controller is required')

	if not 'host' in args:
		for i in alst:
			if startup.has_key(i):
				if not isinstance(startup[i], dict):
					raise error('tcp server not support host')

				if startup[i][None]:
					raise error('duplicate controllers %s:%d' %i)
			else:
				startup[i] = {None: controller}
		return

	for j in [i for i in args['host'].split(',') if i.strip()]:
		l = j.split(':')
		if len(l) == 1:
			host, port = l[0].strip(), None

		elif len(l) == 2:
			try:
				host, port = l[0].strip(), int(l[1].strip())

			except (ValueError, TypeError):
				raise error('incorrect host %s' %j.strip())

		hlst.append((host, port))

	for host, port in hlst:
		host = list(reversed([i.strip() for i in host.split('.')]))
		for key in alst:
			if startup.has_key(key):
				node = startup[key]
			else:
				startup[key] = {}
				node = startup[key]

			for i in host:
				if node.has_key(i):
					node = node[i]
				else:
					node[i] = {}
					node = node[i]

			if node.has_key(port):
				raise error('duplicate controllers (%s:%d)' %key)

			node[port] = controller

class createproducts(object):
	def __getattr__(self, name):
		return productsobject(name)

class productsobject(object):
	def __init__(self, name):
		self.__dict__['__t_path'] = ['Products', name]

	def __getattr__(self, name):
		self.__dict__['__t_path'].append(name)
		return self

def getproduct(o):
	if hasattr(o, '__t_path'):
		path, o.__t_path = o.__t_path, ['Products']

	elif isinstance(o, basestring):
		path = [i.strip() for i in o.split('.')]

	elif callable(o):
		return o

	else:
		raise error('unknow controller')

	ctrl = __import__('.'.join(path[:-1]))
	for name in path[1:]:
		ctrl = getattr(ctrl, name)

	return ctrl

def getctrl(node):
	if len(node) == 1 and node.has_key(None):
		return node[None]

	try:
		default = node[None]
	except KeyError:
		default = lambda client: client.close()

	def ctrl(client):
		lastcallable = default
		try:
			host = client['Host']
		except KeyError:
			return lastcallable(client)

		try:
			host, port = host.split(':')
		except ValueError:
			port = 80
		else:
			try:
				port = int(port)
			except (ValueError, TypeError):
				return lastcallable(client)

		node1 = node
		for name in reversed(host.lower().split('.')):
			try:
				node1 = node1[name.strip()]
			except KeyError:
				return lastcallable(client)

			try:
				lastcallable = node1[port]
			except KeyError:
				try:
					lastcallable = node1[None]
				except KeyError:
					continue

		return lastcallable(client)

	return ctrl

startup, Products = {}, createproducts()
