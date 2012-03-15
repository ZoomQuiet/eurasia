import sys
if 3 == sys.version_info[0]:
    from httpd43 import *
else:
    from httpd42 import *
