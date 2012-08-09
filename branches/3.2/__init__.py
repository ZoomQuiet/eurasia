revision = '$Revision$'

revision = revision[
           revision.find (':')  + 1 : \
           revision.rfind('$')].strip()

__version__ = '3.2:%s' % revision
