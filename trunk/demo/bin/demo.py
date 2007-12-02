#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-

import os, sys
from os import fork
from time import sleep
from sys import stderr, stdout
from socket import error as SocketError
from traceback import print_exc

import schema # 载入配置信息

from Eurasia import pyetc as etc
from Eurasia.daemon import Daemon, ServerProxy, Fault, \
	error as DaemonError

## #

def usage():
	print '使用方法: %s start|stop|status' %sys.argv[0]

def start():
	# 读取配置文件
	# demo.conf
	etc.load(schema.ETC('demo.conf'), env=schema.env)
	conf = schema.config.daemon

	try:
		# 创建 Daemon 对象
		daemon = Daemon(
			address = conf.address, # 进程控制器地址/pid 文件位置
			program = conf.program, # 后台进程程序位置
			verbose = conf.verbose  # 调试
			)

		print '进程管理器已经启动'

		pid = fork()

		if pid != 0:
			# 启动后台进程
			# 	daemon(arg1, arg2, ...)
			# 	参数 arg1, arg2 ... 将被用于启动后台进程:
			# 		program.py arg1 arg2 ...
			daemon()

		else:
			check(conf)

	except DaemonError, msg:
		print '进程管理器未启动, 原因是: ', msg

	except:
		print_exc(file=stderr)

def check(conf):
	sleep(0.5)
	print
	stdout.write('正在检查进程状态 ')
	stdout.flush()

	for i in xrange(3):
		stdout.write('.')
		stdout.flush()
		sleep(0.6)

	try:
		daemon = ServerProxy(conf.address)
		status = daemon.status()

		if status == 'running':
			print ' 进程 "%s" 已经启动' %conf.program

		elif status == 'stopped':
			stdout.write( ('进程 "%s " 启动失败, 正在停止进程管理器 ... '
				) %conf.program )

			stop()

		else:
			print '进程状态未知'

	except SocketError:
		print '进程管理器已经退出, 无法查询进程状态'

	except:
		print_exc(file=stderr)

	stdout.write('(按任意键继续)')

def stop():
	etc.load(schema.ETC('demo.conf'), env=schema.env)
	conf = schema.config.daemon

	# 取得进程控制器
	try:
		daemon = ServerProxy(conf.address)
		daemon.stop()

		print '进程已经退出'

	except SocketError:
		print '进程管理器未启动'

	except Fault:
		print '进程管理器已被强制关闭'

	except:
		print_exc(file=stderr)

def status():
	etc.load(schema.ETC('demo.conf'), env=schema.env)
	conf = schema.config.daemon

	try:
		daemon = ServerProxy(conf.address)
		status = daemon.status()

		if status == 'running':
			print '进程 "%s" 正在运行' %conf.program

		elif status == 'stopped':
			stdout.write( ('进程管理器正在运行, 但是进程 "%s" 已经停止, '
				'正在停止进程管理器 ... '
				) %conf.program )

			stop()

		else:
			print '进程管理器正在运行, 进程状态未知'

	except SocketError:
		print '进程管理器未启动'

	except:
		print_exc(file=stderr)

## #

# 解析参数

if len(sys.argv) != 2:
	usage()

elif sys.argv[1] == 'start':
	start()

elif sys.argv[1] == 'stop':
	stop()

elif sys.argv[1] == 'status':
	status()

else: usage()