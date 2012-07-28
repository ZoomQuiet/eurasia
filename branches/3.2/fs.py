code = '''def %(name1)s(%(args1)s timeout=-1):
    co  = getcurrent()
    id_ = c_uint(id(co)).value
    if -1 == timeout:%(prepare)s
        objects[id_] = ref(co)
        req = eio_%(name2)s(%(args2)s 0, c_callback, id_)
        try:
            co.parent.switch()
            contents = req.contents
            if contents.cancelled:
                raise default_cancelled%(result)s
        finally:
            del objects[id_]
    else:%(prepare)s
        objects[id_] = ref(co)
        timer1 = ev_timer()
        memmove(byref(timer1), timer0, sizeof_timer)
        timer1.at = timeout
        ev_timer_start(EV_DEFAULT_UC, byref(timer1))
        req = eio_%(name2)s(%(args2)s 0, c_callback, id_)
        try:
            contents = req.contents
            try:
                co.parent.switch()
            except Timeout:
                if contents.cancelled:
                    raise default_cancelled
                eio_cancel(req)
                raise%(result)s
        finally:
            ev_timer_stop(EV_DEFAULT_UC, byref(timer1))
            del objects[id_]
    return contents'''

prepare = '''
        buf = create_string_buffer(length)'''
result  = '''
            return buf.raw'''
exec code % {
    'name1' : 'read',
    'name2' : 'read',
    'args1' : 'fd,length,offset,',
    'args2' : 'fd,buf,length,offset,',
    'result':  result, 'prepare': prepare}
result = '''
            return contents.size'''
exec code % {
    'name1' : 'write',
    'name2' : 'write',
    'args1' : 'fd,data,offset,',
    'args2' : 'fd,data,len(data),offset,',
    'result':  result , 'prepare': ''}
result = '''
            return cast(contents.ptr2, c_char_p).value'''
name, args = 'readlink', 'path,'
exec code % {
    'name1' : name  , 'name2': name,
    'args1' : args  , 'args2': args,
    'result': result, 'prepare': ''}
result = '''
            res  = contents.result
            data = cast(contents.ptr2, POINTER(c_char*(res*0xfe))
                ).contents.raw
            return data.split('\\x00')'''
args = 'path,flags,'
exec code % {
    'name1' : 'readdir', 'name2'  : 'readdir',
    'args1' :  args    , 'args2'  :  args    ,
    'result':  result  , 'prepare': ''}
result = '''
            st = cast(contents.ptr2, c_stat_p).contents
            return pystat(
                st.st_mode , st.st_ino  , st.st_dev  ,
                st.st_nlink, st.st_uid  , st.st_gid  , st.st_size,
                st.st_atime, st.st_mtime, st.st_ctime)'''
for name, args in [( 'stat', 'path,'), ('lstat', 'path,'), ('fstat', 'fd,')]:
    exec code % {
        'name1' : name  , 'name2': name,
        'args1' : args  , 'args2': args,
        'result': result, 'prepare': ''}
result = '''
            st = cast(contents.ptr2, c_stat_p).contents
            return pystatvfs(
                st.f_bsize , st.f_frsize, st.f_blocks,
                st.f_bfree , st.f_bavail, st.f_files , st.f_ffree,
                st.f_favail, st.f_flag  , st.f_namemax)'''
for name, args in [('statvfs', 'path,'), ('fstatvfs', 'fd,')]:
    exec code % {
        'name1' : name  , 'name2': name,
        'args1' : args  , 'args2': args,
        'result': result, 'prepare': ''}
result  = '''
            return contents.result'''
for args in '''open path,flags,mode=0777:path,flags,mode|mkdir path,mode=0777:\
path,mode|mknod path,mode=0600,dev=0:path,mode,dev'''.split('|'):
    name, args = args.split(None, 1)
    args       = args.split( ':', 1)
    exec code % {
        'name1' : name,
        'name2' : name,
        'args1' : args[0]+',',
        'args2' : args[1]+',',
        'result': result, 'prepare': ''}
for args in '''truncate path,offset|chown path,uid,gid|chmod path,mode|rmdir p\
ath|unlink path|utime path,atime,mtime|link path,new_path|symlink path,new_pat\
h|rename path,new_path|mlock addr,length|close fd|sync|fsync fd|fdatasync fd|f\
utime fd,atime,mtime|ftruncate fd,offset|fchmod fd,mode|fchown fd,uid,gid|dup2\
 fd,fd2|mlockall flags|msync addr,length,flags|realpath path|sendfile out_fd,i\
n_fd,in_offset,length|readahead fd,offset,length|syncfs fd|sync_file_range fd,\
offset,nbytes,flags|fallocate fd,mode,offset,len_|mtouch addr,length,flags|bus\
y delay'''.split('|'):
    args = args.split(None, 1)
    if len(args) == 1:
        name, args = args[0], ''
    else:
        name, args = args[0], args[1] + ','
    exec code % {
        'name1' : name  , 'name2': name,
        'args1' : args  , 'args2': args,
        'result': result, 'prepare': ''}

del args, code, name, prepare, result
pread, pwrite, listdir = read, write, readdir

import sys
from pyev  import *
from pyeio import *
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

objects = {}
c_callback = eio_cb(callback)
default_cancelled = Cancelled()
sizeof_timer = sizeof(ev_timer)
timer0 = get_timer0(); del get_timer0
pystat = namedtuple('pystat', '''st_mode st_ino st_dev st_nlink st_uid st_gid \
st_size st_atime st_mtime st_ctime'''.split())
pystatvfs = namedtuple('pystatvfs', '''f_bsize f_frsize f_blocks f_bfree f_bav\
ail f_files f_ffree f_favail f_flag f_namemax'''.split())
