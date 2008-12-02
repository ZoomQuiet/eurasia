import sys
if sys.version_info < (2, 5):
	print >> sys.stderr, 'error: python 2.5 or higher is required, you are using %s' %'.'.join(
		str(i) for i in sys.version_info)

	sys.exit(1)

import os, os.path
base = os.path.dirname(__file__)
basejoin = lambda *args: os.path.abspath(os.path.join(*tuple([base] + list(args))))

try:
	import stackless
except ImportError:
	stackless = None
	if not os.path.exists(basejoin('3rd-party', 'pypy', 'lib', 'stackless.py')):
		print 'you must install eurasia first'
		sys.exit(0)

	try:
		from py.magic import greenlet
	except ImportError:
		print 'eurasia instance requires the py package (http://codespeak.net/py) to run'
		y = raw_input('download and install it now? [Y/n] ').strip().lower()
		while y not in ['', 'yes', 'y', 'no', 'n']:
			y = raw_input('download and install it now? [Y/n] ').strip().lower()

		if y in ['no', 'n']:
			sys.exit(0)

		if os.name == 'nt':
			easy_install = os.path.join(os.path.dirname(sys.executable), 'Scripts', 'easy_install.exe')
			if not os.path.exists(easy_install):
				os.system('%s %s' %(sys.executable, basejoin('ez_setup.py')))

			errno = os.system('%s py' %easy_install)
		else:
			try:
				import setuptools
			except ImportError:
				os.system('%s %s' %(sys.executable, basejoin('ez_setup.py')))

			easy_install = os.path.join(os.path.dirname(sys.executable), 'easy_install')
			errno = os.system('%s %s py' %(sys.executable, easy_install))

		if(errno != 0):
			sys.exit(errno)

try:
	import eurasia
except ImportError:
	eurasia   = None
	skelpath  = basejoin('skel')
	if not os.path.exists(skelpath):
		print 'can\'t find skel'
		sys.exit(0)
else:
	skelpath = os.path.join(os.path.dirname(eurasia.__file__), 'skel')

import optparse
p = optparse.OptionParser(prog = 'mkeurinstance.py',
	usage   = 'python mkeurinstance.py [options]',
	version = 'mkeurinstance.py for eurasia3')

p.add_option('-d', '--dir', dest='destination', metavar='DIR',
	help = 'the dir in which the instance home should be created')

options, args = p.parse_args(sys.argv[1:])
if args:
	p.error('too many arguments')

if not options.destination:
	while True:
		print 'please choose a directory in which you\'d like to install eurasia instance home'
		skeltarget = raw_input('directory: ').strip()

		if skeltarget == '':
			print >> sys.stderr, 'you must specify a directory'
			continue
		break

	options.destination = os.path.abspath(
		os.path.expanduser(skeltarget))

if not os.path.exists(options.destination):
	try:
		os.mkdir(options.destination)

	except OSError, e:
		print >> sys.stderr, 'could not create instance home: ', e
		sys.exit(1)

elif not os.path.isdir(options.destination):
	print >> sys.stderr, options.destination, 'is not a directory'
	print >> sys.stderr, '(instance homes cannot be created in non-directories)'
	sys.exit(1)

replacements = [('<<PYTHON>>', sys.executable)]

def copytree(src, dst):
	names = os.listdir(src)
	if '.svn' in names:
		names.remove('.svn')

	for name in names:
		srcname = os.path.join(src, name)
		dstname = os.path.join(dst, name)
		if os.path.isdir(srcname):
			os.mkdir(dstname)
			copytree(srcname, dstname)
		else:
			copyfile(srcname, dstname)

import shutil
def copyfile(src, dst):
	if dst.endswith('.in'):
		dst = dst[:-3]
		text = open(src, 'r').read()

		for var, string in replacements:
			text = text.replace(var, string)

		f = open(dst, 'w')
		f.write(text)
		f.close()
		shutil.copymode(src, dst)
		shutil.copystat(src, dst)
	else:
		shutil.copy2(src, dst)

copytree(skelpath, options.destination)
if not stackless:
	copyfile(os.path.abspath(os.path.join(
		os.path.dirname(__file__), '3rd-party', 'pypy', 'lib', 'stackless.py')),
		os.path.join(options.destination, 'lib', 'stackless.py'))

if not eurasia:
	destination = os.path.join(options.destination, 'lib', 'eurasia')
	if not os.path.exists(destination):
		try:
			os.mkdir(destination)

		except OSError, e:
			print >> sys.stderr, 'could not create instance home: ', e
			sys.exit(1)

	copytree(basejoin('src', 'eurasia'), destination)
