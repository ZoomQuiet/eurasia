__version__ = '3.0.0'

def patch():
	try:
		from py.magic import greenlet
	except ImportError:
		pass
	else:
		class GWrap(greenlet):
			def raise_exception(self, e):
				self.throw(e)

		__import__('stackless').GWrap = GWrap

	try:
		from select import poll
	except ImportError:
		select2poll()
	else:
		stacklessfile()

	import sys, web, request, response, routing, utility
	for m, l in ((routing, ('config', )), (request, ('Form', 'SimpleUpload')),
		(response, ('Comet', 'Response'))):

		for i in l:
			setattr(web, i, getattr(m, i))

	def multicoop(cpus=True):
		if isinstance(cpus, bool):
			cpus = utility.cpu_count() if cpus else 1

		if cpus < 2:
			routing.install()
			web.mainloop0()
			return

		try:
			from os import fork
		except ImportError:
			routing.install()
			web.mainloop0()
			return

		routing.install()
		for i in '\x00' * (cpus - 1):
			if fork() == 0:
				web.mainloop0()
				sys.exit()

		web.mainloop0()

	web.mainloop0, web.mainloop = web.mainloop, multicoop

	glob = globals()
	del glob['patch'], glob['select2poll'], glob['stacklessfile'], glob

def stacklessfile():
	import os.path
	filename = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'web.py')
	if not os.path.exists(filename):
		return

	classcode = ''.join(
		i[1:] if i[:1] == '\t' else i for i in open(filename).readlines()[21:327]).replace(
		'self.socket.recv('  , 'fread(self.pid, ' ).replace(
		'self.socket.send('  , 'fwrite(self.pid, ').replace(
		'self.socket.close()', 'file.close(self)' )

	import web, cherrypy
	from web import socket_map
	from fcntl import fcntl, F_SETFL
	from stackless import channel, getcurrent
	from os import read as fread, write as fwrite, O_NONBLOCK
	class File(file):
		def __init__(self, filename, *args):
			file.__init__(self, filename, *args)
			self.pid = self.fileno()
			if fcntl(self.pid, F_SETFL, O_NONBLOCK) != 0:
				raise OSError('fcntl(%d, F_SETFL, O_NONBLOCK)' %self.pid)

			self.address = filename
			self.tasklet = getcurrent()
			self._rbuf = self._wbuf = ''
			self.read_channel = channel()
			self.write_channel = channel()
			socket_map[self.pid] = self

		exec classcode in web.__dict__

	cherrypy.open = web.File = web.FileClient = File

def select2poll():
	from select import select
	def poll(timeout):
		a, b, c = select(r.keys(), w.keys(), e.keys(), 0.0001)
		return [(i, R) for i in a] + [(i, W) for i in b] + [(i, E) for i in c]

	def register(pid, flag):
		if flag & R:
			e[pid] = r[pid] = None
			if flag & W:
				w[pid] = None
			else:
				try:
					del w[pid]
				except KeyError:
					pass
		elif flag & W:
			e[pid] = w[pid] = None
			try:
				del r[pid]
			except KeyError:
				pass
		elif flag & E:
			e[pid] = None
			try:
				del r[pid]
			except KeyError:
				pass
			try:
				del w[pid]
			except KeyError:
				pass

	def unregister(pid):
		try: del r[pid]
		except KeyError: pass
		try: del w[pid]
		except KeyError: pass
		try: del e[pid]
		except KeyError: pass

	r, w, e = {}, {}, {}
	POLLIN, POLLPRI, POLLOUT, POLLERR, POLLHUP, POLLNVAL = 1, 2, 4, 8, 16, 32
	R, W, E = POLLIN | POLLPRI, POLLOUT, POLLERR | POLLHUP | POLLNVAL

	import select as module
	module.poll = lambda: type('Poll', (), { 'poll': staticmethod(poll),
			'register'  : staticmethod(register  ),
			'unregister': staticmethod(unregister)})

	for i in ('POLLIN', 'POLLOUT', 'POLLERR', 'POLLPRI', 'POLLHUP', 'POLLNVAL'):
		exec 'module.%s = %s' %(i, i) in locals()

patch()
import web, modules
