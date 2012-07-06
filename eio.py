import ctypes.util
from cdefs import *
where  = ctypes.util.find_library('eio')
if where is None:
    import os, posixpath
    base = posixpath.abspath(posixpath.dirname(__file__))
    for fn in os.listdir(base):
        for suffix in ['so', 'dll', 'dylib']:
            if 'libeio.' + suffix == fn[:7+len(suffix)]:
                where = posixpath.join(base, fn)
                break
assert where, 'eio.py needs libeio installed.'
libeio = CDLL(where)

eio_ssize_t = c_ssize_t
eio_tstamp  = c_double
# eio_wd = c_void_p  # POINTER(eio_pwd)
eio_wd = POINTER(eio_pwd)
eio_pwd._fields_ = [('len', c_int), ('str', c_char_p)]
# if HAVE_AT in config.h:
#     eio_pwd._fields_.insert(0, ('fd', c_int))

class eio_pwd(Structure):
    pass

class eio_req(Structure):
    pass

eio_req_p = POINTER(eio_req)
eio_cb = CFUNCTYPE(c_int, eio_req_p)
eio_req._fields_ = [
    ('next'     , eio_req_p  ), ('wd'       , eio_wd    ),
    ('result'   , eio_ssize_t), ('offs'     , c_off_t   ),
    ('size'     , c_size_t   ), ('ptr1'     , c_void_p  ),
    ('ptr2'     , c_void_p   ), ('nv1'      , eio_tstamp),
    ('nv2'      , eio_tstamp ), ('type'     , c_int     ),
    ('int1'     , c_int      ), ('int2'     , c_long    ),
    ('int3'     , c_long     ), ('errorno'  , c_int     ),
    ('cancelled', c_uchar    ),  # if __i386 || __amd64
    ('flags'    , c_uchar    ), ('pri'      , c_char    ),
    ('data'     , c_void_p   ), ('finish'   , eio_cb    ),
    ('destory'  , c_void_p   ), ('feed'     , c_void_p  ),
                                 # EIO_REQ_MEMBERS
    ('grp'      , eio_req_p  ), ('grp_prev' , eio_req_p ),
    ('grp_next' , eio_req_p  ), ('grp_first', eio_req_p )]

def interface(name, restype, *argtypes):
    func = getattr(libeio, name)
    func.restype, func.argtypes = restype, argtypes
    globals()[name] = func

# INITIALISATION/INTEGRATION
interface('eio_init'  , c_int, CFUNCTYPE(None), CFUNCTYPE(None))
interface('eio_poll'  , c_int )
interface('eio_nreqs' , c_uint)
# CANCELLING REQUESTS
interface('eio_cancel', None, eio_req_p)
# POSIX API WRAPPERS
interface('eio_open', eio_req_p, c_char_p, c_int, c_mode_t,
    c_int, eio_cb, c_void_p)
interface('eio_truncate', eio_req_p, c_char_p, c_off_t,
    c_int, eio_cb, c_void_p)
interface('eio_chown', eio_req_p, c_char_p, c_int, c_int,
    c_int, eio_cb, c_void_p)
interface('eio_chmod', eio_req_p, c_char_p, c_mode_t,
    c_int, eio_cb, c_void_p)
interface('eio_mkdir', eio_req_p, c_char_p, c_mode_t,
    c_int, eio_cb, c_void_p)
interface('eio_rmdir', eio_req_p, c_char_p,
    c_int, eio_cb, c_void_p)
interface('eio_unlink', eio_req_p, c_char_p,
    c_int, eio_cb, c_void_p)
interface('eio_utime', eio_req_p, c_char_p, c_double, c_double,
    c_int, eio_cb, c_void_p)
interface('eio_mknod', eio_req_p, c_char_p, c_mode_t, c_off_t,
    c_int, eio_cb, c_void_p)
interface('eio_link', eio_req_p, c_char_p, c_char_p,
    c_int, eio_cb, c_void_p)
interface('eio_symlink', eio_req_p, c_char_p, c_char_p,
    c_int, eio_cb, c_void_p)
interface('eio_rename', eio_req_p, c_char_p, c_char_p,
    c_int, eio_cb, c_void_p)
interface('eio_mlock', eio_req_p, c_void_p, c_size_t,
    c_int, eio_cb, c_void_p)
interface('eio_close', eio_req_p, c_int,
    c_int, eio_cb, c_void_p)
interface('eio_sync',
    c_int, eio_cb, c_void_p)
interface('eio_fsync', eio_req_p, c_int,
    c_int, eio_cb, c_void_p)
interface('eio_fdatasync', eio_req_p, c_int,
    c_int, eio_cb, c_void_p)
interface('eio_futime', eio_req_p, c_int, c_double, c_double,
    c_int, eio_cb, c_void_p)
interface('eio_ftruncate', eio_req_p, c_int, c_off_t,
    c_int, eio_cb, c_void_p)
interface('eio_fchmod', eio_req_p, c_int, c_mode_t,
    c_int, eio_cb, c_void_p)
interface('eio_fchown', eio_req_p, c_int, c_int, c_int,
    c_int, eio_cb, c_void_p)
interface('eio_dup2', eio_req_p, c_int, c_int,
    c_int, eio_cb, c_void_p)
interface('eio_read',
    eio_req_p, c_int, c_void_p, c_size_t, c_off_t,
    c_int, eio_cb, c_void_p)
interface('eio_write',
    eio_req_p, c_int, c_void_p, c_size_t, c_off_t,
    c_int, eio_cb, c_void_p)
interface('eio_mlockall', eio_req_p, c_int,
    c_int, eio_cb, c_void_p)
interface('eio_msync', eio_req_p, c_void_p, c_size_t, c_int,
    c_int, eio_cb, c_void_p)
interface('eio_readlink', eio_req_p, c_char_p,
    c_int, eio_cb, c_void_p)
interface('eio_realpath', eio_req_p, c_char_p,
    c_int, eio_cb, c_void_p)
interface('eio_stat', eio_req_p, c_char_p,
    c_int, eio_cb, c_void_p)
interface('eio_lstat', eio_req_p, c_char_p,
    c_int, eio_cb, c_void_p)
interface('eio_fstat', eio_req_p, c_int,
    c_int, eio_cb, c_void_p)
interface('eio_statvfs', eio_req_p, c_char_p,
    c_int, eio_cb, c_void_p)
interface('eio_fstatvfs', eio_req_p, c_int,
    c_int, eio_cb, c_void_p)
# READING DIRECTORIES
interface('eio_readdir', eio_req_p, c_char_p, c_int,
    c_int, eio_cb, c_void_p)
# OS-SPECIFIC CALL WRAPPERS
if hasattr(libeio, 'eio_sendfile'):
    interface('eio_sendfile',
        eio_req_p, c_int, c_int, c_off_t, c_size_t,
        c_int, eio_cb, c_void_p)
if hasattr(libeio, 'eio_readahead'):
    interface('eio_readahead',
        eio_req_p, c_int, c_off_t, c_size_t,
        c_int, eio_cb, c_void_p)
if hasattr(libeio, 'eio_syncfs'):
    interface('eio_syncfs', eio_req_p, c_int,
        c_int, eio_cb, c_void_p)
if hasattr(libeio, 'eio_sync_file_range'):
    interface('eio_sync_file_range',
        eio_req_p, c_int, c_off_t, c_size_t, c_uint,
        c_int, eio_cb, c_void_p)
if hasattr(libeio, 'eio_fallocate'):
    interface('eio_fallocate',
        eio_req_p, c_int, c_mode_t, c_off_t, c_off_t,
        c_int, eio_cb, c_void_p)
# LIBEIO-SPECIFIC REQUESTS
interface('eio_mtouch', eio_req_p, c_char_p, c_size_t, c_int,
    c_int, eio_cb, c_void_p)
interface('eio_custom', eio_req_p, eio_req_p,
    c_int, eio_cb, c_void_p)
interface('eio_busy', eio_req_p, c_double,
    c_int, eio_cb, c_void_p)
interface('eio_nop', eio_req_p,
    c_int, eio_cb, c_void_p)
# GROUPING AND LIMITING REQUESTS
interface('eio_grp', eio_req_p, eio_cb, c_void_p)
interface('eio_grp_add', None, eio_req_p, eio_req_p)
interface('eio_grp_cancel', None, eio_req_p)
# OTHER
interface('eio_wd_open', eio_req, c_char_p,
    c_int, eio_cb, c_void_p)
interface('eio_wd_close', eio_wd,
    c_int, eio_cb, c_void_p)
interface('eio_seek', eio_req_p, c_int, c_off_t, c_int,
    c_int, eio_cb, c_void_p)
