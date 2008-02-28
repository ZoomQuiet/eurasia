#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-

import schema # 载入配置文件定义
from Eurasia import pyetc as etc
from Eurasia.web import config
from Eurasia.aisarue import urlopen
from Eurasia.web import config, mainloop, Request, Response

# 代理服务器
def controller(client):
	request = Request(client)

	url = client.query_string and '%s?%s' %(
		client.path, client.query_string
		) or client.path

	d = {}
	for key, value in client.headers.items():
		d['-'.join(i.capitalize() for i in key.split('-'))] = value
	del d['Proxy-Connection']
	d['Connection'] = 'close'

	fd = (client.method == 'get') and urlopen(url, headers=d
		) or urlopen(url, headers=d, data=request)

	response = Response(client)
	for key in fd.keys():
		response['-'.join(i.capitalize() for i in key.split('-'))
			] = fd[key]

	response.begin()
	ll = fd.read(8192)
	while ll:
		response.write(ll)
		ll = fd.read(8192)

	response.end()
	print '[%s]' %url

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
