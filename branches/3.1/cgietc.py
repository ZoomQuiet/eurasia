from string import Template
from errno import EOVERFLOW
from json import dumps as json
from urllib import unquote_plus

def form(httpfile, max_size=1048576, timeout=-1):
    if 'CONTENT_LENGTH' in httpfile.environ:
        length = int(httpfile.environ['CONTENT_LENGTH'])
        if int(length) > max_size:
            httpfile.shutdown()
            raise ValueError(CONTENTLIMIT%(length, max_size))
        query = httpfile.environ['QUERY_STRING'].split('&') + \
                httpfile.read(length, timeout).split('&')
    else:
        query = httpfile.environ['QUERY_STRING'].split('&')
    dct = {}
    for item in query:
        try:
            key, value = item.split('=', 1)
            value = unquote_plus(value)
            try:
                if isinstance(dct[key], list):
                    dct[key].append(value)
                else:
                    dct[key] = [dct[key], value]
            except KeyError:
                dct[key] = value
        except ValueError:
            continue
    return dct

class browser(object):
    def __init__(self, httpfile, domain=None, timeout=-1):
        if not httpfile.headers_sent:
            httpfile._w_call(self._init, timeout, httpfile, domain)
        self.httpfile = httpfile

    def _init(self, httpfile, domain=None):
        httpfile.headers.update(COMETHEADERS)
        httpfile._start_response('200 OK', [])
        if domain is None:
            httpfile._sendall(COMETBEGIN1)
        else:
            httpfile._sendall(COMETBEGIN2%domain)

    def __call__(self, *args, **kwargs):
        self.httpfile.sendall(
            rpcstr(func=kwargs['func'],
                   args=', '.join(json(arg) for arg in args)),
            kwargs.get('timeout', -1))

    def __getattr__(self, func):
        return remotecall(self.httpfile, func)

    def __getitem__(self, name):
        return self.httpfile[name]

    def __contains__(self, name):
        return name in self.httpfile

    def javascript(self, code, timeout=-1):
        self.httpfile.sendall('<script>%s</script>'%code, timeout)

    def fileno(self):
        return self.httpfile.fileno()

    def shutdown(self):
        return self.httpfile.shutdown()

    def close(self, timeout=-1):
        if not self.closed:
            self.httpfile._w_call(self._close, timeout)
    closed = False

    def _close(self):
        self.httpfile._sendall(COMETEND)
        self.httpfile._close()

    def has_key(self, name):
        return name in self.httpfile

    def get_cookie(self):
        return self.httpfile.cookie
    cookie = property(get_cookie)

    def get_status(self):
        return self.httpfile.status
    status = property(get_status)
    del get_cookie, get_status

    code = '''\
    def get_${prop}(self):
        return self.httpfile.${prop}

    def set_${prop}(self, value):
        self.httpfile.${prop} = value

    ${prop} = property(get_${prop}, set_${prop})
    del get_${prop}, set_${prop}
    '''

    code = '\n'.join([s[4:] for s in code.split('\n')])
    for prop in 'request_uri', 'script_name', 'path_info', 'query_string':
        exec(code.replace('${prop}', prop))
    del code, prop, s

class remotecall(object):
    def __init__(self, httpfile, func):
        self.__func = func
        self.__httpfile = httpfile

    def __getattr__(self, func):
        return remotecall(self.__httpfile,
            '%s.%s'%(self.__func, func))

    def __getitem__(self, func):
        if isinstance(func, unicode):
            return remotecall(self.__httpfile,
                '%s[%s]'%(self.__func, repr(func)[1:]))
        return remotecall(self.__httpfile,
            '%s[%s]'%(self.__func, repr(func)))

    def __call__(self, *args, **kwargs):
        self.__httpfile.sendall(
            rpcstr(func=self.__func,
                   args=', '.join(json(arg) for arg in args)),
            kwargs.get('timeout', -1))

def parse_header(line):
    plist = [x.strip() for x in line.split(';')]
    key = plist.pop(0).lower()
    pdict = {}
    for p in plist:
        i = p.find('=')
        if i >= 0:
            name = p[:i].strip().lower()
            value = p[i+1:].strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
                value = value.replace('\\\\', '\\').replace('\\"', '"')
            pdict[name] = value
    return key, pdict

class simpleupload(dict):
    def __init__(self, httpfile, timeout=-1):
        pass

Form, Browser = form, browser
__all__ = 'form Form browser Browser'.split()
COMETBEGIN0 = ('<html>'
    '<head>'
        '<meta http-equiv="Pragma" content="no-cache">'
        '<meta http-equiv="Content-Type" content="text/html">'
    '</head>'
    '<body>'
    '<script>'
        '%s'
        'var comet=window.parent?parent:window;'
        'comet.escape&&comet.escape("IE");'
    '</script>')
COMETEND    = '</body></html>'
COMETBEGIN2 = COMETBEGIN0%'document.domain="%s";'
COMETBEGIN1 = COMETBEGIN0%''
COMETHEADERS = {'Content-Type': 'text/html; charset=UTF-8',
    'Pragma' : 'no-cache', 'Cache-Control': 'no-cache, must-revalidate',
    'Expires': 'Mon, 26 Jul 1997 05:00:00 GMT'}
CONTENTLIMIT = 'the content length of %i is larger than the limit of %i'
rpcstr = Template('<script>comet.${func}(${args});</script>').substitute
