def template(text, environ={}):
    code = compile(text)
    module = new_module('<string>')
    module.__dict__.update(environ)
    try:
        exec code in module.__dict__
    except (SyntaxError, IndentationError), e:
        p = e.lineno - 7
        lines = code.split('\n')
        if  p < 0:
            p = 0
        e.msg = '%s\n[ Template ]\n\n%s' % (
            e.msg, '\n'.join(lines[p:e.lineno]))
        raise e
    return module

def compile(code):
    result = deque()
    extbuf = deque()
    lv = lv_if = lv_for = lv_def = call_lv = nil = 0
    for type_, data in tokenize(code):
        if   type_ == TEXT:
            extbuf.append(u"r'''%s'''" % data)
            continue
        elif type_ == EXPR:
            extbuf.append(u'_str_(%s)'   % data)
            continue
        if extbuf:
            if lv_def > 0:
                line = u'writelines((%s, ))' % (
                    u', '.join(extbuf))
                result.append(indent*lv + line)
                nil = 0
            extbuf = deque()
        if   type_ == IF:
            result.append(indent*lv + data)
            lv += 1
            lv_if += 1
            nil = 1
        elif type_ == ELIF:
            lv -= 1
            lv_if -= 1
            if lv_if == -1:
                raise SyntaxError(
                    u'invalid syntax %r' % data)
            result.append(indent*lv + data)
            lv += 1
            lv_if += 1
            nil = 1
        elif type_ == FOR:
            result.append(indent*lv + data)
            lv += 1
            lv_for += 1
            nil = 1
        elif type_ == ENDIF:
            if nil:
                result.append(indent*lv + 'pass')
            lv -= 1
            lv_if -= 1
            nil = 0
            if lv_if == -1:
                raise SyntaxError(
                    u'invalid syntax %r' % data)
        elif type_ == ENDFOR:
            if nil:
                result.append(indent*lv + 'pass')
            lv -= 1
            lv_for -= 1
            nil = 0
            if lv_for == -1:
                raise SyntaxError(
                    u'invalid syntax %r' % data)
        elif type_ == PY:
            base = None
            nil = p = 0
            for line in data.split(u'\n'):
                g1, g2 = get_base(line).groups()
                if not g2:
                    continue
                if base is None:
                    base = g1
                    p = len(g1)
                    result.append(indent*lv + g2)
                elif g1[:p] == base:
                    result.append(indent*lv + line[p:])
                else:
                    raise IndentationError(
                        u'unexpected indent %r' % line)
        elif type_ == DEF:
            result.append(u'%sdef %s:' % (
                indent*lv, data))
            lv += 1
            lv_def += 1
            line = (u'_out_ = []; '
                u'write = _out_.append; '
                u'writelines = _out_.extend')
            result.append(indent*lv + line)
        elif type_ == ENDDEF:
            if lv_if  != 0:
                raise SyntaxError('lost "%endif"')
            if lv_for != 0:
                raise SyntaxError('lost "%endfor"')
            line = u'return \'\'.join(_out_)'
            result.append(indent*lv + line)
            lv -= 1
            lv_def -= 1
            nil = 0
            if lv_def == -1:
                raise SyntaxError(
                    u'invalid syntax %r' % data)
    if lv_if  != 0:
        raise SyntaxError('lost "%endif"')
    if lv_for != 0:
        raise SyntaxError('lost "%endfor"')
    if lv_def != 0:
        raise SyntaxError('lost "</%def>"')
    result.appendleft(header)
    return u'\n'.join(result).encode('utf-8')

def tokenize(code):
    code = unicode(code, 'utf-8')
    matched = search(code)
    buf = deque()
    p = 0
    while matched is not None:
        text = code[p:matched.start()]
        if text:
            buf.append(text)
        g1, g2, g3, g4, g5, g6 = matched.groups()
        if g1 is not None:
            buf.append(g1[0])
            p = matched.end()
            matched = search(code, p)
            continue
        if buf:
            yield (TEXT, u''.join(buf))
            buf = deque()
        if   g2 is not None:
            yield (EXPR, g2)
        elif g3 is not None:
            matched1 = get_ctrl(g3)
            if matched1 is None:
                raise SyntaxError(g3)
            g11, g12, g13, g14, g15 = \
                matched1.groups()
            if   g11 is not None:
                yield (IF    , g3)
            elif g12 is not None:
                yield (ELIF  , g3)
            elif g13 is not None:
                yield (FOR   , g3)
            elif g14 is not None:
                yield (ENDIF , g3)
            else:
                yield (ENDFOR, g3)
        elif g4 is not None:
            yield (DEF, eval(g4))
        elif g5 is not None:
            yield (ENDDEF, None)
        else:
            yield (PY, g6)
        p = matched.end()
        matched = search(code, p)
    text = code[p:]
    if text:
        buf.append(text)
    if buf:
        yield (TEXT, u''.join(buf))

indent = u'\t'
header = u'''\
from json import dumps
write = writelines = lambda *args: None
def _str_(obj):
    if   isinstance(obj, basestring):
        return obj
    elif isinstance(obj, (list, dict, tuple)):
        return dumps(obj)
    try:
        return dumps(list(obj))
    except TypeError:
        pass
    try:
        return str (obj)
    except:
        return repr(obj)'''
TEXT, EXPR, IF, ELIF, ENDIF, FOR, ENDFOR, \
        DEF, ENDDEF, PY = range(10)
string = ur'(?:"(?:(?:\\\\)?(?:\\")?[^"]?)*")?' + \
         ur"(?:'(?:(?:\\\\)?(?:\\')?[^']?)*')?"
head, tail = ur'(?:\r?\n[ \t]*)?', ur'(?:[ \t\r]*\n)?'
import re
search = re.compile(u'|'.join([
    ur'(\$\$|%%)',
    ur'\${((?:%s[^}]?)*)}' % (string),
    ur'%s%%(.*)(?:\n|$)%s' % (head, tail),
    ur'%s<%%def\s+(?:name\s*=\s*)?(%s)\s*>%s' % (
                        head, string, tail),
    ur'%s<\s*/\s*%%(def)>%s' % (head, tail),
    ur'%s<%%((?:%s[^%%]?(?:%%(?!>))?)*)%%>%s' % (
                        head, string, tail)
]), re.M|re.I|re.U).search
get_base = re.compile(ur'^([ \t]*)(.*)',
    re.I|re.U).match
get_ctrl = re.compile((
    ur'^[ \t]*(?:(if[ \t])|(elif[ \t])|(for[ \t])|'
    ur'(endif)|(endfor))'), re.I|re.U).match
from imp import new_module
from collections import deque
