PROJECTNAME = 'Eurasia'
VERSION     = '3.0.0-alpha'
AUTHOR      = 'William Shen'

import sys
if sys.version_info < ( 2, 5 ):
	print 'ERROR: Your python version is not supported by %s-%s' %(
		PROJECTNAME, VERSION)
	print '%s-%s needs Stackless Python 2.5 or greater. You are running: %s' %(
		PROJECTNAME, VERSION, sys.version)

	sys.exit(1)

try:
	import stackless
except ImportError:
	print 'ERROR: Your python version is not supported by %s-%s' %(
		PROJECTNAME, VERSION)
	print '%s-%s needs Stackless Python 2.5 or greater. You are running: %s' %(
		PROJECTNAME, VERSION, sys.version)

	sys.exit(1)

from distutils.core import setup
setup(
	name     = PROJECTNAME ,
	author   = AUTHOR      ,
	version  = VERSION     ,
	packages = ['Eurasia']
)
