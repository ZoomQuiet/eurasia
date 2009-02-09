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

	import sys
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
			routing.install(web)
			web.mainloop0()
			return

		routing.install(web)
		for i in '\x00' * (cpus - 1):
			if fork() == 0:
				web.mainloop0()
				sys.exit()

		web.mainloop0()

	import routing
	web.mainloop0, web.mainloop, web.routing = web.mainloop, multicoop, routing.config

	glob = globals()
	del glob['patch'], glob['select2poll'], glob

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

import web, modules
patch()
