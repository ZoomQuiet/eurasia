#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-

import sys
from os.path import dirname, abspath, join as path_join
sys.path.append(abspath(path_join(dirname(__file__), '..', 'lib')))

import os
import schema
from os import fork
from copy import copy
from time import sleep
from sys import stderr, stdout
from socket import error as SocketError
from traceback import print_exc

from Eurasia import pyetc
from Eurasia.daemon import Daemon, ServerProxy, Fault, \
	error as DaemonError

## #

def usage():
	print '使用方法: %s start|stop|status' %sys.argv[0]

def start():
	pyetc.load(schema.etc('demo.conf'), env=schema.env)
	c = copy(schema.daemon)

	try:
		daemon = Daemon(**c)
		print '进程管理器已经启动'

		pid = fork()
		if pid != 0:
			# 启动后台进程
			# 	daemon(arg1, arg2, ...)
			# 	参数 arg1, arg2 ... 将被用于启动后台进程:
			# 		program.py arg1 arg2 ...
			daemon()

		else:
			check(c)

	except DaemonError, msg:
		print '进程管理器未启动, 原因是: ', msg

	except:
		print_exc(file=stderr)

def check(c):
	sleep(0.5)
	print
	stdout.write('正在检查进程状态 ')
	stdout.flush()

	for i in xrange(3):
		stdout.write('.')
		stdout.flush()
		sleep(0.6)

	try:
		daemon = ServerProxy(c.address)
		status = daemon.status()

		if status == 'running':
			print ' 进程 "%s" 已经启动' %c.program

		elif status == 'stopped':
			stdout.write( ('进程 "%s " 启动失败, 正在停止进程管理器 ... '
				) %c.program )

			stop()

		else:
			print '进程状态未知'

	except SocketError:
		print '进程管理器已经退出, 无法查询进程状态'

	except:
		print_exc(file=stderr)

	stdout.write('(按回车键继续)')

def stop():
	pyetc.load(schema.etc('demo.conf'), env=schema.env)
	c = copy(schema.daemon)

	# 取得进程控制器
	try:
		daemon = ServerProxy(c.address)
		daemon.stop()

		print '进程已经退出'

	except SocketError:
		print '进程管理器未启动'

	except Fault:
		print '进程管理器已被强制关闭'

	except:
		print_exc(file=stderr)

def status():
	pyetc.load(schema.etc('demo.conf'), env=schema.env)
	c = copy(schema.daemon)

	try:
		daemon = ServerProxy(c.address)
		status = daemon.status()

		if status == 'running':
			print '进程 "%s" 正在运行' %c.program

		elif status == 'stopped':
			stdout.write( ('进程管理器正在运行, 但是进程 "%s" 已经停止, '
				'正在停止进程管理器 ... '
				) %c.program )

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
