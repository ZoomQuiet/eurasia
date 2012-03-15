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
eio_wd      = c_void_p  # POINTER(eio_pwd)
eio_tstamp  = c_double

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

interface('eio_init'  , c_int, CFUNCTYPE(None), CFUNCTYPE(None))
interface('eio_poll'  , c_int )
interface('eio_nreqs' , c_uint)

interface('eio_fsync', eio_req_p, c_int, c_int, eio_cb, c_void_p)
interface('eio_close', eio_req_p, c_int, c_int, eio_cb, c_void_p)
interface('eio_read' , eio_req_p, c_int, c_void_p, c_size_t, c_off_t,
    c_int, eio_cb, c_void_p)
interface('eio_write', eio_req_p, c_int, c_void_p, c_size_t, c_off_t,
    c_int, eio_cb, c_void_p)
interface('eio_ftruncate', eio_req_p, c_int, c_off_t,
    c_int, eio_cb, c_void_p)
interface('eio_open', eio_req_p, c_char_p, c_int, c_mode_t,
    c_int, eio_cb, c_void_p)
interface('eio_truncate', eio_req_p, c_char_p, c_off_t,
    c_int, eio_cb, c_void_p)
interface('eio_mkdir', eio_req_p, c_char_p, c_mode_t,
    c_int, eio_cb, c_void_p)
interface('eio_rmdir' , eio_req_p, c_char_p, c_int, eio_cb, c_void_p)
interface('eio_unlink', eio_req_p, c_char_p, c_int, eio_cb, c_void_p)
interface('eio_rename', eio_req_p, c_char_p, c_char_p,
    c_int, eio_cb, c_void_p)

interface('eio_cancel', None, eio_req_p)
