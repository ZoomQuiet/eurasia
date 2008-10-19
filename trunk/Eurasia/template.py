import re
from string import Template as _Template

def Template(text, env={}):
	code = compile(text)
	module = Module('<template>')
	module.__dict__.update(env)
	exec code in module.__dict__
	return module

def compile(text):
	self = Instance(text=text, strc=0, strl=[])
	try:
		tr = list(lines(self, False))
	except error, e:
		e.line = len(text.split('\n')) - len(self.text.split('\n')) + 1
		raise e

	code = [code_main0(strl='\n'.join(self.strl))]
	_compile(code, 0, tr)
	code.append(code_main1)
	return '\n'.join(code)

def _compile(code, base, tr):
	for i in tr:
		if isinstance(i, basestring) and base > 0:
			code.append('%s____w(%s)' %(base*'\t', i))

		elif isinstance(i, Var) and base > 0:
			tabs = base*'\t'
			code.append('%s____w(%s)' %(tabs, i.data))

		elif isinstance(i, If):
			code.append('%sif %s:' %(base*'\t', i.args))
			_compile(code, base + 1, i.data)

		elif isinstance(i, For):
			code.append('%sfor %s:' %(base*'\t', i.args))
			_compile(code, base + 1, i.data)

		elif isinstance(i, Elif):
			code.append('%selif %s:' %(base*'\t', i.args))
			_compile(code, base + 1, i.data)

		elif isinstance(i, Else):
			code.append(base*'\t' + 'else:')
			_compile(code, base + 1, i.data)

		elif isinstance(i, Py):
			tabs = base*'\t'
			code.append('\n'.join(tabs + j for j in i.data))

		elif isinstance(i, Def):
			tabs = base*'\t'
			code.append(code_func0(t=tabs, name=i.name, args=i.args))
			_compile(code, base + 1, i.data)
			code.append(code_func1(t=tabs, name=i.name))

		elif isinstance(i, Call) and base > 0:
			tabs = base*'\t'
			code.append(code_call0(t=tabs, name=i.name))
			_compile(code, base + 1, i.data)
			code.append(code_call1(t=tabs, name=i.name, args=i.args))

def lines(self, level=0):
	buff = []
	while True:
		lst = split(self.text, 1)
		try:
			s, esc, var, cmd, sta, stags, eta, code, self.text = lst

		except ValueError:
			buff.append(lst[0])
			break

		buff.append(s)
		if esc is not None:
			buff.append(esc[0])

		elif cmd is not None:
			try:
				m1, args, m2, m3 = match_cmd(cmd).groups()

			except AttributeError:
				continue

			if buff:
				if level > 0:
					s = ''.join(buff)
					if s:
						self.strl.append('____s%d = %r' %(self.strc, s))
						yield '____s%d' %self.strc
						self.strc += 1
				buff = []

			if m1:
				m1, args = m1.lower(), args.strip()
				if m1 == 'if':
					currtype = If
					while True:
						data = []
						try:
							for i in lines(self, level):
								data.append(i)

							raise NotClosed('%if: ... [!]%endif')

						except EndOfIf:
							yield currtype(args=args, data=data)
							break

						except BeginOfElif, e:
							yield currtype(args=args, data=data)
							currtype, args = Elif, e.args[1]

						except BeginOfElse:
							yield currtype(args=args, data=data)
							data = []
							while True:
								try:
									for i in lines(self, level):
										data.append(i)

									raise NotClosed('%if: ... %else: ... [!]%endif')

								except EndOfIf:
									yield Else(data=data)
									break

								except fatalerrors:
									raise

								except error:
									raise NotClosed('%if: ... %else: ... [!]%endif')
							break

						except fatalerrors:
							raise

						except error:
							raise NotClosed('%if: ... [!]%endif')

				elif m1 == 'for':
					data = []
					try:
						for i in lines(self, level):
							data.append(i)

						raise NotClosed('%for: ... [!]%endfor')

					except EndOfFor:
						yield For(args=args, data=data)

					except fatalerrors:
						raise

					except error:
						raise NotClosed('%for: ... [!]%endfor')

				elif m1 == 'elif':
					raise BeginOfElif('%if[!] ... %elif:', args)

			elif m2 is not None and m2.lower() == 'else':
				raise BeginOfElse('%if[!] ... %else:')

			elif m3 is not None:
				m3 = m3.strip()
				if m3 == 'endif':
					raise EndOfIf('%if[!] ... %endif')

				elif m3 == 'endfor':
					raise EndOfFor('%for[!] ... %endfor')
			continue

		if buff:
			if level > 0:
				s = ''.join(buff)
				if s:
					self.strl.append('____s%d = %r' %(self.strc, s))
					yield '____s%d' %self.strc
					self.strc += 1

			buff = []

		if var is not None and level > 0:
			yield Var(data=var)

		elif code is not None:
			n, data, l = None, [], code.split('\n')
			space, start = match_space(l[0]).groups()
			if start:
				raise IndentationError('<%% [X]%s ...' %start.strip())

			data.append(l[0][len(space):])
			for j in l[1:]:
				if not j.strip():
					continue

				if n is None:
					space, s = match_space(j).groups()
					t = len(space)
					if s:
						n = t

					data.append(j[t:])
					continue

				if j[:n] != space:
					raise IndentationError(j)

				data.append(j[n:])

			yield Py(data=data)

		elif sta is not None:
			sta, stags = sta.lower(), stags.strip()
			if sta == 'def':
				data = []
				try:
					for i in lines(self, level+1):
						data.append(i)

					raise NotClosed('<%def> ... [!]</%def>')

				except EndOfDef:
					m = match_drags(stags)
					if m:
						stags = eval(m.groups()[0])

					try:
						name, args = match_frags(stags).groups()
					except AttributeError:
						raise SyntaxError(stags)

					yield Def(name=name, args=args.strip(), data=data)

				except fatalerrors:
					raise

				except error:
					raise NotClosed('<%def> ... [!]</%def>')

			elif sta == 'call' and level > 0:
				data = []
				try:
					for i in lines(self, level+1):
						data.append(i)

					raise NotClosed('<%call> ... [!]</%call>')

				except EndOfCall:
					m = match_crags(stags)
					if m:
						stags = eval(m.groups()[0])

					try:
						name, args = match_frags(stags).groups()
					except AttributeError:
						raise SyntaxError(stags)

					yield Call(name=name, args=args.strip(), data=data)

				except fatalerrors:
					raise

				except error, e:
					raise NotClosed('<%call> ... [!]</%call>')

		elif eta is not None:
			eta = eta.lower()
			if eta == 'def':
				raise EndOfDef('? ... </def>')

			elif eta == 'call' and level > 0:
				raise EndOfCall('? ... </call>')

	if buff and level > 0:
		s = ''.join(buff)
		if s:
			self.strl.append('____s%d = %r' %(self.strc, s))
			yield '____s%d' %self.strc
			self.strc += 1

Module = type(re)

class error(Exception):
	def __str__(self):
		return '%s, line %d' %(self.args[0], self.line)
class Instance:
	def __init__(self, **args):
		self.__dict__.update(args)

for cls in ('EndOfIf', 'EndOfDef', 'EndOfFor', 'EndOfCall', 'NotClosed',
	'BeginOfElif', 'BeginOfElse', 'SyntaxError', 'IndentationError'):

	exec 'class %s(error): pass' %cls

fatalerrors = (NotClosed, SyntaxError, IndentationError)

for cls in ('If', 'Def', 'For', 'Py', 'Var', 'Elif', 'Else', 'Call'):
	exec 'class %s(Instance): pass' %cls

code_main0 = _Template('''\
from sys import _getframe
from StringIO import StringIO
${strl}
''').substitute

code_main1 = '''\
def ____getcall(func):
	func = func.__class__()
	func.context = _getframe(1).f_locals
	func.caller  = ____getcaller(func.context)
	return func

class ____getcaller(object):
	def __init__(self, environ):
		self.__environ = environ

	def __getattr__(self, name):
		try:
			return self.__environ[name]
		except KeyError:
			raise AttributeError(name)

	def has_key(self, key):
		return self.__environ[key]\
'''

code_func0 = _Template('''\
${t}def _____${name}(self, ${args}):
${t}	if hasattr(self, 'caller'):
${t}		caller  = self.caller
${t}		context = self.context

${t}	out = StringIO()
${t}	____getvalue = out.getvalue
${t}	____w = puts = write = out.write\
''').substitute

code_func1 = _Template('''\

${t}	return ____getvalue()
${t}${name} = type('${name}', (), dict(__call__=_____${name}))()
''').substitute

code_call0 = _Template('''\
${t}def ____call_${name}():\
''').substitute

code_call1 = _Template('''\

${t}	____w(____getcall(${name})(${args}))
${t}____call_${name}()\
''').substitute

ignstr = r'(?:"(?:(?:\\\\)?(?:\\")?[^"]?)*")?'+r"(?:'(?:(?:\\\\)?(?:\\')?[^']?)*')?"

match_drags = re.compile(r'(?:name\s*=\s*)?(%s)' %ignstr).match
match_crags = re.compile(r'(?:expr\s*=\s*)?(%s)' %ignstr).match
match_frags = re.compile(r'([a-zA-Z][a-zA-Z0-9_]*)\s*\((.*)\)').match
match_space = re.compile(r'^(\s*)(def\s|class\s|if\s|try\s*:|for\s|while\s)?.*$').match

split = re.compile('|'.join((
	r'(\$\$|%%)',
	r'\${(%s)}' %(r'(?:%s[^}]?)*' %ignstr),
	r'\n?\s*%(.*)(?:\n|$)',
	r'\n?\s*<%%(def|call)\s+(%s)>' %(r'(?:%s[^>]?)*' %ignstr),
	r'\n?\s*<\s*/\s*%(def|call)>',
	r'\n?\s*<%%%s%%>\n?' %(r'((?:%s[^%%]?(?:%%(?!>))?)*)' %ignstr

	))), re.I | re.M).split

match_cmd = re.compile('|'.join((
	r'^([a-zA-Z][a-zA-Z0-9]*)\s+((?:%s[^#]?)*):(?:\s*#.*)?$' %ignstr,
	r'^([a-zA-Z][a-zA-Z0-9]*)\s*:(?:\s*#.*)?$',
	r'^([a-zA-Z][a-zA-Z0-9]*)\s*(?:#.*)?$' ))).match
