import sys
class Modules(type(sys)):	
	def __init__(self):
		type(sys).__init__(self, 'eurasia.modules')

	def __getitem__(self, name):
		fullname = 'eurasia.__modules.x-' + name
		try:
			__import__(fullname)
		except ImportError:
			raise KeyError(name)

		return sys.modules[fullname]

	def __getattr__(self, name):
		fullname = 'eurasia.__modules.x-' + name
		try:
			__import__(fullname)
		except ImportError:
			raise AttributeError(name)

		return sys.modules[fullname]

sys.modules['eurasia.__modules'] = sys.modules['eurasia.modules']
sys.modules['eurasia.modules'] = Modules()
