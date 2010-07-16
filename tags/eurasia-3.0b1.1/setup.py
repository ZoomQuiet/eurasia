import sys, os.path
if sys.version_info < (2, 5):
	print >> sys.stderr, 'error: python 2.5 or higher is required, you are using %s' %'.'.join(
		str(i) for i in sys.version_info)

	sys.exit(1)

def main():
	import ez_setup
	ez_setup.use_setuptools()

	from setuptools import setup
	args = dict(
		name = 'eurasia',
		version = '3.0.0b1',
		license = 'BSD license',
		description = 'a low-level python web framework',
		author = 'wilhelm shen',
		author_email = 'http://groups.google.com/group/eurasia-users',
		platforms = ['unix', 'linux', 'osx', 'cygwin', 'win32'],
		packages = ('eurasia', ),
		zip_safe = False )

	data_files = []
	os.path.walk('skel', skel_visit, data_files)

	try:
		import stackless
	except ImportError:
		args['install_requires'] = ['py']
		data_files.append(('', (os.path.join('3rd-party', 'pypy', 'lib', 'stackless.py'), )))

	args['data_files']  = data_files
	args['package_dir'] = {'eurasia': os.path.join('src', 'eurasia')}

	args['classifiers'] = [
		'Development Status :: 4 - Beta',
		'Intended Audience :: Developers',
		'License :: OSI Approved :: BSD License',
		'Programming Language :: Python',
		'Topic :: Internet',
		'Topic :: Software Development :: Libraries :: Application Frameworks']

	from distutils.command import install
	if len(sys.argv) > 1 and sys.argv[1] == 'bdist_wininst':
		for scheme in install.INSTALL_SCHEMES.values():
			scheme['data'] = scheme['purelib']

		for fileInfo in data_files:
			fileInfo[0] = '..\\PURELIB\\%s' % fileInfo[0]

	setup(**args)

def skel_visit(skel, dirname, names):
	L = []
	for name in names:
		if os.path.isfile(os.path.join(dirname, name)):
			L.append(os.path.join(dirname, name))

	skel.append([os.path.join('eurasia', dirname), L])

if __name__ == '__main__':
	main()
