# -*- coding: utf-8 -*-
from traceback import print_exc
from Eurasia.web import Form, Response, Pushlet, SimpleUpload
from time import sleep

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

# 请求分发器
def controller(conn):
	if conn.path[:8] == '/pushlet': # URL=/pushlet*
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
