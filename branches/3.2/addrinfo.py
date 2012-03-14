import re
import _socket
from socket import getfqdn

def bind(address, sock_type):
    family, addr = addrinfo(address)
    if isinstance(addr, int):
        s = _socket.fromfd(
            addr, family, sock_type)
        s.setblocking(0)
        activated = 1
    else:
        s = _socket.socket(family, sock_type)
        s.setblocking(0)
        activated = 0
        if _socket.AF_INET6 == family and \
                       '::' == addr[0]:
            s.setsockopt(
                _socket.IPPROTO_IPV6,
                _socket.IPV6_V6ONLY, 0)
        s.setsockopt(
            _socket.SOL_SOCKET,
            _socket.SO_REUSEADDR, 1)
        s.bind(addr)
    server_address = s.getsockname()
    if isinstance(server_address, tuple):
        host, server_port = server_address
        server_name = getfqdn(host)
    else:
        server_port = server_name = None
    return {'server_address': server_address,
            'server_name'   : server_name,
            'server_port'   : server_port,
            'sock_family'   : family,
            'sock_type'     : sock_type,
            'activated'     : activated,
            's'             : s}

def addrinfo(address):
    if isinstance(address, str):
        _ = is_ipv4_with_port(address)
        if _:
            host, port = _.groups()
            return _socket.AF_INET , (host, int(port))
        _ = is_ipv6_with_port(address)
        if _:
            host, port = _.groups()
            return _socket.AF_INET6, (host, int(port))
        _ = is_domain_with_port(address)
        if _:
            host, port = _.groups()
            return _socket.AF_INET , (host, int(port))
        raise ValueError(address)
    family, addr = address
    if _socket.AF_INET == family:
        if isinstance(addr, tuple):
            host, port = addr
            port = int(port)
            if not ((is_ipv4  (host)   or \
                     is_domain(host)) and \
                  0 <= port < 65536):
                raise ValueError(address)
            return _socket.AF_INET, (host, port)
        else:
            return _socket.AF_INET,  addr
    if _socket.AF_INET6 == family:
        if isinstance(addr, tuple):
            host, port = addr
            port = int(port)
            if not ((is_ipv6  (host)   or \
                     is_domain(host)) and \
                  0 <= port < 65536):
                raise ValueError(address)
            return _socket.AF_INET6, (host, port)
        else:
            return _socket.AF_INET6,  addr
        if _socket.AF_UNIX == family:
            if isinstance(addr_0, int):
                return _socket.AF_UNIX, addr
            elif isinstance(addr, str):
                return _socket.AF_UNIX, addr
            else:
                raise ValueError(address)
        raise ValueError(address)

port = (r'6553[0-5]|655[0-2]\d|65[0-4]\d{2}|6[0-4]\d{3}|[1-5'
r']\d{4}|[1-9]\d{0,3}|0')
ipv4 = (r'(?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-4]'
r'|2[0-4]\d|1\d\d|[1-9]?\d)){3}')
ipv6 = (r'(?!.*::.*::)(?:(?!:)|:(?=:))(?:[0-9a-f]{0,4}(?:(?<'
r'=::)|(?<!::):)){6}(?:[0-9a-f]{0,4}(?:(?<=::)|(?<!::):)[0-9'
r'a-f]{0,4}(?:(?<=::)|(?<!:)|(?<=:)(?<!::):))')
domain = (r'(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z'
r']{2,6}')
is_ipv4   = re.compile(r'^\s*(%s)\s*$' % ipv4  ).match
is_ipv6   = re.compile(r'^\s*(%s)\s*$' % ipv6  ).match
is_domain = re.compile(r'^\s*(%s)\s*$' % domain).match
is_ipv4_with_port   = re.compile(
    r'^\s*(%s)\s*:\s*(%s)\s*$' % (ipv4, port)).match
is_ipv6_with_port   = re.compile(
    r'^\s*\[\s*(%s)\s*]\s*:\s*(%s)\s*$' % (ipv6, port)).match
is_domain_with_port = re.compile(
    r'^\s*(%s)\s*:\s*(%s)\s*$' % (domain, port)).match
