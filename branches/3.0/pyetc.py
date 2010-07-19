import sys, os.path

Module = type(sys)
modules = {}

def load(fullpath, env={}, module=Module):
	try:
		code = open(fullpath).readlines()
	except IOError:
		raise ImportError, 'No module named  %s' %fullpath

	code = '\n'.join(i.rstrip() for i in code)

	filename = os.path.basename(fullpath)

	try:
		return modules[filename]
	except KeyError:
		pass

	m = module(filename)
	m.__module_class__ = module
	m.__file__ = fullpath

	m.__dict__.update(env)

	exec compile(code, filename, 'exec') in m.__dict__
	modules[filename] = m

	return m

def unload(m):
	filename = os.path.basename(m.__file__)
	del modules[filename]

	return None

def reload(m):
	fullpath = m.__file__

	try:
		code = open(fullpath).read()
	except IOError:
		raise ImportError, 'No module named  %s' %fullpath

	code = '\n'.join(i.rstrip() for i in code)

	env = m.__dict__
	module_class = m.__module_class__

	filename = os.path.basename(fullpath)
	m = module_class(filename)

	m.__file__ = fullpath
	m.__dict__.update(env)
	m.__module_class__ = module_class

	exec compile(code, filename, 'exec') in m.__dict__
	modules[filename] = m

	return m
