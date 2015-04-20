# Eurasia 高效能服务器 #

欢迎加入 [Eurasia 用戶組](http://groups.google.com/group/eurasia-users) 以获取最新动向及技术支持！

欲快速了解 eurasia 技术敬请阅读 [官方文档](http://code.google.com/p/eurasia/wiki/eurasia_3_2_userguide) 。

快速用例：

```
from eurasia import httpserver
def handler(http):
    http.start_response('200 OK', [('Content-Type', 'text/html')])
    http.write('<html>Hello world</html>')
    http.close()

server = httpserver('0.0.0.0:8080', handler)
server.serve_forever()
```

执行脚本，使用浏览器访问 http://127.0.0.1:8080/ 即可。

# 安装 #

[下载](http://eurasia.googlecode.com/svn/branches/3.2/eurasia.py) [eurasia.py](http://eurasia.googlecode.com/svn/branches/3.2/eurasia.py) 即可，无需安装。

```
$ svn co https://eurasia.googlecode.com/svn/branches/3.2/
```

## 安装依赖 ##

安装 libev 库（将 libev.so 与 eurasia.py 放在同一目录即可）：

```
$ wget https://eurasia-dl.googlecode.com/files/libev-1.125.tar.bz2
$ tar xjf libev-1.125.tar.bz2
$ cd libev-1.125
$ chmod +x autogen.sh
$ ./autogen.sh
$ ./configure
$ make
$ cp .libs/libev.so /PATH/TO/EURASIA_PY
```

安装 libeio 库（将 libeio.so 与 eurasia.py 放在同一目录即可）：

```
$ wget https://eurasia-dl.googlecode.com/files/libeio-1.424.tar.bz2
$ tar xjf libeio-1.424.tar.bz2
$ cd libeio-1.424
$ chmod +x autogen.sh
$ ./autogen.sh
$ ./configure
$ make
$ cp .libs/libeio.so /PATH/TO/EURASIA_PY
```

安装 greenlet 模块（将 greenlet.so 与 eurasia.py 放在同一目录即可）：

```
$ wget http://pypi.python.org/packages/source/g/greenlet/greenlet-0.4.0.zip
$ unzip greenlet-0.4.0.zip
$ cd greenlet-0.4.0
$ /PATH/TO/PYTHON setup.py build_ext --inplace
$ cp greenlet.so /PATH/TO/EURASIA_PY
```

Eurasia 的读法在 [这里](http://www.m-w.com/dictionary/eurasia) 。