try:
	from select import poll
except ImportError:
	from select import select
	def poll(timeout):
		a, b, c = select(r.keys(), w.keys(), e.keys(), 0.0001)
		return [(i, R) for i in a] + [(i, W) for i in b] + [(i, E) for i in c]

	def register(pid, flag):
		if flag & R:
			e[pid] = r[pid] = None
			if flag & W: w[pid] = None
			else:
				try: del w[pid]
				except KeyError: pass
		elif flag & W:
			e[pid] = w[pid] = None
			try: del r[pid]
			except KeyError: pass

		elif flag & E:
			e[pid] = None
			try: del r[pid]
			except KeyError: pass
			try: del w[pid]
			except KeyError: pass

	def unregister(pid):
		try: del r[pid]
		except KeyError: pass
		try: del w[pid]
		except KeyError: pass
		try: del e[pid]
		except KeyError: pass

	r, w, e = {}, {}, {}
	POLLIN, POLLPRI, POLLOUT = 1, 2, 4
	POLLERR, POLLHUP, POLLNVAL = 8, 16, 32
	R = POLLIN | POLLPRI; W = POLLOUT
	E = POLLERR | POLLHUP | POLLNVAL

	patch = __import__('select')
	patch.poll = lambda: type('Poll', (), {
			'poll'      : staticmethod(poll      ),
			'register'  : staticmethod(register  ),
			'unregister': staticmethod(unregister) } )

	patch.POLLIN   = POLLIN ; patch.POLLOUT  = POLLOUT
	patch.POLLERR  = POLLERR; patch.POLLPRI  = POLLPRI
	patch.POLLHUP  = POLLHUP; patch.POLLNVAL = POLLNVAL

class OverLimit(IOError): pass
class Disconnect(IOError): pass
