import sqlite3, sha
from time import time
from random import random
from sqlite3 import IntegrityError
from stackless import tasklet, schedule, channel

def sleep(sec):
	c = channel()
	while True:
		uid = sha.new('%s' % random()).hexdigest()

		try:
			cursor.execute(
				'INSERT INTO hypnus VALUES (?, ?)',
				(uid, time() + sec) )
			break
		except IntegrityError:
			continue

	channels[uid] = c
	c.receive()

def tasklets():
	while True:
		now = time()
		l = cursor.execute(
			'SELECT id FROM hypnus WHERE timeout<?',
			(now, ) ).fetchall()
		for i in l:
			uid = i[0]
			c = channels[uid]
			del channels[uid]

			c.send(None)
		if l:
			cursor.execute(
				'DELETE FROM hypnus WHERE timeout<?',
				(now, ))
		schedule()

cursor = sqlite3.connect(':memory:').cursor()
cursor.execute( ( 'CREATE TABLE IF NOT EXISTS hypnus '
	'(id TEXT PRIMARY KEY, timeout FLOAT NOT NULL)' ) )
cursor.execute('CREATE INDEX idx_timeout on hypnus(timeout)')
channels = {}; tasklet(tasklets)()

__import__('time').sleep = sleep
