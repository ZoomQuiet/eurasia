from os import urandom
from Queue import Queue
from os.path import abspath
from random import randrange
from cPickle import dumps, loads
from sys import _getframe, modules
from exceptions import BaseException
from stackless import channel, schedule
from _weakref import proxy, ref as weakref
from copy import deepcopy, error as CopyError
from thread import allocate_lock, start_new_thread
try:
	from gdbm import open as dbm
except ImportError:
	from shelve import open as dbm

def open(filename, pool=None):
	pool = get_global_threadpool() if pool is None else pool

	e = channel()
	pool.queue.put((e, BTreeBaseConnectionWrapper, (filename, pool), {}))
	errno, e = e.receive()
	if errno == 0:
		return e

	raise e

class Pool:
	def __init__(self, n=16):
		self.queue = Queue()
		for i in xrange(n):
			start_new_thread(self.pipe, ())

	def __call__(self, func):
		def wrapper(*args, **kw):
			e = channel()
			self.queue.put((e, func, args, kw))
			errno, e = e.receive()
			if errno == 0:
				return e

			raise e

		return wrapper

	def pipe(self):
		while True:
			rst, func, args, kw = self.queue.get()
			try:
				result = func(*args, **kw)
			except BaseException, e:
				rst.send((-1, e))
			else:
				rst.send((0, result))

class Base(object):
	@property
	def _p_ldata(self):
		try:
			return self.__dict__['_p_data']
		except KeyError:
			self.__dict__['_p_data'] = self._p_conn[self._p_key]
			return self._p_data

	def __getstate__(self):
		attrs = self.__dict__
		try:
			return attrs['_p_key']
		except KeyError:
			conn = _getframe(1).f_locals['self']
			attrs['_p_key' ] = conn << self
			attrs['_p_conn'] = proxy(conn)
			return attrs['_p_key']

	def __setstate__(self, key):
		attrs = self.__dict__
		attrs['_p_key'] = key
		attrs['_p_conn'] = proxy(_getframe(1).f_locals['self'])
		del attrs['_p_data']

	def __deepcopy__(self, memo):
		if '__del__' not in memo:
			raise CopyError('uncopyable object')

		attrs = self.__dict__
		try:
			key = attrs['_p_key']
		except KeyError:
			return 0

		try:
			if self._p_conn.closed:
				return 0

			deepcopy(self._p_ldata, {'__del__': 0})
			del self._p_conn[key]

		except ReferenceError:
			pass

		return 0

	def _p_note_change(self):
		try:
			key = self.__dict__['_p_key']
		except KeyError:
			pass
		else:
			self._p_conn[key] = self

class Persistent(Base):
	def __new__(klass, *args, **kw):
		o = __new__(klass)
		o.__dict__['_p_data'] = {}
		return o

	def __getattr__(self, name):
		try:
			return self._p_ldata[name]

		except KeyError:
			raise AttributeError(name)

	def __setattr__(self, name, value):
		if name[:3] == '_p_':
			self.__dict__[name] = value
			return

		self._p_ldata[name] = value
		self._p_note_change()

	def __delattr__(self, name):
		if name[:3] == '_p_':
			try:
				del self.__dict__[name]
			except KeyError:
				raise AttributeError(name)
			else:
				return

		try:
			o = self._p_ldata[name]
		except KeyError:
			raise AttributeError(name)

		deepcopy(o, {'__del__': 0})
		del self._p_ldata[name]
		self._p_note_change()

	def __getnewargs__(self):
		return ()

class BNode(Base):
	@property
	def min_item(self):
		if not self._p_ldata[1]:
			return self._p_data[0][0]
		else:
			return self._p_data[1][0].min_item

	@property
	def max_item(self):
		if not self._p_ldata[1]:
			return self._p_data[0][-1]
		else:
			return self._p_data[1][-1].max_item

	def __init__(self, key=None, conn=None):
		if key:
			self._p_key, self._p_conn = key, conn
		else:
			self._p_data = [[], None]

	def __setstate__(self, key):
		self._p_key  = key
		self._p_conn = proxy(_getframe(1).f_locals['self'])

	def __len__(self):
		result = len(self._p_ldata[0])
		for node in self._p_data[1] or []:
			result += len(node)

		return result

	def __delitem__(self, key):
		p = self.get_position(key)
		matches = p < len(self._p_ldata[0]) and self._p_data[0][p][0] == key
		if not self._p_data[1]:
			if matches:
				del self._p_data[0][p]
				self._p_note_change()
			else:
				raise KeyError(key)
		else:
			node = self._p_data[1][p]
			lower_sibling = p > 0 and self._p_data[1][p - 1]
			upper_sibling = p < len(self._p_data[1]) - 1 and self._p_data[1][p + 1]
			if matches:
				if node and len(node._p_ldata[0]) >= minimum_degree:
					extreme = node.max_item
					del node[extreme[0]]
					self._p_data[0][p] = extreme

				elif upper_sibling and len(upper_sibling._p_ldata[0]
					) >= minimum_degree:
					extreme = upper_sibling.min_item
					del upper_sibling[extreme[0]]
					self._p_data[0][p] = extreme
				else:
					extreme = upper_sibling.min_item
					del upper_sibling[extreme[0]]
					node._p_data[0] = node._p_ldata[0] + [extreme
						] + upper_sibling._p_ldata[0]
					if node._p_data[1]:
						node._p_data[1] = node._p_data[1] + upper_sibling._p_data[1]

					del self._p_data[0][p]
					del self._p_data[1][p + 1]

				self._p_note_change()
			else:
				if not (node and len(node._p_ldata[0]) >= minimum_degree):
					if lower_sibling and len(lower_sibling._p_ldata[0]
						) >= minimum_degree:

						node._p_data[0].insert(0, self._p_data[0][p - 1])
						self._p_data[0][p - 1] = lower_sibling._p_data[0][-1]
						del lower_sibling._p_data[0][-1]
						if node._p_data[1]:
							node._p_data[1].insert(0, lower_sibling._p_data[1][-1])
							del lower_sibling._p_data[1][-1]

						lower_sibling._p_note_change()

					elif upper_sibling and len(upper_sibling._p_ldata[0]
						) >= minimum_degree:

						node._p_data[0].append(self._p_data[0][p])
						self._p_data[0][p] = upper_sibling._p_data[0][0]
						del upper_sibling._p_data[0][0]
						if node._p_data[1]:
							node._p_data[1].append(upper_sibling._p_data[1][0])
							del upper_sibling._p_data[1][0]

						upper_sibling._p_note_change()

					elif lower_sibling:
						p1 = p - 1
						node._p_data[0] = (lower_sibling._p_ldata[0] + [self._p_data[0][p1]] +
							node._p_data[0])

						if node._p_data[1]:
							node._p_data[1] = lower_sibling._p_data[1] + node._p_data[1]

						del self._p_data[0][p1]
						del self._p_data[1][p1]
					else:
						node._p_data[0] = (node._p_data[0] + [self._p_data[0][p]] +
							upper_sibling._p_ldata[0])

						if node._p_data[1]:
							node._p_data[1] = node._p_data[1] + upper_sibling._p_data[1]

						del self._p_data[0][p]
						del self._p_data[1][p + 1]

					self._p_note_change()
					node._p_note_change()

					assert (node and len(node._p_data[0]) >= minimum_degree)

				del node[key]

			if not self._p_data[0]:
				o = self._p_data[1][0]
				self._p_data[0] = o._p_ldata[0]
				self._p_data[1] = o._p_data[1]

	def __iter__(self):
		if not self._p_ldata[1]:
			for item in self._p_data[0]:
				yield item
		else:
			for position, item in enumerate(self._p_data[0]):
				for it in self._p_data[1][position]:
					yield it

				yield item

			for it in self._p_data[1][-1]:
				yield it

	def __reversed__(self):
		if not self._p_ldata[1]:
			for item in reversed(self._p_data[0]):
				yield item
		else:
			for item in reversed(self._p_data[1][-1]):
				yield item

			for position in range(len(self._p_data[0]) - 1, -1, -1):
				yield self._p_data[0][position]
				for item in reversed(self._p_data[1][position]):
					yield item

	def iter_from(self, key):
		position = self.get_position(key)
		if not self._p_data[1]:
			for item in self._p_data[0][position:]:
				yield item
		else:
			for item in self._p_data[1][position].iter_from(key):
				yield item

			for p in range(position, len(self._p_data[0])):
				yield self._p_data[0][p]
				for item in self._p_data[1][p + 1]:
					yield item

	def iter_backward_from(self, key):
		position = self.get_position(key)
		if not self._p_data[1]:
			for item in reversed(self._p_data[0][:position]):
				yield item
		else:
			for item in self._p_data[1][position].iter_backward_from(key):
				yield item

			for p in range(position - 1, -1, -1):
				yield self._p_data[0][p]
				for item in reversed(self._p_data[1][p]):
					yield item

	def get_position(self, key):
		for position, item in enumerate(self._p_ldata[0]):
			if item[0] >= key:
				return position

		return len(self._p_data[0])

	def search(self, key):
		position = self.get_position(key)
		if position < len(self._p_data[0]) and self._p_data[0][position][0] == key:
			return self._p_data[0][position]
		elif not self._p_data[1]:
			return None
		else:
			return self._p_data[1][position].search(key)

	def insert_item(self, item):
		assert not len(self._p_ldata[0]) == 2 * minimum_degree - 1
		key = item[0]
		position = self.get_position(key)
		if position < len(self._p_data[0]) and self._p_data[0][position][0] == key:
			self._p_data[0][position] = item
			self._p_note_change()
		elif not self._p_data[1]:
			self._p_data[0].insert(position, item)
			self._p_note_change()
		else:
			child = self._p_data[1][position]
			if len(child._p_ldata[0]) == 2 * minimum_degree - 1:
				self.split_child(position, child)
				if key == self._p_data[0][position][0]:
					self._p_data[0][position] = item
					self._p_note_change()
				else:
					if key > self._p_data[0][position][0]:
						position += 1

					self._p_data[1][position].insert_item(item)
			else:
				self._p_data[1][position].insert_item(item)

	def split_child(self, position, child):
		assert len(self._p_ldata[0]) != 2 * minimum_degree - 1
		assert self._p_data[1]
		assert self._p_data[1][position] is child
		assert len(child._p_ldata[0]) == 2 * minimum_degree - 1
		bigger = BNode()
		middle = minimum_degree - 1
		splitting_key = child._p_data[0][middle]
		bigger._p_data[0] = child._p_data[0][middle + 1:]
		child._p_data[0] = child._p_data[0][:middle]
		assert len(bigger._p_data[0]) == len(child._p_data[0])
		if child._p_data[1]:
			bigger._p_data[1] = child._p_data[1][middle + 1:]
			child._p_data[1] = child._p_data[1][:middle + 1]
			assert len(bigger._p_data[1]) == len(child._p_data[1])

		self._p_data[0].insert(position, splitting_key)
		self._p_data[1].insert(position + 1, bigger)

		child._p_note_change()
		self._p_note_change()

class BTree(Base):
	@property
	def min_item(self):
		assert self._p_root._p_ldata[0], 'empty BTree has no min item'
		key, value = self._p_root.min_item
		return key, value

	@property
	def max_item(self):
		assert self._p_root._p_ldata[0], 'empty BTree has no max item'
		key, value = self._p_root.max_item
		return key, value

	@property
	def _p_key(self):
		return self._p_root._p_key

	@property
	def _p_conn(self):
		return self._p_root._p_conn

	@property
	def _p_data(self):
		return self._p_root._p_data

	def __new__(klass, *args, **kw):
		o = __new__(klass)
		o._p_root = BNode()
		return o

	def __deepcopy__(self, memo):
		if '__del__' not in memo:
			raise CopyError('uncopyable object')

		node = self._p_root
		try:
			key = node._p_key
		except AttributeError:
			return 0

		try:
			if node._p_conn.closed:
				return 0

			deepcopy(node._p_ldata, {'__del__': 0})
			del node._p_conn[key]

		except ReferenceError:
			pass

		return 0

	def __getstate__(self):
		node = self._p_root
		try:
			return node._p_key
		except AttributeError:
			conn = _getframe(1).f_locals['self']
			node._p_key = conn << node
			node._p_conn = proxy(conn)
			return node._p_key

	def __setstate__(self, key):
		self._p_pnt = proxy(_getframe(2).f_locals['self'])
		self._p_root = BNode(key, proxy(_getframe(1).f_locals['self']))

	def __repr__(self):
		return '{%s}' % ', '.join('%r: %r' % (key, value
			) for key, value in self.items())

	def __len__(self):
		return len(self._p_root)

	def __nonzero__(self):
		return bool(self._p_root._p_ldata[0])

	def __iter__(self):
		for item in self._p_root:
			yield item[0]

	def __reversed__(self):
		for item in reversed(self._p_root):
			yield item[0]

	def __contains__(self, key):
		return self._p_root.search(key) is not None

	def __getitem__(self, key):
		item = self._p_root.search(key)
		if item is None:
			raise KeyError(key)

		return item[1]

	def __setitem__(self, key, value=True):
		if len(self._p_root._p_ldata[0]) == 2 * minimum_degree - 1:
			node = BNode()
			node._p_data[1] = [self._p_root]
			node.split_child(0, node._p_data[1][0])
			self._p_root = node
			if hasattr(self, '_p_pnt'):
				self._p_pnt._p_note_change()

		self._p_root.insert_item((key, value))

	def __delitem__(self, key):
		item = self._p_root.search(key)
		if item is None:
			raise KeyError(key)

		del self._p_root[key]
		deepcopy(key , {'__del__': 0})
		deepcopy(item, {'__del__': 0})

	def has_key(self, key):
		return self._p_root.search(key) is not None

	def get(self, key, default=None):
		item = self._p_root.search(key)
		if item is None:
			return default

		return item[1]

	def setdefault(self, key, value):
		item = self._p_root.search(key)
		if item is None:
			self[key] = value
			return value

		return item[1]

	def update(self, *args, **kwargs):
		if args:
			if len(args) > 1:
				raise TypeError( (
					'update expected at most 1 argument, '
					'got %s') % len(args) )
			items = args[0]
			if hasattr(items, 'iteritems'):
				item_sequence = items.iteritems()
			else:
				item_sequence = items

			for key, value in item_sequence:
				self[key] = value

		for key, value in kwargs.iteritems():
			self[key] = value

	def clear(self):
		self._p_root = BNode()
		if hasattr(self, '_p_pnt'):
			self._p_pnt._p_note_change()

	def iterkeys(self):
		for item in self._p_root:
			yield item[0]

	def keys(self):
		return list(self.iterkeys())

	def itervalues(self):
		for item in self._p_root:
			yield item[1]

	def values(self):
		return list(self.itervalues())

	def items(self):
		return list(self.iteritems())

	def iteritems(self):
		for key, value in self._p_root:
			yield (key, value)

	def items_backward(self):
		for key, value in reversed(self._p_root):
			yield (key, value)

	def items_from(self, key, closed=True):
		for key2, value in self._p_root.iter_from(key):
			if closed or key2 != key:
				yield (key2, value)

	def items_backward_from(self, key, closed=False):
		if closed:
			item = self._p_root.search(key)
			if item is not None:
				yield (item[0], item[1])

		for key, value in self._p_root.iter_backward_from(key):
			yield (key, value)

	def items_range(self, start, end, closed_start=True, closed_end=False):
		if start <= end:
			for item in self.items_from(start, closed=closed_start):
				if item[0] > end:
					break

				if closed_end or item[0] < end:
					yield item
		else:
			for item in self.items_backward_from(start, closed=closed_start):
				if item[0] < end:
					break

				if closed_end or item[0] > end:
					yield item

class BTreeBaseConnectionWrapper(BTree):
	def __init__(self, filename, pool=None):
		self._p_conn_ref = Connection(filename, pool=pool)
		try:
			self._p_root_ref = self._p_conn_ref.load(id0)
		except KeyError:
			self._p_root_ref = BTree()
			self._p_conn_ref.dump(id0, self._p_root_ref)

		self._p_root = self._p_root_ref._p_root

	def __del__(self):
		pass

	def __getstate__(self):
		raise TypeError('can\'t pickle connection objects')

	def __setitem__(self, key, value=True):
		if len(self._p_root._p_ldata[0]) == 2 * minimum_degree - 1:
			node = BNode()
			node._p_data[1] = [self._p_root]
			node.split_child(0, node._p_data[1][0])
			self._p_root_ref._p_root = self._p_root = node
			self._p_conn_ref.note_change(id0)

		self._p_root.insert_item((key, value))

	def clear(self):
		self._p_root_ref._p_data = self._p_data = BNode()
		self._p_conn_ref.note_change(id0)

	def sync(self):
		return self._p_conn_ref.sync()

	def close(self):
		return self._p_conn_ref.close()

class Connection:
	def __init__(self, filename, pool=None):
		filename = abspath(filename)
		pool = get_global_threadpool() if pool is None else pool

		self.db, self.closed = dbm(filename, 'c'), False
		self.filename, self.queue, self.pool = filename, pool.queue, pool
		self.invalid, self.cache_invalid_lock = set(), allocate_lock()
		self.cache, self.changed, self.deleted, self.created = {}, {}, {}, []

		self.register_connection()

	def __del__(self):
		if hasattr(self, 'db'):
			e = channel()
			self.queue.put((e, self._close, (), {}))
			errno, e = e.receive()
			if errno != 0:
				raise e

	def __lshift__(self, o):
		oid = uuid4()
		while self.db.has_key(oid) or oid in self.created:
			oid = uuid4()

		self.db[oid] = dumps(o._p_data, 2)
		if oid in self.deleted:
			del self.deleted[oid]

		self.cache[oid] = o._p_data
		self.created.append(oid)
		return oid

	def __getitem__(self, key):
		if key in self.deleted:
			raise KeyError(key)

		try:
			return self.cache[key]
		except KeyError:
			pass

		while not self.cache_invalid_lock.acquire(0):
			schedule()
		try:
			if key in self.invalid:
				raise ReadConflictError(key)

			e = channel()
			self.queue.put((e, dbmget, (self.db, key), {}))
			errno, e = e.receive()
			if errno != 0:
				raise e

			o = loads(e)
			self.cache[key] = o
		finally:
			self.cache_invalid_lock.release()

		return o

	def __setitem__(self, key, o):
		if key in self.deleted:
			del self.deleted[key]

		self.changed[key] = None

	def __delitem__(self, key):
		try:
			del self.changed[key]
		except KeyError:
			pass

		self.deleted[key] = None

	def get(self, key):
		e = channel()
		self.queue.put((e, dbmget, (self.db, key), {}))
		errno, e = e.receive()
		if errno != 0:
			raise e

		return loads(e)

	def sync(self):
		if self.changed or self.deleted:
			e = channel()
			self.queue.put((e, self._sync, (), {}))
			errno, e = e.receive()
			if errno == 0:
				return

			raise e

	def close(self):
		if hasattr(self, 'db'):
			if self.changed or self.deleted:
				e = channel()
				self.queue.put((e, self._close_and_sync, (), {}))
				errno, e = e.receive()
				if errno != 0:
					raise e
			else:
				e = channel()
				self.queue.put((e, self._close, (), {}))
				errno, e = e.receive()
				if errno != 0:
					raise e

	def _close(self):
		self.db.close()
		del self.db
		self.unregister_connection()
		self.closed = True

	def _close_and_sync(self):
		self._sync()
		self.db.close()
		del self.db
		self.unregister_connection()
		self.closed = True

	def _sync(self):
		commit_lock, dct = environ[1][self.filename]
		commit_lock.acquire()
		try:
			self.cache_invalid_lock.acquire()
			try:
				if self.invalid:
					raise WriteConflictError(self.invalid)

				connections = []
				for dummy, ref in dct.items():
					conn = ref()
					if conn is not self:
						try:
							conn.cache_invalid_lock.acquire()
						except:
							pass
						else:
							connections.append(conn)
				try:
					for key in self.changed:
						self.db[key] = dumps(self.cache[key], 2)

					for key in self.deleted:
						del self.db[key]

					self.db.sync()

					changed = set(self.changed)
					changed.update(self.deleted)
					changed.update(self.created)
					for conn in connections:
						if has_intersection(conn.cache, changed):
							conn.invalid.update(changed)

					self.changed, self.deleted, self.created, \
						self.invalid = {}, {}, [], set()
				finally:
					for conn in connections:
						try:
							conn.cache_invalid_lock.release()
						except:
							pass
			finally:
				self.cache_invalid_lock.release()
		finally:
			commit_lock.release()

	def load(self, oid):
		try:
			o = self.cache[oid]
		except KeyError:
			self.cache_invalid_lock.acquire()
			try:
				if oid in self.invalid:
					raise ReadConflictError(oid)

				o = loads(self.db[oid])
				self.cache[oid] = o
			finally:
				self.cache_invalid_lock.release()

		return o

	def dump(self, oid, o):
		self.cache_invalid_lock.acquire()
		try:
			self.db[oid] = dumps(o, 2)
			self.cache[oid] = o
			self.cache[o._p_key] = o._p_data
			self.changed[oid] = None
		finally:
			self.cache_invalid_lock.release()

	def note_change(self, oid):
		self.changed[oid] = None

	def register_connection(self):
		envlock, envfiles = environ
		envlock.acquire()
		try:
			try:
				lock, dct = envfiles[self.filename]
			except KeyError:
				lock, dct = allocate_lock(), {}
				envfiles[self.filename] = (lock, dct)

			dct[id(self)] = weakref(self)
		finally:
			envlock.release()

	def unregister_connection(self):
		envlock, envfiles = environ
		try:
			lock, dct = envfiles[self.filename]
			lock.acquire()
			try:
				del dct[id(self)]
			finally:
				lock.release()
		except KeyError:
			pass
		else:
			envlock.acquire()
			try:
				if not dct:
					del envfiles[self.filename]
			finally:
				envlock.release()

def has_intersection(dct1, dct2):
	if len(dct1) > len(dct2):
		for i in dct2:
			if i in dct1:
				return True
	else:
		for i in dct1:
			if i in dct2:
				return True
	return False

def get_global_threadpool():
	if global_threadpool is None:
		try:
			import global_threadpool as pool
		except ImportError:
			pool = Pool()
			modules['global_threadpool'] = pool
			globals()['global_threadpool'] = pool
		else:
			globals()['global_threadpool'] = pool

		return pool

	return global_threadpool

try:
	urandom(16)
except NotImplementedError:
	def uuid4():
		n = long(fmt % tuple(randrange(256) for i in range16))
		n &= n1; n |= n2; n &= n3; n |= n4
		return ''.join(chr((n >> shift) & 0xff) for shift in range01288)
else:
	def uuid4():
		n = long(fmt % tuple(map(ord, urandom(16))), 16)
		n &= n1; n |= n2; n &= n3; n |= n4
		return ''.join(chr((n >> shift) & 0xff) for shift in range01288)

__new__ = object.__new__

dbmget = lambda db, key: db[key]
global_threadpool, environ = None, (allocate_lock(), {})
ConflictError  = type('ConflictError', (Exception, ), {})
ReadConflictError = type('ReadConflictError' , (ConflictError, ), {})
WriteConflictError = type('WriteConflictError', (ConflictError, ), {})

range01288 = list(reversed(range(0, 128, 8)))
n1, n2, n3, n4 = ~(0xc000 << 48L), 0x8000 << 48L, ~(0xf000 << 64L), 4 << 76L
range16, fmt, id0, minimum_degree = '\x00' * 16, '%02x' * 16, '\x00' * 16, 16
