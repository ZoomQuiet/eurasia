import sha, sqlite3
from random import random
from sqlite3 import IntegrityError
from time import time
from stackless import tasklet, schedule, channel

class UidError(Exception ): pass

class UidGenerator:
	def __init__(self):
		cursor = sqlite3.connect(':memory:').cursor()
		cursor.execute( (
			'CREATE TABLE IF NOT EXISTS session '
			'(id TEXT PRIMARY KEY, timeout INTEGER NOT NULL)' ) )
		cursor.execute('CREATE INDEX idx_timeout on session(timeout)')

		self.items = {}
		self.has_key = self.items.has_key
		self.cursor = cursor
		self.timeout = 1800
		self.garbage_timeout = 900
		self.next_garbage_clean = int(time()) + self.garbage_timeout

	def __setitem__(self, uid, item):
		try:
			self.cursor.execute(
				'INSERT INTO session VALUES (?, ?)',
				(uid, int(time()) + self.timeout) )

		except IntegrityError:
			try:
				self.cursor.execute(
					'SELECT id FROM session WHERE id=? AND timeout>?',
					(uid, now) ).fetchone()[0]
				self.cursor.execute(
					'UPDATE session SET timeout=? WHERE id=?',
					(now + self.timeout, uid) )
			except TypeError:
				raise UidError

		self.items[uid] = item

	def __getitem__(self, uid):
		now = int(time())
		if self.next_garbage_clean < now:
			self.garbage_clean()
		try:
			self.cursor.execute(
				'SELECT id FROM session WHERE id=? AND timeout>?',
				(uid, now) ).fetchone()[0]
			self.cursor.execute(
				'UPDATE session SET timeout=? WHERE id=?',
				(now + self.timeout, uid) )
		except TypeError:
			raise UidError

		return self.items[uid]

	def __delitem__(self, uid):
		try:
			self.items[uid].exit()
		except AttributeError:
			pass
		except TypeError:
			pass
		del self.items[uid]

		self.cursor.execute('DELETE FROM session WHERE id=', (uid, ))

	def __call__(self):
		timeout = int(time()) + self.timeout
		while True:
			try:
				uid = sha.new('%s' % random()).hexdigest()
				self.cursor.execute(
					'INSERT INTO session VALUES (?, ?)',
					(uid, timeout) )
				return uid

			except IntegrityError:
				continue

	def __lshift__(self, item):
		uid = self()
		self.items[uid] = item
		return uid

	def garbage_clean(self):
		now = int(time())
		for uid in [i[0] for i in self.cursor.execute(
			'SELECT id FROM session WHERE timeout<?',
			(now, ) ).fetchall() ]:

			try:
				self.items[uid].exit()
			except AttributeError:
				pass
			except TypeError:
				pass
			del self.items[uid]

		self.cursor.execute('DELETE FROM session WHERE timeout<?', (now, ))
		self.next_garbage_clean = now + self.garbage_timeout

def sleep(sec):
	c = channel()
	while True:
		uid = sha.new('%s' % random()).hexdigest()

		try:
			hypnus_cursor.execute(
				'INSERT INTO hypnus VALUES (?, ?)',
				(uid, time() + sec) )
			break
		except IntegrityError:
			continue

	hypnus_channels[uid] = c
	c.receive()

def hypnus_tasklets():
	while True:
		now = time()
		l = hypnus_cursor.execute(
			'SELECT id FROM hypnus WHERE timeout<?',
			(now, ) ).fetchall()
		for i in l:
			uid = i[0]
			c = hypnus_channels[uid]
			del hypnus_channels[uid]

			c.send(None)
		if l:
			hypnus_cursor.execute(
				'DELETE FROM hypnus WHERE timeout<?',
				(now, ))
		schedule()

hypnus_cursor = sqlite3.connect(':memory:').cursor()
hypnus_cursor.execute( (
	'CREATE TABLE IF NOT EXISTS hypnus '
	'(id TEXT PRIMARY KEY, timeout FLOAT NOT NULL)' ) )
hypnus_cursor.execute('CREATE INDEX idx_timeout on hypnus(timeout)')
hypnus_channels = {}
tasklet(hypnus_tasklets)()
