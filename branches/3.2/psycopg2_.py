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
        connection1 = self.connection
        assert connection1.x_co is None, 'execute conflict'
        cursor_execute(self, operation, *args)
        connection1.wait()

    def executemany(self, operation, seq_of_parameters):
        connection1 = self.connection
        assert connection1.x_co is None, 'execute conflict'
        cursor_executemany(self, operation, seq_of_parameters)
        connection1.wait()

    def callproc(self, procname, *args):
        connection1 = self.connection
        assert connection1.x_co is None, 'execute conflict'
        cursor_callproc(self, procname, *args)
        connection1.wait()

class connection(_psycopg.connection):
    def __init__(self, dsn):
        connection_init(self, dsn, async=1)
        self.conn = conn1 = Conn()
        memmove(byref(conn1), conn0, sizeof_conn)
        conn1.r_io.fd   = conn1.w_io.fd   = self.fileno()
        conn1.r_io.data = conn1.w_io.data = self.id_ = \
                id_ = c_uint(id(self)).value
        objects[id_] = ref(self)
        self.wait()

    def __del__(self):
        try:
            del objects[self.id_]
        except KeyError:
            pass

    def begin(self):
        cursor = self.cursor()
        cursor.execute('BEGIN')

    def commit(self):
        cursor = self.cursor()
        cursor.execute('COMMIT')

    def rollback(self):
        cursor = self.cursor()
        cursor.execute('ROLLBACK')

    def wait(self):
        self.x_co = co = getcurrent()
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
            self.x_co = None

    cursor, x_co = cursor, None

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
    return _connect(dsn, connection_factory=connection)

class Conn(Structure):
    _fields_ = [('r_io', ev_io), ('w_io', ev_io)]

def callback(l, w, e):
    id_ = w.contents.data
    connection1  = objects[id_]()
    if connection1  is not None and \
       connection1.x_co is not None:
        try:
            connection1.x_co.switch()
        except:
            print_exc(file=sys.stderr)

def find_cb(type_):
    for k, v in type_._fields_:
        if 'cb' == k:
            return v

def get_conn0():
    conn1, buf = Conn(), create_string_buffer(sizeof_conn)
    conn1.r_io.cb = conn1.w_io.cb = c_callback
    conn1.r_io.events = EV__IOFDSET | EV_READ
    conn1.w_io.events = EV__IOFDSET | EV_WRITE
    memmove(buf, byref(conn1), sizeof_conn)
    return buf

objects = {}
sizeof_conn = sizeof(Conn)
c_callback  = find_cb(ev_io)(callback)
conn0 = get_conn0(); del get_conn0
cursor_execute     = _psycopg.cursor.execute
cursor_executemany = _psycopg.cursor.executemany
cursor_callproc    = _psycopg.cursor.callproc
connection_init    = _psycopg.connection.__init__
