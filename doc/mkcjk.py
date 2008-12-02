#!/usr/bin/env python
import sys, os, os.path

dirname = os.path.abspath(sys.argv[1])

for filename in os.listdir(dirname):
	if filename[-5:].lower() != '.html':
		continue

	fullname = os.path.join(dirname, filename)
	data = unicode(unicode(open(fullname).read(), 'utf-8').encode('iso8859-1'), 'utf-8').encode('utf-8')
	fd = open(fullname, 'w')
	fd.write(data)
	fd.close()
