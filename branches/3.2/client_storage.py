import _socket
from durus.storage_server import StorageServer
protocol = StorageServer.protocol
assert len(protocol) == 4
if ':' in DEFAULT_HOST:
    DEFAULT_ADDRESS = (_socket.AF_INET6,
        (DEFAULT_HOST, DEFAULT_PORT))
else:
    DEFAULT_ADDRESS = (_socket.AF_INET ,
        (DEFAULT_HOST, DEFAULT_PORT))
del _socket, StorageServer

class ClientStorage(Storage):
    def __init__(self, address=default_address):
        self.s = Socket(address)
        self.durus_id_pool = []
        self.durus_id_pool_size = 32
        self.begin()
        self.s.write('V' + protocol)
        server_protocol = self.s.read(4)
        if server_protocol != protocol:
            raise ProtocolError('Protocol version mismatch.')

    def new_durus_id(self):
        if not self.durus_id_pool:
            batch = self.durus_id_pool_size
            self.s.write('M' + chr(batch))
            self.durus_id_pool = split_durus_ids(
                self.s.read(batch << 3))
            self.durus_id_pool.reverse()
            assert len(self.durus_id_pool) == \
                   len(set(self.durus_id_pool))
        durus_id = self.durus_id_pool.pop()
        assert durus_id not in self.durus_id_pool
        self.transaction_new_durus_ids.append(durus_id)
        return durus_id

    def load(self, durus_id):
        self.s.write('L' + durus_id)
        return self._get_load_response(durus_id)

    def _get_load_response(self, durus_id):
        status = self.s.read(1)
        if status == STATUS_OKAY:
            pass
        elif status == STATUS_INVALID:
            raise ReadConflictError([durus_id])
        elif status == STATUS_KEYERROR:
            raise DurusKeyError(durus_id)
        else:
            raise ProtocolError(
                'status=%r, durus_id=%r' % (status, durus_id))
        n = unpack('>L', self.s.read(4))[0]
        record = self.s.read(n)
        return record

    def begin(self):
        self.records = {}
        self.transaction_new_durus_ids = []

    def store(self, durus_id, record):
        assert len(durus_id) == 8
        assert durus_id not in self.records
        self.records[durus_id] = record

    def end(self, handle_invalidations=None):
        self.s.write('C')
        n = unpack('>L', self.s.read(4))[0]
        durus_id_list = []
        if n != 0:
            packed_durus_ids = self.s.read(n << 3)
            durus_id_list = split_durus_ids(packed_durus_ids)
            try:
                handle_invalidations(durus_id_list)
            except ConflictError:
                self.transaction_new_durus_ids.reverse()
                self.durus_id_pool.extend(self.transaction_new_durus_ids)
                assert len(self.durus_id_pool) == \
                       len(set(self.durus_id_pool))
                self.begin()
                self.s.write(pack('>L', 0))
                raise
        tdata = []
        for durus_id, record in iteritems(self.records):
            tdata.append(pack('>L', 8 + len(record)))
            tdata.append(as_bytes(durus_id))
            tdata.append(record)
        tdata = join_bytes(tdata)
        self.s.write(pack('>L', len(tdata)))
        self.s.write(tdata)
        self.records.clear()
        if len(tdata) > 0:
            status = self.s.read(1)
            if status == STATUS_OKAY:
                pass
            elif status == STATUS_INVALID:
                raise WriteConflictError()
            else:
                raise ProtocolError(
                    'server returned invalid status %r' % status)

    def sync(self):
        self.s.write('S')
        n = unpack('>L', self.s.read(4))[0]
        if n == 0:
            packed_durus_ids = ''
        else:
            packed_durus_ids = self.s.read(n << 3)
        return split_durus_ids(packed_durus_ids)

    def pack(self):
        self.s.write('P')
        status = self.s.read(1)
        if status != STATUS_OKAY:
            raise ProtocolError(
                'server returned invalid status %r' % status)

    def bulk_load(self, durus_ids):
        durus_id_str = join_bytes(durus_ids)
        num_durus_ids, remainder = divmod(len(durus_id_str), 8)
        assert remainder == 0, remainder
        self.s.write('B' + pack('>L', num_durus_ids))
        self.s.write(durus_id_str)
        records = [self._get_load_response(durus_id) \
                      for durus_id in durus_ids]
        for record in records:
            yield record

    def close(self):
        self.s.write('.')
        self.s.close()

from socket_ import Socket
from struct import pack, unpack
from durus.storage import Storage
from durus.serialize import split_durus_ids
from durus.utils import as_bytes, iteritems, join_bytes
from durus.error import ProtocolError, DurusKeyError, \
    ConflictError, ReadConflictError, WriteConflictError
from durus.storage_server import DEFAULT_HOST, DEFAULT_PORT, \
    STATUS_OKAY, STATUS_INVALID, STATUS_KEYERROR
