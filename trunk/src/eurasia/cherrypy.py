import re, sys
import mimetypes
from os import fstat
from sys import stderr
from urllib import unquote
from string import Template
from urlparse import urljoin
from traceback import print_exc
from os import getcwd, curdir, pardir
from posixpath import normpath as posixnormpath, splitext as posixsplitext
from os.path import isdir, exists, splitdrive, split as pathsplit, join as pathjoin

def expose(func):
	if func.__name__ == '__call__':
		f = sys._getframe(1)
		if f.f_code.co_name != '<module>':
			f.f_locals['exposed'] = True
	else:
		func.exposed = True

	return func

class CherryEmulator(dict):
	def __init__(self, root=None):
		self.root = root if root else default200
		self.update(defaultresponses)

	def __call__(self, client):
		if hasattr(client, 'location'):
			loc, qs = client.location, client.querystring
		else:
			loc, qs = client.path, ''
			try:
				loc, qs = loc.split('?', 1)
			except ValueError:
				pass

			client.querystring = qs

		p, t = loc, urls(loc)
		a, b = t.next()
		if a or not b:
			return client.close()

		location = loc
		node, lastcallable = self.root, None
		for a, b in t:
			if callable(node) and hasattr(node, 'exposed') and node.exposed:
				lastloc, lastcallable = p, node

			try:
				node = node[a]
			except:
				try:
					node = getattr(node, a)
				except:
					node = None

			if node is None:
				break

			if not b:
				if callable(node) and hasattr(node, 'exposed') and node.exposed:
					lastloc, lastcallable = '', node
				break
			p = b

		if lastcallable is None:
			return self[404](client)

		client.location = lastloc
		try:
			lastcallable(client)

		except NotFound:
			return self[404](client)

		except Forbidden:
			return self[403](client)

		except NotModified:
			return self[304](client)

		except Redirect, e:
			urls1, status = e.args
			try:
				host = client['Host']
			except KeyError:
				return self[404](client)

			browser_url = 'http://%s%s' %(host, location)
			abs_urls = [urljoin(browser_url, url) for url in (
				[urls1] if isinstance(urls1, basestring) else urls1)]

			if status is None:
				status = 302 if client.version == 'HTTP/1.0' else 303
			else:
				status = int(status)
				if status < 300 or status > 399:
					raise ValueError('status must be between 300 and 399.')

			if status in multiredirects:
				return self[status](client, abs_urls)
			elif status is 304:
				return self[status](client)
			elif status is 305:
				return self[status](client, abs_urls[0])
			else:
				raise ValueError('The %s status code is unknown.' % status)

		except InternalServerError:
			return self[500](client)
		except:
			print_exc(file=stderr)
			return client.close()

class Directory:
	index = ['index.html', 'index.htm']
	exposed = True

	def __init__(self, base=None):
		self.base = base or getcwd()

	def __call__(self, client):
		path = client.location
		fullpath = translate_path(self.base, path)
		if isdir(fullpath):
			if path[-1:] != '/':
				raise Redirect(client.path.split('?', 1)[0] + '/')

			return self.listdir(client, fullpath)

		self.fetch(client, fullpath)

	def listdir(self, client, dirname):
		for index in self.index:
			index = pathjoin(dirname, index)
			if exists(index):
				return self.fetch(client, index)

		raise Forbidden

	def fetch(self, client, filename):
		try:
			fd = open(filename, 'rb')
		except (OSError, IOError):
			raise NotFound
		else:
			try:
				data = template200h(
					version=client.version,
					content_length=str(fstat(fd.fileno()).st_size),
					content_type=guess_type(filename))
				while data:
					client.write(data)
					data = fd.read(8192)
			finally:
				try:
					fd.close()
				finally:
					client.close()

def urls(url):
	p1 = 0
	while True:
		p = url.find('/', p1)
		if p == -1:
			yield url[p1:], ''
			break

		yield url[p1:p], url[p:]
		p1 = p + 1

def translate_path(*args):
	try:
		path = args[1]
	except IndexError:
		path = args[0]
		base = getcwd()
	else:
		base = args[0]

	for word in filter(None, posixnormpath(unquote(path)).split('/')):
		word = pathsplit(splitdrive(word)[1])[1]
		if word in (curdir, pardir):
			continue

		base = pathjoin(base, word)

	return base

def guess_type(path):
	try:
		return _mimetypes[posixsplitext(path)[1].lower()]
	except KeyError:
		return 'application/octet-stream'

if not mimetypes.inited:
	mimetypes.init()

_mimetypes = mimetypes.types_map.copy()

eurasia_version = sys.modules['eurasia'].__version__
try:
	platform = 'CherryEmulator (Eurasia %s/Python %s/%s)' %tuple([eurasia_version] +
		[i.strip() for i in re.compile(r'^([^(]*)\([^)]*\)[^(]+\(([^)]*)\)'
		).match(sys.version).groups()])

except AttributeError:
	platform = 'CherryEmulator (Eurasia %s)' %eurasia_version

class Redirect(Exception):
	def __init__(self, urls, status=None):
		Exception.__init__(self, urls, status)

for i in ('NotFound', 'Forbidden', 'NotModified', 'InternalServerError'):
	exec '''class %s(Exception):
	pass''' %i

for i in (200, 403, 404, 500):
	exec '''def default%d(client):
	client.write(template%d(version=client.version, path=client.path.split('?', 1)[0]))

	client.close()''' %(i, i)

for i in (300, 301, 302, 303, 307):
	exec '''def default%d(client, urls):
	client.write(template%db(version=client.version, location=urls[0], locations='\t<br>'.join(
		template%du(url=url) for url in urls)))

	client.close()''' %(i, i, i)

def default304(client):
	client.write(template304(version=client.version))
	client.close()

def default305(client, url):
	client.write(template305(version=client.version, location=url))
	client.close()

multiredirects   = dict((i, eval('default%d' %i)) for i in (300, 301, 302, 303, 307))
defaultresponses = dict((i, eval('default%d' %i)) for i in (300, 301, 302, 303, 304, 305, 307, 403, 404, 500))

templatexxx = '''\
${version} %%%%d %%%%s\r\nContent-Type: text/html\r\n%%s\r\n<html>
<head>
	<title>%%%%s</title>
</head>
<body>
%%%%s
	<hr>
	<address>%s</address>
</body>
</html>''' %platform

template_normal   = templatexxx %''
template_redirect = templatexxx %'Location: ${location}\r\n'
template200h = Template('${version} 200 OK\r\nContent-Type: ${content_type}\r\nContent-Length: ${content_length}'+
	'\r\n\r\n').substitute
template200  = Template(template_normal %(200, 'OK', 'Eurasia3 Default Page', '''\
	<h1>It works!</h1>''')).substitute
template403 = Template(template_normal %(403, 'Forbidden', '403 Forbidden', '''\
	<h1>Forbidden</h1>
	<p>You don\'t have permission to list the contents of ${path} on this server.</p>''')).substitute
template404 = Template(template_normal %(404, 'Not Found', '404 Not Found', '''\
	<h1>Not Found</h1>
	<p>The requested URL ${path} was not found on this server.</p>''')).substitute
template500 = Template(template_normal %(500, 'Internal Server Error', '500 Internal Server Error', '''\
	<h1>Internal Server Error</h1>
	<p>The server encountered an internal error and was unable to complete your request.</p>''')).substitute
template300u = Template('This resource can be found at <a href="${url}">${url}</a>.').substitute
template300b  = Template(template_redirect %(300, 'Multiple Choices', 'Object has several resources', '''\
	<h1>Object has several resources -- see URI list</h1>
	<p>${locations}</p>''')).substitute
template301u = Template('This resource has permanently moved to <a href="${url}">${url}</a>.').substitute
template301b = Template(template_redirect %(301, 'Moved Permanently', 'Object moved permanently', '''\
	<h1>Object moved permanently -- see URI list</h1>
	<p>${locations}</p>''')).substitute
template302u = Template('This resource resides temporarily at <a href="${url}">${url}</a>.').substitute
template302b = Template(template_redirect %(302, 'Found', 'Object moved temporarily', '''\
	<h1>Object moved temporarily -- see URI list</h1>
	<p>${locations}</p>''')).substitute
template303u = Template('This resource can be found at <a href="${url}">${url}</a>.').substitute
template303b = Template(template_redirect %(303, 'See Other', 'Object moved', '''\
	<h1>Object moved -- see Method and URL list</h1>
	<p>${locations}</p>''')).substitute
template307u = Template('This resource has moved temporarily to <a href="${url}">${url}</a>.').substitute
template307b = Template(template_redirect %(307, 'Temporary Redirect', 'Object moved temporarily', '''\
	<h1>Object moved temporarily -- see URI list</h1>
	<p>${locations}</p>''')).substitute
template304 = Template('${version} 304 Not Modified\r\n\r\n').substitute
template305 = Template('${version} 305 Use Proxy\r\nLocation: ${location}\r\n\r\n').substitute
