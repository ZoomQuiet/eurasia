import re, sys
from string import Template as _Template

def Template(text, env={}):
	code = compile(text)
	module = Module('<string>')
	module.__dict__.update(env)
	exec code in module.__dict__
	return module

def compile(text):
	self = Instance(text=text, stack=[], scount=0, scode=[])
	try:
		tr = list(lines(self, False))
	except error, e:
		e.line = len(text.split('\n')) - len(self.text.split('\n')) + 1
		raise e

	code = [code_main0(scode='\n'.join(self.scode))]
	_compile(code, 0, tr, False)
	code.append(code_main1)
	return '\n'.join(code)

def _compile(code, base, tr, ntop=True):
	for i in tr:
		if isinstance(i, basestring) and ntop: # "..." NOT ON TOP LEVEL (ntop)
			code.append('%s____w(%s)' %(base*'\t', i))

		elif isinstance(i, Var) and ntop: # ${...} NOT ON TOP LEVEL (ntop)
			tabs = base*'\t'
			code.append('%s____w(%s)' %(tabs, i.data))

		elif isinstance(i, (If, Elif, For)): # %if/%elif/%for
			code.append('%s%s' %(base*'\t', i.args))
			_compile(code, base + 1, i.data)

		elif isinstance(i, Else):
			code.append(base*'\t' + 'else:')
			_compile(code, base + 1, i.data)

		elif isinstance(i, Src): # <% ... %>
			tabs = base*'\t'
			code.append('\n'.join(tabs + j for j in i.data))

		elif isinstance(i, Def):
			dummy, name, args = cml(i.name).groups()
			tabs = base*'\t'
			code.append(code_func0(t=tabs, name=name, args=args))
			_compile(code, base + 1, i.data)

			code.append(code_func1(t=tabs, name=name))

		elif isinstance(i, Call) and ntop: # %call NOT ON TOP LEVEL (ntop)
			dummy, name, args = cml(i.expr).groups()
			tabs = base*'\t'
			code.append(code_call0(t=tabs, name=name))
			_compile(code, base + 1, i.data)

			code.append(code_call1(t=tabs, name=name, args=args))

def lines(self, ntop=True):
	buff = []
	while True:
		lst = split(self.text, 1)
		try:
			t, m0, m1, m2, m3, m4, m5, m6, m7, self.text = lst

		except ValueError:
			buff.append(lst[0])
			break

		buff.append(t)
		if m0 is not None: # $$ -> $
			buff.append('$')
			continue

		elif m3 is not None: # %% -> %
			buff.append('%')
			continue

		elif m4 is not None: # %if/%elif/%for
			try:
				args, a, b, c = cmd(m4).groups()
			except AttributeError:
				continue
			else:
				if buff:
					if ntop:
						s = ''.join(buff)
						if s:
							self.scode.append('____s%d = %r' %(self.scount, s))
							yield '____s%d' %self.scount
							self.scount += 1

					buff = []
				if a == 'if':
					currtype = If
					while True:
						data = []
						try:
							for i in lines(self):
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
									for i in lines(self):
										data.append(i)

									raise NotClosed('%if: ... %else: ... [!]%endif')

								except EndOfIf:
									yield Else(data=data)
							break

				elif a == 'for':
					data = []
					try:
						for i in lines(self):
							data.append(i)

						raise NotClosed('%for: ... [!]%endfor')
					except EndOfFor:
						yield For(args=args, data=data)

				elif a == 'elif':
					raise BeginOfElif('%if[!] ... %elif:', args)

				elif b == 'else':
					raise BeginOfElse('%if[!] ... %else:')

				elif c == 'endif':
					raise EndOfIf('%if[!] ... %endif')

				elif c == 'endfor':
					raise EndOfFor('%for[!] ... %endfor')

				continue
		if buff:
			if ntop:
				s = ''.join(buff)
				if s:
					self.scode.append('____s%d = %r' %(self.scount, s))
					yield '____s%d' %self.scount
					self.scount += 1

			buff = []

		if m1 is not None: # ${...}
			yield Var(data=m1)

		elif m2 is not None: # <% ... %>
			try:
				code, dummy, self.text = eop(self.text, 1)
			except ValueError:
				raise NotClosed('<% ... [!]%>')

			n, data, l = None, [], code.split('\n')
			space, s = spc(l[0]).groups()
			if s:
				raise IndentationError('<%% [X]%s' %s)

			data.append(l[0][len(space):])
			for j in l[1:]:
				if not j.strip():
					continue

				if n is None:
					space, s = spc(j).groups()
					t = len(space)
					if s:
						n = t

					data.append(j[t:])
					continue

				if j[:n] != space:
					raise IndentationError(j)

				data.append(j[n:])

			yield Src(data=data)

		elif m5 is not None: # <def name=...>
			data = []
			try:
				for i in lines(self):
					data.append(i)

				raise NotClosed('<def> ... [!]</def>')

			except EndOfDef:
				yield Def(name=m5, data=data)

		elif m6 is not None: # <call expr=...>
			data = []
			try:
				for i in lines(self):
					data.append(i)

				raise NotClosed('<call> ... [!]</call>')

			except EndOfCall:
				yield Call(expr=m6, data=data)

		elif m7 is not None: # </def> / </call>
			if m7 == 'def' :
				raise EndOfDef('? ... </def>')

			elif m7 == 'call':
				raise EndOfCall('? ... </call>')

	if buff and ntop:
		s = ''.join(buff)
		if s:
			self.scode.append('____s%d = %r' %(self.scount, s))
			yield '____s%d' %self.scount
			self.scount += 1

Module = type(sys)

code_main0 = _Template('''\
from sys import _getframe
from cStringIO import StringIO
${scode}
''').substitute

code_main1 = '''\
class ____Caller(object):
	def __init__(self):
		self.__locals = _getframe(1).f_locals

	def __getattr__(self, name):
		try:
			return self.__locals[name]
		except KeyError:
			raise AttributeError(name)
'''

code_func0 = _Template('''\
${t}def _____${name}(self, ${args}):
${t}	if hasattr(self, 'caller'):
${t}		caller = self.caller

${t}	out = StringIO()
${t}	____getvalue = out.getvalue
${t}	____w = puts = write = out.write\
''').substitute

code_func1 = _Template('''\

${t}	return ____getvalue()
${t}${name} = type('${name}', (), dict(__call__=_____${name}))()
''').substitute

code_call0 = _Template('''\
${t}def ____call_${name}(____w):\
''').substitute

code_call1 = _Template('''\
${t}	____cp_${name} = ${name}.__class__()
${t}	____cp_${name}.caller = ____Caller()

${t}	____w(____cp_${name}(${args}))
${t}____call_${name}(____w)
''').substitute

class error(Exception):
	def __str__(self):
		return '%s, line %d' %(self.args[0], self.line)
class Instance:
	def __init__(self, **args):
		self.__dict__.update(args)

for cls in ('EndOfIf', 'EndOfDef', 'EndOfFor', 'EndOfCall',
	'NotClosed', 'BeginOfElif', 'BeginOfElse', 'IndentationError'):

	exec 'class %s(error): pass' %cls

for cls in ('If', 'Def', 'For', 'Src', 'Var', 'Elif', 'Else', 'Call'):
	exec 'class %s(Instance): pass' %cls

split = re.compile('|'.join((
	r'(\$\$)', #0 # $$ -> $
	r'\${[\s\t]*([^}]*)[\s\t]*}', #1 # ${...}
	r'(<%)', #2 # <% ...
	r'(%%)', #3 # %% -> %
	r'%(.*)[\s\t]*$', #4 # %cmd
	r'(?:<[\s\t]*def[\s\t]+name[\s\t]*=[\s\t]*([^>]+)[\s\t]*>)', #5 # <def name=...>
	r'(?:<[\s\t]*call[\s\t]+expr[\s\t]*=[\s\t]*([^>]+)[\s\t]*>)', #6 # <call expr=...>
	r'(?:<[\s\t]*/[\s\t]*(def|call)[\s\t]*>)' #7 # <def>/<call>
	)), re.I | re.M).split

eop = re.compile(r'(%>)', re.I | re.M).split
cml = re.compile(r'(\'|\")[\s\t]*([^(\s\t]+)[\s\t]*\((.*)\)[\s\t]*\1').match
spc = re.compile(r'^([\s\t]*)(?:(def[\s\t]|class[\s\t]|if[\s\t]|try[\s\t]*:|for[\s\t]|while[\s\t])?.*)$').match
cmd = re.compile('|'.join((
	r'(^(if|elif|for)[\s\t]+.*:(?:[\s\t]*#.*)?$)',
	r'(?:^(else)[\s\t]*:$)',
	r'(?:(endif|endfor)(?:[\s\t]*#.*)?)'))).match
