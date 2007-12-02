# -*- coding: utf-8 -*-

# 设置路径, 增加 Eurasia-3.0.0/ 为 lib 目录
import sys, os.path

EURASIA_HOME = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEMO_HOME = os.path.abspath(os.path.join(EURASIA_HOME, 'demo'))

ETC = lambda filename: os.path.join(DEMO_HOME, 'etc', filename)
VAR = lambda filename: os.path.join(DEMO_HOME, 'var', filename)
BIN = lambda filename: os.path.join(DEMO_HOME, 'bin', filename)

sys.path.append(EURASIA_HOME)

# 默认配置
class Config(dict):
	def __getattr__(self, name):
		return self[name]

config = Config({
	'server': Config({
		'port': 8080 # 服务器使用 8080 端口

		}),

	'daemon': Config({
		'address': VAR('daemon.pid'), # pid 文件
		'program': BIN('server.py' ), # 服务器程序
		'verbose': True

		})
})

# 配置接口
def Server(**args):
	config['server'].update(args)

def Daemon(**args):
	config['daemon'].update(args)

# 配置文件 "demo.conf" 可见的变量
env = {'Server': Server, 'Daemon': Daemon,
	'etc': ETC, 'var': VAR, 'bin': BIN}



