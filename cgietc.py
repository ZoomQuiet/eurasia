import re, string
from sys import stderr
from weakref import proxy
from cgi import parse_header
from urllib import unquote_plus
from traceback import print_exc

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
		self.httpfile = httpfile
		try:
			self.next = next = '--' + parse_header(httpfile.environ[
				'CONTENT_TYPE'])[1]['boundary']
		except:
			raise IOError

		c = 0
		self.last = last = self.next + '--'
		while True:
			line = httpfile.readline(65536)
			c += len(line)
			if not line:
				raise IOError

			if line[:2] == '--':
				data = line.strip()
				if data == next:
					c1 = (line[-2:] == '\r\n' and 2 or 1) << 1
					cnext = c1 + len(next)
					break

				if data == last:
					raise IOError

		filename = None
		while True:
			name = None
			for i in xrange(10):
				line = httpfile.readline(65536)
				c += len(line)
				line = line.strip()
				if not line:
					if not name:
						raise IOError

					if filename:
						fp = _upload_file_reader(self._reader().next)
						self.filename = filename
						try:
							size = int(httpfile.environ['CONTENT_LENGTH'])
						except:
							self.read, self.readline = fp.read, fp.readline
							return

						self.size = size - c - c1 - len(last)
						self.read, self.readline = fp.read, fp.readline
						return

					s = _upload_file_reader(self._reader().next).read()
					c += cnext + len(s)
					try: self[name].append(s)
					except KeyError: self[name] = s
					except AttributeError: self[name] = [self[name], s]
					break

				t1, t2 = line.split(':', 1)
				if t1.lower() != 'content-disposition':
					continue

	 			t1, t2 = parse_header(t2)
				if t1.lower() != 'form-data':
					raise IOError

				try: name = t2['name']
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

	def _reader(self):
		httpfile = self.httpfile
		line = httpfile.readline(65536)
		if not line:
			raise IOError

		next, last = self.next, self.last
		if line[:2] == '--':
			data = line.strip()
			if data == next or data == last:
				raise IOError

		el = line[-2:] == '\r\n' and '\r\n' or (line[-1] == '\n' and '\n' or '')
		while True:
			line2 = httpfile.readline(65536)
			if not line2:
				raise IOError

			if line2[:2] == '--' and el:
				data = line2.strip()
				if data == next or data == last:
					yield line[:-len(el)]
					break
			yield line
			line = line2
			el = line[-2:] == '\r\n' and '\r\n' or (line[-1] == '\n' and '\n' or '')

		while True:
			yield None

class _upload_file_reader:
	def __init__(self, reader):
		self.buff = ''
		self._read = reader

	def read(self, size=None):
		buff = self.buff
		if size:
			while len(buff) < size:
				data = self._read()
				if not data:
					self.buff = ''
					return buff
				buff += data

			self.buff = buff[size:]
			return buff[:size]

		d = [buff]
		self.buff = ''
		while True:
			data = self._read()
			if not data:
				return ''.join(d)

			d.append(data)

	def readline(self, size=None):
		s = self.buff
		if size:
			p = s.find('\n', 0, size)
			if p >= 0:
				p += 1
				self.buff = s[p:]
				return s[:p]

			elif len(s) > size:
				self.buff = s[size:]
				return s[:size]

			t = self._read()
			if not t:
				self.buff = ''
				return s

			s = s + t
			if len(s) > size:
				self.buff = s[size:]
				return s[:size]

			self.buff = ''
			return s
		else:
			p = s.find('\n')
			if p >= 0:
				p += 1
				self.buff = s[p:]
				return s[:p]

			else:
				t = self._read()
				self.buff = ''
				if not t:
					return s
				s += t
				return s

def wsgi(application):
	def controller(httpfile):
		environ = httpfile.environ
		environ.update(WSGI_DEFAULTS)
		environ['wsgi.input'] = proxy(httpfile)
		environ['wsgi.url_scheme' ] = 'https' \
			if environ.get('HTTPS') in ('on', '1') \
			else 'http'

		write = httpfile.write
		def start_response(status, response_headers, exc_info=None):
			if exc_info:
				try:
					if hasattr(httpfile, 'end'):
						raise exc_info[0], exc_info[1], exc_info[2]
				finally:
					exc_info = None

			elif hasattr(httpfile, 'end'):
				raise AssertionError('headers already set')

			httpfile._status = status
			httpfile.headers_set += response_headers
			return write

		try:
			for line in application(environ, start_response):
				line and write(line)

			if not hasattr(httpfile, 'end'):
				try:
					httpfile.close()
				except IOError:
					pass
		except:
			print_exc(file=stderr)
			httpfile._status = '500 Internal Server Error'
			try:
				httpfile.close()
			except IOError:
				pass

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
	'<script language="JavaScript">\r\n<!--\r\n%s'
	'window.__comet__=window.parent?(parent.__comet__?parent.__comet__:parent):window;\r\n'
	'__comet__.escape&&__comet__.escape("FUCK IE");\r\n'
	'//-->\r\n</script>\r\n<!--COMET BEGIN-->\r\n')

COMET_BEGIN = T_COMET_BEGIN %''

COMET_BEGIN_WITH_DOMAIN = string.Template(
	T_COMET_BEGIN %'document.domain="${domain}";\r\n').safe_substitute

COMET_END = '<!--COMET END-->\r\n</body>\r\n</html>'

COMETHEADERS = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
	'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT', 'Content-Type': 'text/html; charset=UTF-8' }

WSGI_DEFAULTS = {'wsgi.version': (1, 0), 'wsgi.errors': stderr, 'wsgi.run_once': False,
	'wsgi.multithread': False, 'wsgi.multiprocess': True}
