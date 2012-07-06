from pyev import *
from weakref import ref
from traceback import print_exc
from greenlet import getcurrent, greenlet
from psycopg2 import *
from psycopg2 import _psycopg, __all__
from psycopg2._psycopg import _connect
from psycopg2.extensions import POLL_OK, POLL_WRITE, POLL_READ
from psycopg2 import _param_escape, InterfaceError, OperationalError

class cursor(_psycopg.cursor):
    def execute(self, operation, *args):
        cursor_execute(self, operation, *args)
        self.connection.wait()

    def executemany(self, operation, seq_of_parameters):
        cursor_executemany(self, operation, seq_of_parameters)
        self.connection.wait()

    def callproc(self, procname, *args):
        cursor_callproc(self, procname, *args)
        self.connection.wait()

    def mogrify(self, operation, *args):
        cursor_mogrify(self, operation, *args)
        self.connection.wait()

class connection(_psycopg.connection):
    def commit(self):
        connection_commit(self)
        self.wait()

    def rollback(self):
        connection_rollback(self)
        self.wait()

    def cursor(self, **kwargs):
        cursor1 = cursor(self, **kwargs)
        return cursor1

    def wait(self):
        co = getcurrent()
        conn1 = Conn()
        memmove(byref(conn1), conn0, sizeof_conn)
        conn1.r_io.fd   = conn1.w_io.fd   = self.fileno()
        conn1.r_io.data = conn1.w_io.data = \
            id_ = c_uint(id(co)).value
        objects[id_] = ref(co)
        try:
            while 1:
                state = self.poll()
                if POLL_OK == state:
                    break
                elif POLL_WRITE == state:
                    ev_io_start(EV_DEFAULT_UC, byref(conn1.w_io))
                    try:
                        co.parent.switch()
                    finally:
                        ev_io_stop(EV_DEFAULT_UC, byref(conn1.w_io))
                elif POLL_READ == state:
                    ev_io_start(EV_DEFAULT_UC, byref(conn1.r_io))
                    try:
                        co.parent.switch()
                    finally:
                        ev_io_stop(EV_DEFAULT_UC, byref(conn1.r_io))
                else:
                    raise OperationalError(
                        'poll() returned %s' % state)
        finally:
            del objects[id_]

def connect(dsn=None,
        database=None, user=None, password=None,
        host    =None, port=None, **kwargs):
    if dsn is None:
        items = []
        if database is not None:
            items.append(('dbname', database))
        if user is not None:
            items.append(('user', user))
        if password is not None:
            items.append(('password', password))
        if host is not None:
            items.append(('host', host))
        if port is not None and int(port) > 0:
            items.append(('port', port))
        items.extend(
            [(k, v) for (k, v) in kwargs.iteritems() if v is not None])
        dsn = " ".join(["%s=%s" % (k, _param_escape(str(v)))
            for (k, v) in items])
        if not dsn:
            raise InterfaceError('missing dsn and no parameters')
    return _connect(dsn, connection_factory=connection, async=True)

class Conn(Structure):
    _fields_ = [('r_io', ev_io), ('w_io', ev_io)]

code = '''def %(type)s_io_cb(l, w, e):
    id_ = w.contents.data
    conn = objects[id_]()
    if conn is not None and conn.x_co is not None:
        try:
            conn.x_co.switch()
        except:
            print_exc(file=sys.stderr)'''
for type_ in 'rw':
    exec(code % {'type': type_})

def find_cb(type_):
    for k, v in type_._fields_:
        if 'cb' == k:
            return v

for type_ in 'rw':
    exec('c_%s_io_cb = find_cb(ev_io)(%s_io_cb)' % tuple([type_] * 2))
del code, type_

def get_conn0():
    conn1, buf = Conn(), create_string_buffer(sizeof_conn)
    conn1.r_io.cb, conn1.w_io.cb = c_r_io_cb, c_w_io_cb
    conn1.r_io.events = EV__IOFDSET | EV_READ
    conn1.w_io.events = EV__IOFDSET | EV_WRITE
    memmove(buf, byref(conn1), sizeof_conn)
    return buf

objects = {}
sizeof_conn = sizeof(Conn)
conn0 = get_conn0(); del get_conn0
cursor_execute     = _psycopg.cursor.execute
cursor_executemany = _psycopg.cursor.executemany
cursor_callproc    = _psycopg.cursor.callproc
cursor_mogrify     = _psycopg.cursor.mogrify
connect_init       = _psycopg.connection.__init__
connect_commit     = _psycopg.connection.commit
connect_rollback   = _psycopg.connection.rollback
