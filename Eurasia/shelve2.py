from os import urandom
from random import randrange
from cPickle import dumps, loads
from weakref import ref as weakref
from gdbm import open as gdbm_open

def open(filename, mode='c'):
	conn = GdbmConnection(filename, mode)

	root = conn.root
	root.sync = conn.sync
	root.new = root._p_new
	root.close = conn.close
	return root

def lazy(filename, mode='c'):
	conn = LazyGdbmConnection(filename, mode)

	root = conn.root
	root.sync = conn.sync
	root.new = root._p_new
	root.close = conn.close
	return root

def leave(obj, name):
	return obj._p_leave(name)

class Modified(Exception):
	def __init__(self, last_version):
		Exception.__init__(self)
		self.last_version = last_version

class Base(object):
	def _p_note_change(self):
		try:
			self._p_conn[self._p_key] = self
		except AttributeError:
			pass

class Persistent(Base):
	def _p_initialize(self, conn):
		self._p_obj  = {}
		self._p_conn = conn

	def _p_new(self, cls):
		def whatever(*args, **kw):
			obj = __new__(cls)
			obj._p_initialize(self._p_conn)
			try:
				__init__ = obj.__init__
			except AttributeError:
				pass
			else:
				__init__(*args, **kw)

			return obj

		return whatever

	def __getstate__(self):
		try:
			return self._p_key
		except AttributeError:
			self._p_key = self._p_conn << self
			return self._p_key

	def __setstate__(self, key):
		self._p_key = key

	def __getattr__(self, name):
		if name[:3] == '_p_':
			raise AttributeError(name)

		try:
			o = self._p_obj[name]
		except KeyError:
			raise AttributeError(name)

		if isinstance(o, Base):
			o._p_pnt_ref = weakref(self)
			return o._p_load(self._p_conn)

		return o

	def __setattr__(self, name, value):
		if name[:3] == '_p_':
			self.__dict__[name] = value
			return

		try:
			o = self._p_obj[name]
		except KeyError:
			o = None

		if isinstance(value, Base):
			try:
				key = value._p_key
			except AttributeError:
				pass
			else:
				if isinstance(o, Base) and key == o._p_key:
					self._p_note_change()
					return
				try:
					try_leave = o._p_leave_key
				except AttributeError:
					raise ValueError('please leave first')

		self._p_obj[name] = value
		self._p_note_change()
		if isinstance(o, Base):
			o._p_release()

	def __delattr__(self, name):
		if name[:3] == '_p_':
			try:
				del self.__dict__[name]
			except KeyError:
				raise AttributeError(name)

			return
		try:
			o = self._p_obj[name]
		except KeyError:
			raise AttributeError(name)

		del self._p_obj[name]
		self._p_note_change()
		if isinstance(o, Base):
			o._p_release()

	def _p_dump(self):
		return dumps(self._p_obj)

	def _p_load(self, conn=None):
		if conn:
			self._p_conn = conn
		else:
			conn = self._p_conn

		attrs = self.__dict__
		if not attrs.has_key('_p_key') and attrs.has_key('_p_obj'):
			return self

		try:
			s = conn[self._p_key]
		except Modified, e:
			if not hasattr(self, '_p_obj'):
				self._p_obj = e.last_version._p_obj
		else:
			self._p_obj = loads(s)

		return self

	def _p_release(self):
		if self.__dict__.has_key('_p_key'):
			del self._p_conn[self._p_key]

		for o in self._p_obj.itervalues():
			if isinstance(o, Base):
				o._p_load(self._p_conn)._p_release()

	def _p_leave(self, key):
		o = getattr(self, key)
		o._p_leave_key = key
		o._p_leave_ref = weakref(self)
		del self._p_root[key]
		return o

class BTree(Base):
	@property
	def min_item(self):
		assert self, 'empty BTree has no min item'
		return self._p_root.min_item

	@property
	def max_item(self):
		assert self, 'empty BTree has no max item'
		return self._p_root.max_item

	def _p_get_key(self):
		return self._p_root.key

	def _p_set_key(self, key):
		self._p_root.key = key

	_p_key = property(_p_get_key, _p_set_key)

	def _p_get_conn(self):
		return self._p_root.conn

	def _p_set_conn(self, conn):
		self._p_root.conn = conn

	_p_conn = property(_p_get_conn, _p_set_conn)

	def _p_initialize(self, conn):
		self._p_root = BNode(conn)

	def _p_new(self, cls):
		def whatever(*args, **kw):
			obj = __new__(cls)
			obj._p_initialize(self._p_root.conn)
			try:
				__init__ = obj.__init__
			except AttributeError:
				pass
			else:
				__init__(*args, **kw)

			return obj

		return whatever

	def __getstate__(self):
		return self._p_root.__getstate__()

	def __setstate__(self, key):
		self._p_root = BNode(None, key)

	def __repr__(self):
		return '{%s}' % ', '.join('%r: %r' % (key, value
			) for key, value in self.items())

	def __len__(self):
		return len(self._p_root)

	def __nonzero__(self):
		return bool(self._p_root.items)

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
		try:
			o = self[key]
		except KeyError:
			o = None

		if isinstance(value, Base):
			try:
				key = value._p_key
			except AttributeError:
				pass
			else:
				if isinstance(o, Base) and key == o._p_key:
					self._p_note_change()
					return
				try:
					try_leave = o._p_leave_key
				except AttributeError:
					raise ValueError('please leave first')

		if len(self._p_root.items) == 2 * minimum_degree - 1:
			try:
				pnt = self._p_pnt_ref()
			except AttributeError:
				if hasattr(self._p_root, 'key'):
					raise RuntimeError('parent node not exists')

				pnt = None

			node = BNode(self._p_root.conn)
			node.nodes = [self._p_root]
			node.split_child(0, node.nodes[0])
			self._p_root = node
			if pnt:
				pnt._p_note_change()

		self._p_root.insert_item((key, value))
		if isinstance(o, Base):
			o._p_release()

	def __delitem__(self, key):
		try:
			o = self[key]
		except KeyError:
			o = None

		del self._p_root[key]
		if isinstance(o, Base):
			o._p_release()

	def _p_dump(self):
		return self._p_root.__getstate__()

	def _p_load(self, conn=None):
		root = self._p_root
		if conn:
			root.conn = conn
		else:
			conn = root.conn

		try:
			key = root.key
		except AttributeError:
			if hasattr(root, 'items'):
				return self
			raise

		try:
			s = conn[key]
		except Modified, e:
			if not hasattr(self, 'items'):
				node = e.last_version
				root.items, root.nodes = node.items, node.nodes
		else:
			root.items, root.nodes = loads(s)

		return self

	def _p_release(self):
		self._p_root._p_release()

	def _p_leave(self, key):
		o = self[key]
		o._p_leave_key = key
		o._p_leave_ref = weakref(self)
		del self._p_root[key]
		return o

	def has_key(self, key):
		return self._p_root.search(key) is not None

	def get(self, key, default=None):
		try:
			return self[key]
		except KeyError:
			return default

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
		pnt = self._p_pnt_ref()
		if not pnt:
			raise RuntimeError('parent node not exists')

		o = self._p_root
		self._p_root = BNode(self._p_root.conn)
		pnt._p_note_change()
		o._p_release()

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
		for item in self._p_root:
			yield item

	def items_backward(self):
		for item in reversed(self._p_root):
			yield item

	def items_from(self, key, closed=True):
		for item in self._p_root.iter_from(key):
			if closed or item[0] != key:
				yield item

	def items_backward_from(self, key, closed=False):
		if closed:
			item = self._p_root.search(key)
			if item is not None:
				yield item

		for item in self._p_root.iter_backward_from(key):
			yield item

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

class BNode(object):
	@property
	def min_item(self):
		if not self.nodes:
			return self.get(self.items[0])
		else:
			return self.nodes[0]._p_load(self.conn).min_item

	@property
	def max_item(self):
		if not self.nodes:
			return self.get(self.items[-1])
		else:
			return self.nodes[-1]._p_load(self.conn).max_item

	def __init__(self, conn, key=None):
		self.conn = conn
		if key:
			self.key = key
		else:
			self.items = []
			self.nodes = None

	def __getstate__(self):
		try:
			return self.key
		except AttributeError:
			self.key = self.conn << self
			return self.key

	def __setstate__(self, key):
		self.key = key

	def __len__(self):
		result = len(self.items)
		for node in self.nodes or []:
			result += len(node._p_load(self.conn))

		return result

	def __delitem__(self, key):
		p = self.get_position(key)
		matches = p < len(self.items) and self.items[p][0] == key
		if not self.nodes:
			if matches:
				del self.items[p]
				self._p_note_change()
			else:
				raise KeyError(key)
		else:
			node = self.nodes[p]._p_load(self.conn)
			lower_sibling = p > 0 and self.nodes[p - 1]._p_load(self.conn)
			upper_sibling = p < len(self.nodes) - 1 and self.nodes[p + 1]._p_load(self.conn)
			if matches:
				if node and len(node.items) >= minimum_degree:
					extreme = node.max_item
					del node[extreme[0]]
					self.items[p] = extreme
				elif upper_sibling and len(upper_sibling.items
					) >= minimum_degree:
					extreme = upper_sibling.min_item
					del upper_sibling[extreme[0]]
					self.items[p] = extreme
				else:
					extreme = upper_sibling.min_item
					del upper_sibling[extreme[0]]
					node.items = node.items + [extreme
						] + upper_sibling.items
					if node.nodes:
						node.nodes = node.nodes + upper_sibling.nodes

					del self.items[p]

					p1 = p + 1
					try:
						key2 = self.nodes[p1].key
					except AttributeError:
						key2 = None
					del self.nodes[p1]
					if key2:
						del self.conn[key2]

				self._p_note_change()
			else:
				if not (node and len(node.items) >= minimum_degree):
					if lower_sibling and len(lower_sibling.items
						) >= minimum_degree:

						node.items.insert(0, self.items[p - 1])
						self.items[p - 1] = lower_sibling.items[-1]
						del lower_sibling.items[-1]
						if node.nodes:
							node.nodes.insert(0, lower_sibling.nodes[-1]._p_load(self.conn))
							del lower_sibling.nodes[-1]
						lower_sibling._p_note_change()
					elif upper_sibling and len(upper_sibling.items
						) >= minimum_degree:

						node.items.append(self.items[p])
						self.items[p] = upper_sibling.items[0]
						del upper_sibling.items[0]
						if node.nodes:
							node.nodes.append(upper_sibling.nodes[0])
							del upper_sibling.nodes[0]
						upper_sibling._p_note_change()
					elif lower_sibling:
						p1 = p - 1
						node.items = (lower_sibling.items + [self.items[p1]] +
							node.items)
						if node.nodes:
							node.nodes = lower_sibling.nodes + node.nodes

						del self.items[p1]

						try:
							key2 = self.nodes[p1].key
						except AttributeError:
							key2 = None
						del self.nodes[p1]
						if key2:
							del self.conn[key2]
					else:
						node.items = (node.items + [self.items[p]] +
							upper_sibling.items)
						if node.nodes:
							node.nodes = node.nodes + upper_sibling.nodes

						del self.items[p]

						p1 = p + 1
						try:
							key2 = self.nodes[p1].key
						except AttributeError:
							key2 = None
						del self.nodes[p1]
						if key2:
							del self.conn[key2]

					self._p_note_change()
					node._p_note_change()

					assert (node and len(node.items) >= minimum_degree)
				del node[key]
			if not self.items:
				o = self.nodes[0]
				self.items = self.nodes[0].items
				self.nodes = self.nodes[0].nodes
				del self.conn[o.key]

	def __iter__(self):
		if not self.nodes:
			for item in self.items:
				yield self.get(item)
		else:
			for position, item in enumerate(self.items):
				for it in self.nodes[position]._p_load(self.conn):
					yield self.get(it)
				yield self.get(item)
			for it in self.nodes[-1]._p_load(self.conn):
				yield self.get(it)

	def __reversed__(self):
		if not self.nodes:
			for item in reversed(self.items):
				yield self.get(item)
		else:
			for item in reversed(self.nodes[-1]._p_load(self.conn)):
				yield self.get(item)
			for position in range(len(self.items) - 1, -1, -1):
				yield self.get(self.items[position])
				for item in reversed(self.nodes[position]._p_load(self.conn)):
					yield self.get(item)

	def _p_dump(self):
		return dumps((self.items, self.nodes))

	def _p_load(self, conn=None):
		if conn:
			self.conn = conn
		else:
			conn = self.conn

		try:
			key = self.key
		except AttributeError:
			if hasattr(self, 'items'):
				return self
			raise

		try:
			s = conn[key]
		except Modified, e:
			if not hasattr(self, 'items'):
				node = e.last_version
				self.items, self.nodes = node.items, node.nodes
		else:
			self.items, self.nodes = loads(s)

		return self

	def _p_release(self):
		if hasattr(self, 'key') and self.key:
			del self.conn[self.key]

		for key, o in self.items:
			if isinstance(o, Base):
				o._p_release()

		if self.nodes:
			for node in self.nodes:
				node._p_release()

	def _p_note_change(self):
		try:
			self.conn[self.key] = self
		except AttributeError:
			pass

	def get(self, item):
		try:
			key, o = item
		except TypeError:
			return None

		if isinstance(o, Base):
			o._p_load(self.conn)
			o._p_pnt_ref = weakref(self)

		return key, o

	def iter_from(self, key):
		position = self.get_position(key)
		if not self.nodes:
			for item in self.items[position:]:
				yield self.get(item)
		else:
			for item in self.nodes[position]._p_load(self.conn).iter_from(key):
				yield self.get(item)
			for p in range(position, len(self.items)):
				yield self.get(self.items[p])
				for item in self.nodes[p + 1]._p_load(self.conn):
					yield self.get(item)

	def iter_backward_from(self, key):
		position = self.get_position(key)
		if not self.nodes:
			for item in reversed(self.items[:position]):
				yield self.get(item)
		else:
			for item in self.nodes[position]._p_load(self.conn).iter_backward_from(key):
				yield self.get(item)
			for p in range(position - 1, -1, -1):
				yield self.get(self.items[p])
				for item in reversed(self.nodes[p]._p_load(self)):
					yield self.get(item)

	def get_position(self, key):
		for position, item in enumerate(self.items):
			if item[0] >= key:
				return position

		return len(self.items)

	def search(self, key):
		position = self.get_position(key)
		if position < len(self.items) and self.items[position][0] == key:
			return self.get(self.items[position])
		elif not self.nodes:
			return None
		else:
			return self.nodes[position]._p_load(self.conn).search(key)

	def insert_item(self, item):
		assert not len(self.items) == 2 * minimum_degree - 1
		key = item[0]
		position = self.get_position(key)
		if position < len(self.items) and self.items[position][0] == key:
			self.items[position] = item
			self._p_note_change()
		elif not self.nodes:
			self.items.insert(position, item)
			self._p_note_change()
		else:
			child = self.nodes[position]._p_load(self.conn)
			if len(child.items) == 2 * minimum_degree - 1:
				self.split_child(position, child)
				if key == self.items[position][0]:
					self.items[position] = item
					self._p_note_change()
				else:
					if key > self.items[position][0]:
						position += 1
					self.nodes[position]._p_load(self.conn).insert_item(item)
			else:
				self.nodes[position]._p_load(self.conn).insert_item(item)

	def split_child(self, position, child):
		assert len(self.items) != 2 * minimum_degree - 1
		assert self.nodes
		assert self.nodes[position] is child
		assert len(child.items) == 2 * minimum_degree - 1
		bigger = BNode(self.conn)
		middle = minimum_degree - 1
		splitting_key = child.items[middle]
		bigger.items = child.items[middle + 1:]
		child.items = child.items[:middle]
		assert len(bigger.items) == len(child.items)
		if child.nodes:
			bigger.nodes = child.nodes[middle + 1:]
			child.nodes = child.nodes[:middle + 1]
			assert len(bigger.nodes) == len(child.nodes)
		self.items.insert(position, splitting_key)
		self.nodes.insert(position + 1, bigger)

		child._p_note_change()
		self._p_note_change()

class GdbmConnection(object):
	roottype = BTree

	@property
	def root(self):
		try:
			tr = self._p_root_ref()
		except AttributeError:
			tr = loads(self.db[id0])._p_load(self)
			tr._p_pnt_ref = weakref(self)
			self._p_root_ref = weakref(tr)

		if not tr:
			tr = loads(self.db[id0])._p_load(self)
			tr._p_pnt_ref = weakref(self)
			self._p_root_ref = weakref(tr)

		return tr

	def __init__(self, filename, mode='c'):
		self.mode = mode
		self.filename = filename
		self.db = gdbm_open(filename, mode)
		if not self.db.has_key(id0):
			tr = self.new(self.roottype)()
			self.db[id0] = dumps(tr)

	def __del__(self):
		self.close()

	def __lshift__(self, obj):
		oid = uuid4()
		while self.db.has_key(oid):
			oid = uuid4()

		obj._p_key = oid
		self.db[oid] = obj._p_dump()
		return oid

	def __getitem__(self, key):
		return self.db[key]

	def __setitem__(self, key, obj):
		self.db[key] = obj._p_dump()

	def __delitem__(self, key):
		try:
			del self.db[key]
		except KeyError:
			pass

	def _p_note_change(self):
		root = self._p_root_ref()
		if not root:
			raise RuntimeError('db root not exists')

		self.db[id0] = dumps(root)

	def new(self, cls):
		def whatever(*args, **kw):
			obj = __new__(cls)
			obj._p_initialize(self)
			try:
				__init__ = obj.__init__
			except AttributeError:
				pass
			else:
				__init__(*args, **kw)

			return obj

		return whatever

	def close(self):
		self.db.close()

	def sync(self):
		self.db.sync()

class LazyGdbmConnection(GdbmConnection):
	def __init__(self, filename, mode='c'):
		self.mode = mode
		self.changed = {}
		self.filename = filename
		self.db = gdbm_open(filename, mode)
		if not self.db.has_key(id0):
			tr = self.new(self.roottype)()
			self.db[id0] = dumps(tr)

	def __setitem__(self, key, o):
		self.changed[key] = o

	def __getitem__(self, key):
		try:
			raise Modified(self.changed[key])
		except KeyError:
			return self.db[key]

	def __delitem__(self, key):
		try:
			del self.db[key]
		except KeyError:
			pass

		try:
			del self.changed[key]
		except KeyError:
			pass

	def close(self):
		for key, obj in self.changed.items():
			self.db[key] = obj._p_dump()

		self.db.close()
		self.changed = {}

	def sync(self):
		for key, obj in self.changed.items():
			self.db[key] = obj._p_dump()

		self.db.sync()
		self.changed = {}

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

range16 = '\x00' * 16; fmt = '%02x' * 16
range01288 = list(reversed(range(0, 128, 8)))
n1 = ~(0xc000 << 48L); n2 = 0x8000 << 48L
n3 = ~(0xf000 << 64L); n4 = 4 << 76L

id0 = '\x00' * 16; minimum_degree = 16
