import re
from string import Template
from time import gmtime, strftime, time
from BaseHTTPServer import BaseHTTPRequestHandler

class Response(dict):
	def __init__(self, client, **args):
		dict.__init__(DEFAULTHEADERS)

		self.client = client
		self.uid = None
		self.content = ''

		self.version = args.get('version', 'HTTP/1.1')
		self.status  = int(args.get('status' , 200))
		self.message = args.get('message', RESPONSES[self.status])

	def write(self, data):
		self.content += data

	def begin(self):
		items = ['%s: %s' %(key, value) for key, value in self.items()]
		if self.uid:
			items.append(T_UID(uid=self.uid, expires=strftime(
				'%a, %d-%b-%Y %H:%M:%S GMT', gmtime(time() + 157679616) ) ) )

		items.append('\r\n')
		items = '\r\n'.join(items)

		client = self.client

		client.write(T_RESPONSE(headers=items, version=self.version,
			status=str(self.status), message=self.message))

		self.write = client.write
		self.close = self.end = client.close
		delattr(self, 'content')

	def close(self):
		self['Content-Length'] = str(len(self.content))
		items = ['%s: %s' %(key, value) for key, value in self.items()]
		if self.uid:
			items.append(T_UID(uid=self.uid, expires=strftime(
				'%a, %d-%b-%Y %H:%M:%S GMT', gmtime(time() + 157679616) ) ) )

		items.append('\r\n')
		items = '\r\n'.join(items)

		self.client.write(T_RESPONSE(headers=items, version=self.version,
			status=str(self.status), message=self.message) + self.content)

		self.client.close()

class Pushlet(dict):
	def __init__(self, client, **args):
		dict.__init__(DEFAULTHEADERS)

		self.client = client
		self.uid = None

		self.version = args.get('version', 'HTTP/1.1')
		self.status  = int(args.get('status' , 200))
		self.message = args.get('message', RESPONSES[self.status])

	def __getattr__(self, name):
		return RemoteCall(self.client, name)

	def begin(self):
		items = ['%s: %s' %(key, value) for key, value in self.items()]
		if self.uid:
			items.append(T_UID(uid=self.uid, expires=strftime(
				'%a, %d-%b-%Y %H:%M:%S GMT', gmtime(time() + 157679616) ) ) )

		items.append('\r\n')
		items = '\r\n'.join(items)

		self.client.write(T_PUSHLET_BEGIN(headers=items, version=self.version,
			status=str(self.status), message=self.message))

	def end(self):
		self.client.write(PUSHLET_END)
		self.client.close()

	def close(self):
		self.client.write(PUSHLET_END)
		self.client.close()

class RemoteCall(object):
	def __init__(self, client, function):
		self.client = client
		self.function = function

	def __call__(self, *args):
		self.client.write(T_REMOTECALL(
			function  = self.function,
			arguments = args and ', '.join([json(arg) for arg in args]) or '' ) )

	def __getattr__(self, name):
		return RemoteCall(self.client, '%s.%s' %(self.function, name))

	def __getitem__(self, name):
		if isinstance(unicode):
			return RemoteCall(self.client, '%s[%s]' %(self.function, repr(name)[1:]))

		return RemoteCall(self.client, '%s[%s]' %(self.function, repr(name)))

RESPONSES = dict((key, value[0]) for key, value in BaseHTTPRequestHandler.responses.items())
DEFAULTHEADERS = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
	'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT' }

R_UPLOAD = re.compile(r'([^\\/]+)$').search
R_UID = re.compile('(?:[^;]+;)* *uid=([^;\r\n]+)').search
T_UID = Template('Set-Cookie: uid=${uid}; path=/; expires=${expires}').safe_substitute
T_RESPONSE = Template('${version} ${status} ${message}\r\n${headers}').safe_substitute
T_PUSHLET_BEGIN = Template( (
	'${version} ${status} ${message}\r\n${headers}'
	'<html>\r\n<head>\r\n'
	'<META http-equiv="Content-Type" content="text/html">\r\n'
	'<meta http-equiv="Pragma" content="no-cache">\r\n'
	'<body>\r\n'
	'<script language="JavaScript">\r\n'
	'if(document.all) parent.escape("FUCK IE");\r\n'
	'</script>\r\n' ) ).safe_substitute
PUSHLET_END = '</body>\r\n</html>'
T_REMOTECALL = Template(
	'<script language="JavaScript">\r\n'
	'parent.${function}(${arguments});\r\n'
	'</script>\r\n' ).safe_substitute
