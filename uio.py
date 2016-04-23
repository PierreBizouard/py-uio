import os
import re
from os import O_RDWR, O_CLOEXEC, O_NONBLOCK
from stat import S_ISCHR
from mmap import mmap
from pathlib import Path

class UioMap:
    def __init__( self, info ):
        self.index = int( re.fullmatch( r'map([0-9])', info.name ).group(1) )
        self.name = (info/'name').read_text().rstrip()
        self.address = int( (info/'addr').read_text(), 0 )
        self.size = int( (info/'size').read_text(), 0 )
        self._mem = None

class Uio:
    def fileno( self):
        return self._fd
    __index__ = fileno  # allows object to be passed to os.* calls

    def __init__( self, path, blocking = True ):
        flags = O_RDWR | O_CLOEXEC
        if not blocking:
            flags |= O_NONBLOCK # for irq_recv
        self._fd = os.open( path, flags )

        # check sysfs for available memory mappings
        dev = os.stat( self ).st_rdev
        dev = '{0}:{1}'.format( os.major(dev), os.minor(dev) )
        self._mappings = {}
        for m in map( UioMap, (Path('/sys/dev/char')/dev/'maps').iterdir() ):
            self._mappings[ m.index ] = m
            self._mappings[ m.name ] = m


    def map( self, m, offset=0, size=None ):
        m = self._mappings[ m ]

        if m._mem is None:
            m._mem = memoryview( mmap( self._fd, m.size, offset=m.index<<12 ) )
        m = m._mem

        if size is None:
            if offset is 0:
                return m
            return m[offset:]
        return m[offset:offset+size]

    def irq_enable( self ):
        os.write( self, b'\x01\x00\x00\x00' )

    def irq_disable( self ):
        os.write( self, b'\x00\x00\x00\x00' )

    # note: irq is disabled once received.  you need to reenable it
    #   - before handling it, if edge-triggered
    #   - after handling it, if level-triggered
    def irq_recv( self ):
        os.recv( self, 4 )