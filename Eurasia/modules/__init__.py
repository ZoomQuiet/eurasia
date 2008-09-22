import sys
class Node(object):
	def __init__(self, modules, name):
		self.__name = name
		self.__modules = modules

	def __call__(self):
		raise ImportError(self.__name)

	def __getattr__(self, name):
		name = '%s.%s' %(self.__name, name)
		try:
			return self.__modules[name]()
		except KeyError:
			self.__name = name
			return self

	def __getitem__(self, name):
		name = '%s.%s' %(self.__name, name)
		try:
			return self.__modules[name]()
		except KeyError:
			self.__name = name
			return self

class Modules(type(sys)):	
	def __init__(self):
		type(sys).__init__(self, 'Eurasia.modules')
		self.__node    = Node
		self.__modules = modules

	def __getattr__(self, name):
		try:
			return self.__modules[name]()
		except KeyError:
			return self.__node(self.__modules, name)

	def __getitem__(self, name):
		try:
			return self.__modules[name]()
		except KeyError:
			return self.__node(self.__modules, name)

def sleep():
	from Eurasia.__modules import hypnus
	return hypnus.sleep

def urlopen():
	from Eurasia.__modules import aisarue
	return aisarue.urlopen

modules = dict((
	('time.sleep'    , sleep  ),
	('urllib.urlopen', urlopen)  ))

sys.modules['Eurasia.__modules'] = sys.modules['Eurasia.modules']
sys.modules['Eurasia.modules'] = Modules()
