#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-
import psyco
psyco.full()

import schema # 载入配置文件定义
from Eurasia import pyetc as etc
from Eurasia.web import config, mainloop, sleep, \
	Request, Form, Response, Pushlet, SimpleUpload, \
	UidGenerator, UidError

from traceback import print_exc

# 简单页面演示:
def SimplePageDemo(conn):
	response = Response(conn)
	response['Content-Type'] = 'text/html; charset=utf-8'
	print >> response, page
	response.close()

page = '''<html>
<a href="/pushlet">"Pushlet 输出流" 演示</a><br/>
<a href="/remotecall">"远程 JavaScript调用" 演示</a><br/>
<a href="/simpleuploadpage">"文件上传" 演示</a><br/>
<a href="/session?a=1&b=2">"Session/状态机" 演示</a>
</html>'''

##

# 流式输出演示:

def PushletDemo(conn):
	response = Response(conn)
	response['Content-Type'] = 'text/html; charset=utf-8'

	response.begin()
	print >> response, '<html>'

	for i in xrange(100):
		print >> response, '收到第 %d 条回复<br/>' % i
		sleep(2) # 间隔 2 秒发送一次

	print >> response, '</html>'
	response.end()

##

# 远程 JavaScript 方法调用

def RemoteCallPage(conn):
	# 疾速动态页面演示,
	# 通常我们只在性能要求比较变态的情况下使用 ...

	conn.write((
	'<html>'
	'<head>'
	'<script language="JavaScript">'
	'function my_alert(stuff) { alert(stuff); };'
	'</script>'
	'</head>'
	'<body>'
	'JavaScript Pushlet RPC!'
	'<iframe src="/remotecallstream" style="display: none;"></iframe>'
	'</body>'
	'</html>' ))
	conn.shutdown()

def RemoteCallDemo(conn):
	client = Pushlet(conn)

	client.begin()

	for i in xrange(100):
		client.my_alert('alert %d!' %i)
		sleep(5)  # 间隔 5 秒发送一次

	client.end()

##

# 文件上传:

def UploadPage(conn):
	conn.write((
	'<html>'
	'<form action="/simpleupload" method="post"'
		' enctype="multipart/form-data">'
	'<input type="hidden" name="a" value="表单变量A" />'
	'<input type="file" name="z-file" />'

		# ...

		# OK, 这是一个问题,
		# 表单变量名 "a" 必须小于文件控件的名称 "z-file":

		# 	>>> 'z-file' > a
		# 	>>> True

		# 因为对 SimpleUpload 组件来说, 文件组件的名字并不重要,
		# 所以请尽量起成 "zzzzzzzz" 之类的名字, 以保证他的值是最大的。

		# 另外, SimpleUpload 组件只上传支持一个文件,
		# ──── Eurasia3 的作者认为多线程上传是一个好主意。

	'<input type="submit" />'
	'</form>'
	'</html>' ))
	conn.shutdown()

def UploadDemo(conn):
	fd = SimpleUpload(conn)

	a = fd['a'] # 没错, 就是那个:
	            # <input type="hidden" name="a" value="..."/>

	filename = fd.filename
	size     = fd.size

	s1 = fd.read(10)
	s2 = fd.readline(10)
	s3 = fd.read()[-20:]  # 读完了

	resp = Response(conn) # Socket 如果没有读取完毕, 引起 IO 错误 
	resp['Content-Type'] = 'text/plain; charset=utf-8'

	print >> resp, '文件内容:'
	print >> resp, s1 + s2, '...',

	resp.write(s3) # 还可以这么写

	print >> resp, ''
	print >> resp, '那个 a:', a
	print >> resp, '文件名:', filename
	print >> resp, '文件大小:', size

	resp.close()

##

# Session 演示:
# Eurasia 使用状态机代替 Session 的作用

ug = uid_generator = UidGenerator() # Uid 生成器, 以及逻辑线程调度器
                                    # 下面是详细用法

def LogicThread(form):
	yield '这是你第一次访问, 表单变量: \n   ' + repr(form)
	form = yield '这是你第二次访问, 表单变量: \n   ' + repr(form)
	form = yield '这是你第三次访问, 表单变量: \n   ' + repr(form)
	form = yield '逻辑线程退出! 表单变量: \n   ' + repr(form)

def SessionDemo(conn):
	# 使用 Form 对象读取 HTTP 请求
	form = Form(conn,

		max_size=9999999) # 用户 Form 请求大小限制, 默认 1048576
		                  # 用户超限提交内容, 将引起 OverLimit 异常,
		                  # 同时 Socket 将会自动关闭

	# Form 会自动从连接中读取所有内容,
	# 这时进行 Response 写操作不会发生写异常 ...

	response = Response(conn)

	# 使用 Response 对象发送 HTTP 回复报文
	try:
		try:
			page = ug[form.uid].send(form)
		except StopIteration:
			uid = response.uid = ug << LogicThread(form)
			page = ug[uid].next()
		except UidError:
			uid = response.uid = ug << LogicThread(form)
			page = ug[uid].next()

		print >> response, page
	except:
		response['Content-Type'] = 'text/plain' # 设置  Response Header
		print_exc(file=response)

	# 完成 HTTP 回复报文, 并发送
	response.close()

##

# 请求分发器
def controller(conn):
	# 哦, 千万别忘了 controller 是一个 tasklet!
	# 您应该知道这意为着什么 ……

	# …… OK, Eurasia3 是单线程的服务器,
	# 您可以 schedule(), 但永远不要阻塞调用任何东西。
	# 而且请把 IO 扔给其他进程!

	if conn.path[:8] == '/session':   # URL=/session*
		SessionDemo(conn)
	elif conn.path[:8] == '/pushlet': # URL=/pushlet*
		PushletDemo(conn)
	elif conn.path[:17] == '/remotecallstream': # ..*
		RemoteCallDemo(conn)
	elif conn.path[:11] == '/remotecall':   # URL=..*
		RemoteCallPage(conn)
	elif conn.path[:17] == '/simpleuploadpage': # ..*
		UploadPage(conn)
	elif conn.path[:13] == '/simpleupload': # URL=..*
		UploadDemo(conn)
	else:
		SimplePageDemo(conn) # 默认页面

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
