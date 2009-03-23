import re, string
from sys import stderr
from weakref import proxy
from cgi import parse_header
from urllib import unquote_plus

class Browser(object):
	def __init__(self, httpfile, domain=None):
		self.httpfile = httpfile
		httpfile.headers.update(COMETHEADERS)
		httpfile.wbegin(COMET_BEGIN_WITH_DOMAIN(domain=domain)) if domain \
		else httpfile.wbegin(COMET_BEGIN)

	def __getattr__(self, name):
		return RemoteCall(self.httpfile, name)

	def __getitem__(self, key):
		return self.httpfile[key]

	def __setitem__(self, key, value):
		self.httpfile.headers['-'.join(i.capitalize() for i in key.split('-'))] = value

	pid     = property(lambda self: self.httpfile.pid)
	address = property(lambda self: self.httpfile.address)
	uid     = property(lambda self: self.httpfile.uid,
	                   lambda self, uid: setattr(self.httpfile, 'uid', uid))

	script_name  = property(lambda self: self.httpfile.script_name )
	request_uri  = property(lambda self: self.httpfile.request_uri )
	query_string = property(lambda self: self.httpfile.query_string)

	fileno  = lambda self: self.httpfile.pid
	nocache = lambda self: self.httpfile.nocache()

	def fileno(self):
		return self.httpfile.sockfile.pid

	def end(self):
		self.httpfile.write(COMET_END)
		self.httpfile.close()

	def close(self):
		self.httpfile.write(COMET_END)
		self.httpfile.close()

	def shutdown(self):
		self.httpfile.close()

class RemoteCall(object):
	def __init__(self, httpfile, name):
		self._name    = name
		self.httpfile = httpfile

	def __call__(self, *args):
		self.httpfile.write(T_REMOTECALL(function = self._name,
			arguments = args and ', '.join([json(arg) for arg in args]) or ''))

	def __getattr__(self, name):
		return RemoteCall(self.httpfile, '%s.%s' %(self._name, name))

	def __getitem__(self, name):
		if isinstance(unicode):
			return RemoteCall(self.httpfile, '%s[%s]' %(self._name, repr(name)[1:]))

		return RemoteCall(self.httpfile, '%s[%s]' %(self._name, repr(name)))

def Form(httpfile, max_size=1048576):
	if httpfile.method == 'POST':
		length = int(httpfile.environ['CONTENT_LENGTH'])
		if int(length) > max_size:
			httpfile.close()
			raise IOError('overload')

		query = httpfile.environ['QUERY_STRING'].split('&') + \
		        httpfile.read(length).split('&')
	else:
		query = httpfile.environ['QUERY_STRING'].split('&')

	dct = {}
	for item in query:
		try:
			key, value = item.split('=', 1)
			value = unquote_plus(value)
			try:
				if isinstance(dct[key], list):
					dct[key].append(value)
				else:
					dct[key] = [dct[key], value]

			except KeyError:
				dct[key] = value

		except ValueError:
			continue

	return dct

class SimpleUpload(dict):
	def __init__(self, httpfile):
		try:
			next = '--' + parse_header(httpfile.environ[
			       'HTTP_CONTENT_TYPE'])[1]['boundary']
		except:
			raise IOError

		last, c = next + '--', 0
		while True:
			line = httpfile.readline(65536)
			c += len(line)
			if not line:
				raise IOError

			if line[:2] == '--':
				strpln = line.strip()
				if strpln == next:
					c1 = (line[-2:] == '\r\n' and 2 or 1) << 1
					c_next = c1 + len(next)
					break

				if strpln == last:
					raise IOError
		filename = None
		while True:
			name = None
			for i in xrange(32):
				line = httpfile.readline(65536)
				c += len(line)
				line = line.strip()
				if not line:
					if not name:
						raise IOError

					if filename:
						self.buff      = ''
						self.httpfile  = httpfile
						self.filename  = filename
						self._readline = self._readline(next, last).next
						try:
							size = int(httpfile.environ['CONTENT_LENGTH'])
						except:
							return

						self.size = size - c - c1 - len(last)
						return

					data = self.read()
					c += c_next + len(data)
					try:
						self[name].append(data)
					except KeyError:
						self[name] = data
					except AttributeError:
						self[name] = [self[name], data]

					break

				t1, t2 = line.split(':', 1)
				if t1.lower() != 'content-disposition':
					continue

	 			t1, t2 = parse_header(t2)
				if t1.lower() != 'form-data':
					raise IOError

				try:
					name = t2['name']
				except KeyError:
					raise IOError

				try:
					filename = t2['filename']
				except KeyError:
					continue

				m = R_UPLOAD(filename)
				if not m:
					raise IOError

				filename = m.groups()[0]

	def _readline(self, next, last):
		httpfile = self.httpfile
		line = httpfile.readline(65536)
		if not line:
			raise IOError

		if line[:2] == '--':
			strpln = line.strip()
			if strpln == next or strpln == last:
				raise IOError

		el = line[-2:] == '\r\n' and '\r\n' or (line[-1] == '\n' and '\n' or '')
		while True:
			line2 = httpfile.readline(65536)
			if not line2:
				raise IOError

			if line2[:2] == '--' and el:
				strpln = line2.strip()
				if strpln == next or strpln == last:
					yield line[:-len(el)]
					break
			yield line
			line = line2
			el = line[-2:] == '\r\n' and '\r\n' or (line[-1] == '\n' and '\n' or '')

		while True:
			yield None

	def read(size=None):
		buff = self.buff
		if size:
			while len(buff) < size:
				line = self._readline()
				if not line:
					self.buff = ''
					return buff

				buff += line

			self.buff = buff[size:]
			return buff[:size]

		d, self.buff = [buff], ''
		while True:
			line = self._readline()
			if not line:
				return ''.join(d)

			d.append(line)

	def readline(size=None):
		buff = self.buff
		if size:
			nl = buff.find('\n', 0, size)
			if nl >= 0:
				nl += 1
				self.buff = buff[nl:]
				return buff[:nl]

			elif len(buff) > size:
				self.buff = buff[size:]
				return buff[:size]

			t = self._readline()
			if not t:
				self.buff = ''
				return buff

			buff = buff + t
			if len(buff) > size:
				self.buff = buff[size:]
				return buff[:size]

			self.buff = ''
			return buff

		nl = buff.find('\n')
		if nl >= 0:
			nl += 1
			self.buff = buff[nl:]
			return buff[:nl]

		t = self._readline()
		self.buff = ''
		return buff + t if t else buff

def wsgi(application):
	def controller(httpfile):
		environ = httpfile.environ
		environ.update(WSGI_DEFAULTS)
		httpfile.wsgi_input = httpfile.read
		environ['eurasia.httpfile'] = proxy(httpfile)
		environ['wsgi.input'] = proxy(httpfile.wsgi_input)
		environ['wsgi.url_scheme' ] = 'https' \
			if environ.get('HTTPS') in ('on', '1') \
			else 'http'

		write = httpfile.write
		def start_response(status, response_headers, exc_info=None):
			httpfile._status = status
			httpfile.headers_set += response_headers
			return write

		try:
			for line in application(environ, start_response):
				line and write(line)
		finally:
			httpfile.close()

	return controller

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

Comet = Browser

R_UPLOAD = re.compile(r'([^\\/]+)$').search

T_REMOTECALL = string.Template(
	'<script language="JavaScript">\r\n<!--\r\n'
	'__comet__.${function}(${arguments});\r\n'
	'//-->\r\n</script>\r\n' ).safe_substitute

T_COMET_BEGIN = (
	'<html>\r\n<head>\r\n'
	'<meta http-equiv="Pragma" content="no-cache">\r\n'
	'<meta http-equiv="Content-Type" content="text/html">\r\n'
	'<body>\r\n'
	'<script language="JavaScript">\r\n<!--\r\n'
	'%s\r\n'
	'if(!window.__comet__) window.__comet__ = window.parent?'
	'(window.parent.__comet__?parent.__comet__:parent):window;\r\n'
	'if(document.all) __comet__.escape("FUCK IE");\r\n'
	'//-->\r\n</script>\r\n<!--COMET BEGIN-->\r\n')

COMET_BEGIN = T_COMET_BEGIN %(
	'var dmlst = document.domain.split(\'.\'), dmlen = dmlst.length;\r\n'
	'if(dmlen > 1) document.domain = [dmlst[dmlen-2], dmlst[dmlen-1]].join(\'.\');\r\n'
	'delete dmlst, dmlen;\r\n')

COMET_BEGIN_WITH_DOMAIN = string.Template(
	T_COMET_BEGIN %'document.domain = "${domain}";').safe_substitute

COMET_END = '<!--COMET END-->\r\n</body>\r\n</html>'

COMETHEADERS = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
	'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT', 'Content-Type': 'text/html; charset=UTF-8' }

WSGI_DEFAULTS = {'wsgi.version': (1, 0), 'wsgi.errors': stderr, 'wsgi.run_once': False,
	'wsgi.multithread': False, 'wsgi.multiprocess': True}
