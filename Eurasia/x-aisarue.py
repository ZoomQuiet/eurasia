import os.path
import re, urllib
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
		port = netloc[1]
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
		if first[-2:] != '\r\n':
			client.shutdown()
			raise IOError

		l = first[:-2].split(None, 2)
		if len(l) == 3:
			version, self.status, self.message = l
			self.version = version.upper()
			if self.version[:5] != 'HTTP/':
				client.shutdown()
				raise IOError

		elif len(l) == 2:
			version, self.status = l
			self.version = version.upper()
			self.message = ''
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
		if socket_map.has_key(self.pid):
			self.shutdown()

R_UID = re.compile('(?:[^;]+;)* *uid=([^;\r\n]+)').search
urllib.urlopen = urlopen
