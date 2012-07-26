code = '''def %(name)s(%(args)s timeout=-1):
    co  = getcurrent()
    id_ = c_uint(id(co)).value
    if -1 == timeout:%(s8)s
        objects[id_] = ref(co)
        req = %(eio_name)s(%(eio_args)s 0, c_callback, id_)
        try:
            co.parent.switch()
            contents = req.contents
            if contents.cancelled:
                raise default_cancelled%(s12)s
        finally:
            del objects[id_]
    else:%(s8)s
        objects[id_] = ref(co)
        timer1 = ev_timer()
        memmove(byref(timer1), timer0, sizeof_timer)
        timer1.at = timeout
        ev_timer_start(EV_DEFAULT_UC, byref(timer1))
        req = %(eio_name)s(%(eio_args)s 0, c_callback, id_)
        try:
            contents = req.contents
            try:
                co.parent.switch()
            except Timeout:
                if contents.cancelled:
                    raise default_cancelled
                eio_cancel(req)
                raise%(s12)s
        finally:
            ev_timer_stop(EV_DEFAULT_UC, byref(timer1))
            del objects[id_]
    return contents'''

def s_n(n, lines):
    lines = lines.rstrip()
    if not lines:
        return '\n'
    return ''.join(['\n%s%s' % (' '*n, s
        ) for s in lines.split('\n')])

for lines, args in [
    ('''\
st = cast(contents.ptr2, c_stat_p).contents
return pystatvfs(
    st.f_bsize , st.f_frsize, st.f_blocks,
    st.f_bfree , st.f_bavail, st.f_files , st.f_ffree,
    st.f_favail, st.f_flag  , st.f_namemax)''', [
        ('statvfs'  , 'path,'),
        ('fstatvfs' , 'fd,')]),
    ('''\
st = cast(contents.ptr2, c_stat_p).contents
return pystat(
    st.st_mode , st.st_ino  , st.st_dev  ,
    st.st_nlink, st.st_uid  , st.st_gid  , st.st_size,
    st.st_atime, st.st_mtime, st_ctime)''', [
        ( 'stat'    , 'path,'),
        ('lstat'    , 'path,'),
        ('fstat'    , 'fd,')]),
    ('''\
res  = contents.result
data = cast(contents.ptr2, POINTER(c_char*(res*0xfe))
    ).contents.raw
return data.split('\x00')''', [
        ('readdir'  , 'path, flags,')]),
    ('''\
return cast(contents.ptr2, c_char_p).value''', [
        ('readlink' , 'path')]),
    ('''\
return contents.result''', [
        ('open'     , 'path, flags, mode,'),
        ('truncate' , 'path, offset,' ),
        ('chown'    , 'path, uid, gid,'),
        ('chmod'    , 'path, mode,'),
        ('mkdir'    , 'path, mode,'),
        ('rmdir'    , 'path,'),
        ('unlink'   , 'path,'),
        ('utime'    , 'path, atime, mtime,'),
        ('mknod'    , 'path, mode, dev,'),
        ('link'     , 'path, new_path,'),
        ('symlink'  , 'path, new_path,'),
        ('rename'   , 'path, new_path,'),
        ('mlock'    , 'addr, length,'),
        ('close'    , 'fd'),
        ('sync'     , ''),
        ('fsync'    , 'fd,'),
        ('fdatasync', 'fd,'),
        ('futime'   , 'fd, atime, mtime,'),
        ('ftruncate', 'fd, offset,'),
        ('fchmod'   , 'fd, mode,'),
        ('fchown'   , 'fd, uid, gid,'),
        ('dup2'     , 'fd, fd2,'),
        ('mlockall' , 'flags,'),
        ('msync'    , 'addr, length, flags,'),
        ('realpath' , 'path,'),
        ('sendfile' , 'out_fd, in_fd, in_offset, length,'),
        ('readahead', 'fd, offset, length,'),
        ('syncfs'   , 'fd,'),
        ('sync_file_range', 'fd, offset, nbytes, flags,')
        ('fallocate', 'fd, mode, offset, len_,')
        ('mtouch'   , 'addr, length, flags,'),
        ('busy'     , 'delay,'),
        ('nop'      , '')])]:
    for name, args in args:
        exec code % {
            's12' : s_n(12, lines),
            's8'  : s_n(8 , ''),
            'name': name, 'eio_name': 'eio_' + name,
            'args': args, 'eio_args':  args }
exec code % {
    's12' :  s_n(12, 'return buf.raw'),
    's8'  : 'buf = create_string_buffer(length)',
    'name': 'read' , 'eio_name': 'eio_read',
    'args': 'fd, length, offset',
    'eio_args': 'fd, buf, length, offset,' }
exec code % {
    's12' : s_n(12, 'return contents.size'),
    's8'  : '',
    'name': 'write', 'eio_name': 'eio_write',
    'args': 'fd, data, offset',
    'eio_args': 'fd, buf, len(data), offset,'}
del args, code, name, lines, sn

import sys
from pyev import *
from os import strerror
from weakref import ref
from errno import ETIMEDOUT
from greenlet import getcurrent
from traceback import print_exc
from collections import namedtuple
from exceptions_ import Timeout, Cancelled

def callback(req):
    contents = req.contents
    id_   = contents.data
    back_ = objects[id_]()
    if back_ is None:
        return 0
    co = getcurrent()
    co.parent = back_.parent
    back_.parent = co
    errorno = contents.errorno
    if 0 == errorno:
        try:
            back_.switch()
        except:
            print_exc(file=sys.stderr)
    else:
        try:
            back_.throw(
                IOError,
                IOError(errorno, strerror(errorno)))
        except:
            print_exc(file=sys.stderr)
    return 0

def timer_cb(l, w, e):
    id_   = w.contents.data
    back_ = objects[id_]()
    if back_ is not None:
        co = getcurrent()
        co.parent = back_.parent
        back_.parent = co
        try:
            back_.throw(
                Timeout,
                Timeout(ETIMEOUT, 'operation timed out'))
        except:
            print_exc(file=sys.stderr)

def get_timer0():
    timer1 = ev_timer()
    buf = create_string_buffer(sizeof_timer)
    memset(byref(timer1), 0, sizeof_timer)
    timer1.cb = c_timer_cb
    memmove(buf, byref(timer1), sizeof_timer)
    return buf

for k, v in ev_timer._fields_:
    if 'cb' == k:
        c_timer_cb = v(timer_cb)

pystat = namedtuple('pystat', [
    'st_mode' , 'st_ino'  , 'st_dev'  ,
    'st_nlink', 'st_uid'  , 'st_gid'  , 'st_size',
    'st_atime', 'st_mtime', 'st_ctime'])

pystatvfs = namedtuple('pystatvfs', [
    'f_bsize' , 'f_frsize', 'f_blocks',
    'f_bfree' , 'f_bavail', 'f_files' , 'f_ffree',
    'f_favail', 'f_flag'  , 'f_namemax'])

objects = {}
c_callback = eio_cb(callback)
sizeof_timer = sizeof(ev_timer)
timer0 = get_timer0(); del get_timer0
default_cancelled = Cancelled()
