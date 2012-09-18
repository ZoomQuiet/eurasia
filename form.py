class form:
    exec '''\
def __init__(self, http, max_size=0x100000, timeout=-1):
    environ = http.environ
    left    = http.left
    if 0 == left:
        self.salt = salt = urandom(4)
        self.data = data = {}
        for item in environ['QUERY_STRING'].split('&'):%(s)s
    elif left > max_size:
        raise ValueError('length > %%i' %% max_size)
    else:
        if -1 == timeout:
            timeout = 16. + (left >> 10)
        data = http.read(left, timeout)
        self.salt = salt = urandom(8)
        self.data = data = {}
        for item in environ['QUERY_STRING'].split('&'):%(s)s
        for item in data.split('&'):%(s)s''' % {'s': '''
            k, v  = item.split('=', 1)
            k = salt + unquote_plus(k)
            value = data.get(k)
            if value is None:
                data[k] = unquote_plus(v)
            elif isinstance(value, list):
                data[k].append(unquote_plus(v))
            else:
                data[k] = [value, unquote_plus(v)]'''}

    def __getitem__(self, key):
        return self.data[self.salt + key]

    def __contains__(self, key):
        return (self.salt + key) in self.data

    def get(self, key, default=None):
        return self.data.get(self.salt+key, default)

    def has_key(self, key):
        return (self.salt + key) in self.data

code = r'''def read(self, size, timeout=-1):
    if 0 == self.left:
        if self.closed:
            return ''
        assert self.nl   == self.http.read(self.nlen)
        assert self.stop == self.http.read(self.stoplen)
        self.closed = 1
        return ''
    if size > self.left:
        if -1 == timeout:
            timeout = 16. + (self.left >> 10)
        data = self.http.read(self.left, timeout)
        self.left = 0
    else:
        if -1 == timeout:
            timeout = 16. +  (size >> 10)
        data = self.http.read(size, timeout)
        self.left -= len(data)
    if 0 == self.left:
        self.closed = 1
        assert self.nl   == self.http.read(self.nlen)
        assert self.stop == self.http.read(self.stoplen)
    return data
def readline(self, size, timeout=-1):
    if 0 == self.left:
        if self.closed:
            return ''
        assert self.nl   == self.http.read(self.nlen)
        assert self.stop == self.http.read(self.stoplen)
        self.closed = 1
        return ''
    if size > self.left:
        if -1 == timeout:
            timeout = 16. + (self.left >> 10)
        data = self.http.readline(self.left, timeout)
    else:
        if -1 == timeout:
            timeout = 16. + (size >> 10)
        data = self.http.readline(size, timeout)
    self.left -= len(data)
    if 0 == self.left:
        self.closed = 1
        assert self.nl   == self.http.read(self.nlen)
        assert self.stop == self.http.read(self.stoplen)
    return data
def close(self, timeout=-1):
    if 0 == self.left:
        if self.closed:
            return
        assert self.nl   == self.http.read(self.nlen)
        assert self.stop == self.http.read(self.stoplen)
        self.closed = 1
        return
    if -1 == timeout:
        timeout = 16. + (len(self.left) >> 10)
    time0 = time()
    while self.left > 0:
        dummy = self.http.read(min(self.left, 8192), timeout)
        timeout -= time() - time0
        self.left -= len(dummy)
    assert self.nl   == self.http.read(self.nlen)
    assert self.stop == self.http.read(self.stoplen)
    self.closed = 1
nl, nlen = '\r\n', 2
filename = name = None
size = left = closed = 0'''

class multipart:
    def __init__(self, http, max_size=0x100000, timeout=-1):
        self.salt = salt = urandom(4)
        self.fields = fields = {}
        if 0 == http.left:
            return
        boundary = '--' + parse_header(
            http.environ['CONTENT_TYPE'])[1]['boundary']
        length = http.left
        if -1 == timeout:
            timeout = 16. + (max_size >> 10)
        time0 = time()
        data = http.readline(8192, timeout)
        timeout -= time() - time0
        if length - http.left > max_size:
            raise ValueError('length > %i' % max_size)
        if '\r\n' == data[-2:]:
            nlen = 2
            nl = '\r\n'
            self.next = next = boundary +   '\r\n'
            self.stop = stop = boundary + '--\r\n'
            self.nextlen = nextlen = len(self.next)
            self.stoplen = stoplen = len(self.stop)
        else:
            assert '\n' == data[-1]
            self.nl = nl = '\n'
            self.nlen = nlen = 1
            self.next = next = boundary +   '\n'
            self.stop = stop = boundary + '--\n'
        self.nextlen = nextlen = len(self.next)
        assert nextlen == len(data) and data == next
        self.stoplen = stoplen = len(self.stop)
        while not self.closed:
            environ = {}
            data = http.readline(8192, timeout)
            timeout -= time() - time0
            if length - http.left > max_size:
                raise ValueError('length > %i' % max_size)
            while 1:
                matchobj = is_header(data)
                if matchobj is None:
                    if '\r\n' == data or '\n' == data:
                        break
                    raise ValueError(
                        'invalid http header %r' % data)
                k, v = matchobj.groups()
                environ['HTTP_' + k.upper().replace('-', '_')] = v
                data = http.readline(8192, 24.)
            k, v = parse_header(
                environ['HTTP_CONTENT_DISPOSITION'])
            assert k.lower() == 'form-data'
            name = v['name']
            if 'filename' in v:
                self.http = http
                self.name = name
                self.filename = v['filename']
                self.size = self.left = http.left - nlen - stoplen
                break
            buf  = StringIO()
            data = http.readline(8192, timeout)
            timeout -= time() - time0
            while 1:
                if not data:
                    raise ValueError('bad request')
                elif len(data) == nextlen and data == next:
                    break
                elif len(data) == stoplen and data == stop:
                    self.closed = 1
                    break
                buf.write(data)
                data = http.readline(8192, timeout)
                timeout -= time() - time0
            buf.seek(-nlen, 2)
            assert nl == buf.read()
            size  = buf.tell() - nlen
            key   = salt + name
            value = fields.get(key)
            buf.seek(0)
            data = buf.read(size)
            if value is None:
                fields[key] = data
            elif isinstance(value, list):
                fields[key].append(data)
            else:
                fields[key] = [value, data]

    def __getitem__(self, key):
        return self.fields[self.salt+key]

    def __contains__(self, key):
        return self.salt + key in self.fields

    def has_key(self, key):
        return self.salt + key in self.fields

    def get(self, key, default=None):
        return self.fields.get(self.salt+key, default)

    exec(code)

class single:
    def __init__(self, http, max_size=8192, timeout=-1):
        if 0 == http.left:
            return
        boundary = '--' + parse_header(
            http.environ['CONTENT_TYPE'])[1]['boundary']
        length = http.left
        if -1 == timeout:
            timeout = 16. + (max_size >> 10)
        time0 = time()
        data = http.readline(8192, timeout)
        timeout -= time() - time0
        if length - http.left > max_size:
            raise ValueError('length > %i' % max_size)
        if '\r\n' == data[-2:]:
            nlen = 2
            nl = '\r\n'
            self.next = next = boundary +   '\r\n'
            self.stop = stop = boundary + '--\r\n'
            self.nextlen = nextlen = len(self.next)
            self.stoplen = stoplen = len(self.stop)
        else:
            assert '\n' == data[-1]
            self.nl = nl = '\n'
            self.nlen = nlen = 1
            self.next = next = boundary +   '\n'
            self.stop = stop = boundary + '--\n'
        self.nextlen = nextlen = len(self.next)
        assert nextlen == len(data) and data == next
        self.stoplen = stoplen = len(self.stop)
        environ = {}
        data = http.readline(8192, timeout)
        timeout -= time() - time0
        if length - http.left > max_size:
            raise ValueError('length > %i' % max_size)
        while 1:
            matchobj = is_header(data)
            if matchobj is None:
                if '\r\n' == data or '\n' == data:
                    break
                raise ValueError(
                    'invalid http header %r' % data)
            k, v = matchobj.groups()
            environ['HTTP_' + k.upper().replace('-', '_')] = v
            data = http.readline(8192, 24.)
        k, v = parse_header(
            environ['HTTP_CONTENT_DISPOSITION'])
        assert k.lower() == 'form-data'
        if 'filename' in v:
            self.filename = v['filename']
        self.http = http
        self.name = v['name']
        self.size = self.left = http.left - nlen - stoplen

    exec(code)

del code

import re
is_header  = re.compile(
    r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*\r?\n$'
        ).match
from time import time
from os import urandom
from cgi import parse_header
from cStringIO import StringIO
