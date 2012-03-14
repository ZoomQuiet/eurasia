import sys
from tcp import serve_forever, exit, run, break_

if 3 == sys.version_info[0]:
    from httpd_py3 import Server, HTTPServer
else:
    from httpd_py2 import Server, HTTPServer
