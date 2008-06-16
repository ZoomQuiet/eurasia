# -*- coding: utf-8 -*-
# 请阅读 lib/controller.py 文件

import sys
from os.path import dirname, abspath, join as path_join
sys.path.append(abspath(path_join(dirname(__file__), '..', 'lib')))

import schema
from Eurasia import pyetc
from schema import etc, env

pyetc.load(etc('demo.conf'), env=env)

from copy import copy
from controller import controller

c = copy(schema.server)
c['controller'] = controller

if c.fcgi:
	from Eurasia.fcgi import config, mainloop
else:
	from Eurasia.web import config, mainloop

config(**c)
mainloop()
