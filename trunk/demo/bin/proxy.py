#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-

import schema # 载入配置文件定义
from Eurasia import pyetc as etc
from Eurasia.aisarue import urlopen
from Eurasia.web import config, mainloop, Request, Response

# 代理服务器
def controller(client):
	request = Request(client)

	url = client.query_string and '%s?%s' %(
		client.path, client.query_string
		) or client.path

	fd = (client.method == 'get') and urlopen(url
		) or urlopen(url, request)

	response = Response(client)
	for key in request.keys():
		response['-'.join(i.capitalize() for i in key.split('-'))
			] = request[key]

	response.begin()
	ll = fd.read(8192)
	while ll:
		response.write(ll)
		ll = fd.read(8192)
	response.end()

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
