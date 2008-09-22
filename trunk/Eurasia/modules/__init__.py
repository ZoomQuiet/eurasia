import sys
class Modules(type(sys)):	
	def __init__(self):
		type(sys).__init__(self, 'Eurasia.modules')
		self.__modules = modules

	def __getattr__(self, name):
		try:
			return self.__modules[name]()
		except KeyError:
			raise ImportError(name)

modules = (
	('time'  , 'hypnus' ),
	('urllib', 'aisarue') )

code = '''\
def %s_module():
	from Eurasia.__modules import %s
	return %s'''

for dummy, s in modules:
	exec(code %(s, s, s))

modules = dict((a, eval(b+'_module')) for a, b in modules)
sys.modules['Eurasia.__modules'] = sys.modules['Eurasia.modules']
sys.modules['Eurasia.modules'] = Modules()
