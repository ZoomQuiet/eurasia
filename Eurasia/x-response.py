import re
from string import Template
from time import gmtime, strftime, time
from BaseHTTPServer import BaseHTTPRequestHandler

class Response(dict):
	def __init__(self, client, **args):
		dict.__init__(self, DEFAULTHEADERS)

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

class Comet(dict):
	def __init__(self, client, **args):
		dict.__init__(self, COMETHEADERS)

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

		self.client.write(T_COMET_BEGIN(headers=items, version=self.version,
			status=str(self.status), message=self.message))

		del self.version, self.status, self.message

	def end(self):
		self.client.write(COMET_END)
		self.client.close()

	def close(self):
		self.client.write(COMET_END)
		self.client.close()

class RemoteCall(object):
	def __init__(self, client, function):
		self.client = client
		self._function = function

	def __call__(self, *args):
		self.client.write(T_REMOTECALL(
			function  = self._function,
			arguments = args and ', '.join([json(arg) for arg in args]) or '' ) )

	def __getattr__(self, name):
		return RemoteCall(self.client, '%s.%s' %(self._function, name))

	def __getitem__(self, name):
		if isinstance(unicode):
			return RemoteCall(self.client, '%s[%s]' %(self._function, repr(name)[1:]))

		return RemoteCall(self.client, '%s[%s]' %(self._function, repr(name)))

def json(obj):
	if isinstance(obj, str): return repr(obj)
	elif isinstance(obj, unicode): return repr(obj)[1:]
	elif obj is None: return 'null'
	elif obj is True: return 'true'
	elif obj is False: return 'false'
	elif isinstance(obj, (int, long)): return str(obj)
	elif isinstance(obj, float): return _json_float(obj)
	elif isinstance(obj, (list, tuple)): return '[%s]' %', '.join(_json_array(obj))
	elif isinstance(obj, dict): return '{%s}' %', '.join(_json_object(obj))
	elif isinstance(obj, RemoteCall): return '__comet__.' + obj.function
	raise ValueError
def _json_array(l):
	for item in l: yield json(item)
def _json_object(d):
	for key in d: yield '"%s":%s' %(key, json(d[key]))
def _json_float(o):
	s = str(o)
	if (o < 0.0 and s[1].isdigit()) or s[0].isdigit(): return s
	if s == 'nan': return 'NaN'
	if s == 'inf': return 'Infinity'
	if s == '-inf': return '-Infinity'
	if o != o or o == 0.0: return 'NaN'
	if o < 0: return '-Infinity'
	return 'Infinity'

RESPONSES = dict((key, value[0]) for key, value in BaseHTTPRequestHandler.responses.items())
DEFAULTHEADERS = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
	'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT' }
COMETHEADERS = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
	'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT', 'Content-Type': 'text/html; charset=UTF-8' }

R_UID = re.compile('(?:[^;]+;)* *uid=([^;\r\n]+)').search
T_UID = Template('Set-Cookie: uid=${uid}; path=/; expires=${expires}').safe_substitute
T_RESPONSE = Template('${version} ${status} ${message}\r\n${headers}').safe_substitute
T_COMET_BEGIN = Template( (
	'${version} ${status} ${message}\r\n${headers}'
	'<html>\r\n<head>\r\n'
	'<META http-equiv="Content-Type" content="text/html">\r\n'
	'<meta http-equiv="Pragma" content="no-cache">\r\n'
	'<body>\r\n'
	'<script language="JavaScript">\r\n<!--\r\n'
	'if(!window.__comet__) window.__comet__ = window.parent?'
	'(window.parent.__comet__?parent.__comet__:parent):window;\r\n'
	'if(document.all) __comet__.escape("FUCK IE");\r\n'
	'//-->\r\n</script>\r\n<!--COMET BEGIN-->\r\n' ) ).safe_substitute
COMET_END = '<!--COMET END-->\r\n</body>\r\n</html>'
T_REMOTECALL = Template(
	'<script language="JavaScript">\r\n<!--\r\n'
	'__comet__.${function}(${arguments});\r\n'
	'//-->\r\n</script>\r\n' ).safe_substitute
