import sys
from copy import copy
from os.path import dirname, abspath, join as path_join

base = abspath(path_join(dirname(__file__), '..'))
bin = lambda filename: path_join(base, 'bin', filename)
etc = lambda filename: path_join(base, 'etc', filename)
var = lambda filename: path_join(base, 'var', filename)

class Config(dict):
	def __getattr__(self, name):
		return self[name]

server = Config(
	port = 8080,
	fcgi = False )

daemon = Config(
	address = var('daemon.pid'),
	program = bin('server.py' ),
	verbose = False )

def Server(**args):
	c = copy(args)
	try:
		c['port'] = int(c['port'])
	except KeyError:
		pass
	try:
		c['fcgi'] = c['fcgi'] is True
	except KeyError:
		pass
	try:
		c['verbose'] = c['verbose'] is True
	except KeyError:
		pass

	server.update(c)

def Daemon(**args):
	c = copy(args)
	try:
		c['verbose'] = c['verbose'] is True
	except KeyError:
		pass

	daemon.update(c)

env = {'Server': Server, 'Daemon': Daemon,
	'etc': etc, 'var': var, 'bin': bin}



