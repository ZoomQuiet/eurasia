import sys
class Modules(type(sys)):	
	def __init__(self):
		type(sys).__init__(self, 'Eurasia.modules')

	def __getitem__(self, name):
		fullname = 'Eurasia.__modules.x-' + name
		try:
			__import__(fullname)
		except ImportError:
			raise KeyError(name)

		return sys.modules[fullname]

	def __getattr__(self, name):
		fullname = 'Eurasia.__modules.x-' + name
		try:
			__import__(fullname)
		except ImportError:
			raise AttributeError(name)

		return sys.modules[fullname]

sys.modules['Eurasia.__modules'] = sys.modules['Eurasia.modules']
sys.modules['Eurasia.modules'] = Modules()
