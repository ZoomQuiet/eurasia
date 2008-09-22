import os.path, re
from copy import copy
from socket2 import *
from urlparse import urlparse
from StringIO import StringIO

def urlopen(url, data='', headers={}, **args):
	headers = dict(('-'.join(i.capitalize() for i in key.split('-')), value
		) for key, value in headers.items() )
	for key, value in args.items():
		headers['-'.join(i.capitalize() for i in key.split('_'))] = value

	scm, netloc, path, params, query, fragment = urlparse(url)
	https = scm.lower() == 'https'
	netloc = netloc.split(':')
	host = netloc[0]
	try:
		port = int(netloc[1])
	except IndexError:
		port = https and 443 or 80

	sock = Socket(AF_INET, SOCK_STREAM)
	sock.setblocking(0)
	try:
		sock.setsockopt(
			SOL_SOCKET, SO_REUSEADDR,
			sock.getsockopt(
				SOL_SOCKET, SO_REUSEADDR) | 1)
	except SocketError:
		pass

	if https and ssl:
		err = sock.connect_ex((host, 80))
		if err not in (EINPROGRESS, EALREADY, EWOULDBLOCK, 0, EISCONN):
			raise SocketError, (err, errorcode[err])

		sock = __import__('httplib').FakeSocket(
			sock, ssl(sock, None, None))
	else:
		err = sock.connect_ex((host, port))
		if err not in (EINPROGRESS, EALREADY, EWOULDBLOCK, 0, EISCONN):
			raise SocketError, (err, errorcode[err])

	path = path or '/'
	path = query and '%s?%s' %(path, query) or path

	if   isinstance(data, str):
		l = len(data)
		read = StringIO(data).read

	elif isinstance(data, file):
		l = int(os.path.getsize(data.name))
		read = data.read

	elif hasattr(data, 'read'):
		if not callable(data.read):
			raise ValueError('data type %r' %type(data))

		read = data.read
		if hasattr(data, 'len'):
			l = int(data.len)
		elif hasattr(data, '__len__') and callable(data, '__len__'):
			l = len(data)
		elif headers.has_key('Content-Length'):
			l = int(headers['Content-length'])
		else:
			data = read()
			l = len(data)
			read = StringIO(data).read

	if l:
		method = 'POST'
		headers['Content-Length'] = str(l)
	else:
		method = 'GET'

	if not headers.has_key('Host'): headers['Host'] = host
	headers = '\r\n'.join('%s: %s' %(key, value) for key, value in headers.items())

	client = Client(sock, (host, port))
	client.write(headers and (
		'%s %s HTTP/1.0\r\n%s\r\n\r\n' %( method, path, headers
		)) or '%s %s HTTP/1.0\r\n\r\n' %( method, path ) )

	data = read(30720)
	while data:
		client.write(data)
		data = read(30720)

	return Aisarue(client)

class Aisarue(dict):
	def __init__(self, client):
		first = client.readline(8192)
		try:
			version, self.status, self.message = R_FIRST(first).groups()
		except AttributeError:
			client.shutdown()
			raise IOError

		self.version = version.upper()
		line = client.readline(8192)
		print line
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
			print line
			counter += len(line)
			if counter > 10240:
				client.shutdown()
				raise IOError

		self.pid      = client.pid
		self.close    = client.shutdown
		self.shutdown = client.shutdown
		self.read     = client.read
		self.readline = client.readline
		self.client   = client

	@property
	def uid(self):
		try:
			return R_UID(self['Cookie']).groups()[0]
		except:
			return None

	def __del__(self):
		try:
			client = self.client
		except AttributeError:
			pass
		else:
			client.shutdown()

R_UID    = re.compile(r'(?:[^;]+;)* *uid=([^;\r\n]+)').search
R_FIRST  = re.compile(r'^(HTTP/1\.[0-9])[\s\t]*([1-9][0-9][0-9])[\s\t]*([^\r\n]*)[\s\t]*\r?\n$', re.I).match
R_HEADER = re.compile(r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*\r?\n$', re.I).match
