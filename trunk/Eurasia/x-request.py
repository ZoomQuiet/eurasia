from Eurasia import OverLimit
from urllib import unquote_plus

def Form(client, max_size=1048576):
	if client.method == 'POST':
		length = client['Content-Length']
		if int(length) > max_size:
			client.close()
			raise Overlimit

		data = client.read(length)
	else:
		data = ''

	p = client.path.find('?')
	if p != -1:
		data = '%s&%s' %(client.path[p+1:], data)

	d = {}
	for item in data.split('&'):
		try:
			key, value = item.split('=', 1)
			value = unquote_plus(value)
			try:
				if isinstance(d[key], list):
					d[key].append(value)
				else:
					d[key] = [d[key], value]
			except KeyError:
				d[key] = value
		except ValueError:
			continue
	return d

def SimpleUpload(client):
	global next, last
	try:
		next = '--' + parse_header(client['Content-Type'])[1]['boundary']
	except:
		raise IOError

	last = next + '--'
	def _preadline():
		l = client.readline(65536)
		if not l:
			raise IOError

		if l[:2] == '--':
			sl = l.strip()
			if sl == next or sl == last:
				raise IOError

		el = l[-2:] == '\r\n' and '\r\n' or (l[-1] == '\n' and '\n' or '')

		while True:
			l2 = client.readline(65536)
			if not l2:
				raise IOError

			if l2[:2] == '--' and el:
				sl = l2.strip()
				if sl == next or sl == last:
					yield l[:-len(el)]
					break
			yield l
			l = l2
			el = l[-2:] == '\r\n' and '\r\n' or (l[-1] == '\n' and '\n' or '')

		while True:
			yield None
	class CGIFile:
		def __getitem__(self, k):
			return self.form[k]

	def _fp():
		rl = _preadline().next
		_fp.buff = ''

		def _read(size=None):
			buff = _fp.buff
			if size:
				while len(buff) < size:
					l = rl()
					if not l:
						_fp.buff = ''
						return buff
					buff += l

				_fp.buff = buff[size:]
				return buff[:size]

			d = [buff]; _fp.buff = ''
			while True:
				l = rl()
				if not l:
					return ''.join(d)

				d.append(l)

		def _readline(size=None):
			s = _fp.buff
			if size:
				nl = s.find('\n', 0, size)
				if nl >= 0:
					nl += 1
					_fp.buff = s[nl:]
					return s[:nl]

				elif len(s) > size:
					_fp.buff = s[size:]
					return s[:size]

				t = rl()
				if not t:
					_fp.buff = ''
					return s

				s = s + t
				if len(s) > size:
					_fp.buff = s[size:]
					return s[:size]

				_fp.buff = ''
				return s
			else:
				nl = s.find('\n')
				if nl >= 0:
					nl += 1
					_fp.buff = s[nl:]
					return s[:nl]

				else:
					t = rl()
					_fp.buff = ''
					if not t:
						return s
					s += t
					return s
		fp = CGIFile()
		fp.read = _read
		fp.readline = _readline
		return fp

	c = 0
	while True:
		l = client.readline(65536)
		c += len(l)
		if not l:
			raise IOError

		if l[:2] == '--':
			sl = l.strip()
			if sl == next:
				c1 = (l[-2:] == '\r\n' and 2 or 1) << 1
				cnext = c1 + len(next)
				break

			if sl == last:
				raise IOError

	filename = None
	d = {}
	while True:
		name = None
		for i in xrange(10):
			l = client.readline(65536)
			c += len(l)
			l = l.strip()
			if not l:
				if not name:
					raise IOError

				if filename:
					fp = _fp()
					fp.filename = filename
					fp.form = d
					try:
						size = int(client['Content-Length'])
					except:
						return fp

					fp.size = size - c - c1 - len(last)
					return fp

				s = _fp().read()
				c += cnext + len(s)
				try: d[name].append(s)
				except KeyError: d[name] = s
				except AttributeError: d[name] = [d[name], s]
				break

			t1, t2 = l.split(':', 1)
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
