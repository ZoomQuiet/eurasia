#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-

import schema # 载入配置文件定义
from Eurasia import pyetc as etc
from Eurasia.web import config
from Eurasia.web import config, mainloop, Response

from urllib import urlopen

# 代理服务器
def controller(client):
	headers = {}
	for key, value in client.headers.items():
		headers['-'.join(i.capitalize() for i in key.split('-'))] = value
	del headers['Proxy-Connection']
	headers['Connection'] = 'close'

	fd = (client.method == 'get') and urlopen(client.path, headers=headers
		) or urlopen(client.path, data=client.read(), headers=headers)

	print '%s %s' %(client.method.upper(), client.path)

	response = Response(client,
		version=fd.version, status=fd.status, message=fd.message)
	for key, value in fd.headers.items():
		response['-'.join(i.capitalize() for i in key.split('-'))
			] = value

	response.begin()
	ll = fd.read(8192)
	while ll:
		response.write(ll)
		ll = fd.read(8192)

	response.end()
	print '(%s %s %s)' %(client.path, response.status, response.message)

# 配置服务器
etc.load(schema.ETC('demo.conf'), # 配置文件
	env=schema.env )          # 作为配置文件的 Python 脚本的可见环境

conf = schema.config.server

config(
	controller = controller, # 应用分发器
	port = conf.port,        # 设置端口
	verbose = conf.verbose   # 调试开关
)

if __name__ == '__main__':
	mainloop()
