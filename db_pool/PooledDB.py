"""PooledDB - pooling for DB connections.

Implements a pool of steady, thread-safe cached connections 
to a database which are transparently reused.

    db = pool.connection()
    db = pool.connection(shareable=False)
    db = pool.dedicated_connection()
    pool.connection().cursor().execute(...)

    db = pool.connection()
    cur = db.cursor()
    cur.execute(...)
    res = cur.fetchone()
    cur.close()  # or del cur
    db.close()   # or del db
"""

from threading import Condition

from .SteadyDB import connect

__version__ = '1.2'

try:
    callable
except NameError:  # Python 3.0 or 3.1
    def callable(obj):
        return any('__call__' in cls.__dict__ for cls in type(obj).__mro__)


class PooledDBError(Exception):
    """General PooledDB error."""


class InvalidConnection(PooledDBError):
    """Database connection is invalid."""


class NotSupportedError(PooledDBError):
    """DB-API module not supported by PooledDB."""


class TooManyConnections(PooledDBError):
    """Too many database connections were opened."""


class PooledDB:
    """Pool for DB-API 2 connections.

    After you have created the connection pool, you can use
    connection() to get pooled, steady DB-API 2 connections.

    """

    version = __version__

    def __init__(self, creator,
            mincached=0, maxcached=0,
            maxshared=0, maxconnections=0, blocking=False,
            maxusage=None, setsession=None, reset=True,
            failures=None, ping=1,
            *args, **kwargs):
        
        try:
            threadsafety = creator.threadsafety
        except AttributeError:
            try:
                if not callable(creator.connect):
                    raise AttributeError
            except AttributeError:
                threadsafety = 2
            else:
                threadsafety = 0
        if not threadsafety:
            raise NotSupportedError("Database module is not thread-safe.")
        self._creator = creator
        self._args, self._kwargs = args, kwargs
        self._blocking = blocking
        self._maxusage = maxusage
        self._setsession = setsession
        self._reset = reset
        self._failures = failures
        self._ping = ping
        if mincached is None:
            mincached = 0
        if maxcached is None:
            maxcached = 0
        if maxconnections is None:
            maxconnections = 0
        if maxcached:
            if maxcached < mincached:
                maxcached = mincached
            self._maxcached = maxcached
        else:
            self._maxcached = 0
        if threadsafety > 1 and maxshared:
            self._maxshared = maxshared
            self._shared_cache = []  # the cache for shared connections
        else:
            self._maxshared = 0
        if maxconnections:
            if maxconnections < maxcached:
                maxconnections = maxcached
            if maxconnections < maxshared:
                maxconnections = maxshared
            self._maxconnections = maxconnections
        else:
            self._maxconnections = 0
        self._idle_cache = []  # the actual pool of idle connections
        self._lock = Condition()
        self._connections = 0
        # Establish an initial number of idle database connections:
        idle = [self.dedicated_connection() for i in range(mincached)]
        while idle:
            idle.pop().close()

    def steady_connection(self):
        """Get a steady, unpooled DB-API 2 connection."""
        return connect(self._creator,
            self._maxusage, self._setsession,
            self._failures, self._ping, True,
            *self._args, **self._kwargs)

    def connection(self, shareable=True):
        """Get a steady, cached DB-API 2 connection from the pool.

        If shareable is set and the underlying DB-API 2 allows it,
        then the connection may be shared with other threads.

        """
        if shareable and self._maxshared:
            self._lock.acquire()
            try:
                while (not self._shared_cache and self._maxconnections
                        and self._connections >= self._maxconnections):
                    self._wait_lock()
                if len(self._shared_cache) < self._maxshared:
                    # shared cache is not full, get a dedicated connection
                    try:  # first try to get it from the idle cache
                        con = self._idle_cache.pop(0)
                    except IndexError:  # else get a fresh connection
                        con = self.steady_connection()
                    else:
                        con._ping_check()  # check this connection
                    con = SharedDBConnection(con)
                    self._connections += 1
                else:  # shared cache full or no more connections allowed
                    self._shared_cache.sort()  # least shared connection first
                    con = self._shared_cache.pop(0)  # get it
                    while con.con._transaction:
                        # do not share connections which are in a transaction
                        self._shared_cache.insert(0, con)
                        self._wait_lock()
                        self._shared_cache.sort()
                        con = self._shared_cache.pop(0)
                    con.con._ping_check()  # check the underlying connection
                    con.share()  # increase share of this connection
                # put the connection (back) into the shared cache
                self._shared_cache.append(con)
                self._lock.notify()
            finally:
                self._lock.release()
            con = PooledSharedDBConnection(self, con)
        else:  # try to get a dedicated connection
            self._lock.acquire()
            try:
                while (self._maxconnections
                        and self._connections >= self._maxconnections):
                    self._wait_lock()
                # connection limit not reached, get a dedicated connection
                try:  # first try to get it from the idle cache
                    con = self._idle_cache.pop(0)
                except IndexError:  # else get a fresh connection
                    con = self.steady_connection()
                else:
                    con._ping_check()  # check connection
                con = PooledDedicatedDBConnection(self, con)
                self._connections += 1
            finally:
                self._lock.release()
        return con

    def dedicated_connection(self):
        """Alias for connection(shareable=False)."""
        return self.connection(False)

    def unshare(self, con):
        """Decrease the share of a connection in the shared cache."""
        self._lock.acquire()
        try:
            con.unshare()
            shared = con.shared
            if not shared:  # connection is idle,
                try:  # so try to remove it
                    self._shared_cache.remove(con)  # from shared cache
                except ValueError:
                    pass  # pool has already been closed
        finally:
            self._lock.release()
        if not shared:  # connection has become idle,
            self.cache(con.con)  # so add it to the idle cache

    def cache(self, con):
        """Put a dedicated connection back into the idle cache."""
        self._lock.acquire()
        try:
            if not self._maxcached or len(self._idle_cache) < self._maxcached:
                con._reset(force=self._reset)  # rollback possible transaction
                # the idle cache is not full, so put it there
                self._idle_cache.append(con)  # append it to the idle cache
            else:  # if the idle cache is already full,
                con.close()  # then close the connection
            self._connections -= 1
            self._lock.notify()
        finally:
            self._lock.release()

    def close(self):
        """Close all connections in the pool."""
        self._lock.acquire()
        try:
            while self._idle_cache:  # close all idle connections
                con = self._idle_cache.pop(0)
                try:
                    con.close()
                except Exception:
                    pass
            if self._maxshared:  # close all shared connections
                while self._shared_cache:
                    con = self._shared_cache.pop(0).con
                    try:
                        con.close()
                    except Exception:
                        pass
                    self._connections -= 1
            self._lock.notifyAll()
        finally:
            self._lock.release()

    def __del__(self):
        """Delete the pool."""
        try:
            self.close()
        except Exception:
            pass

    def _wait_lock(self):
        """Wait until notified or report an error."""
        if not self._blocking:
            raise TooManyConnections
        self._lock.wait()


# Auxiliary classes for pooled connections

class PooledDedicatedDBConnection:
    """Auxiliary proxy class for pooled dedicated connections."""

    def __init__(self, pool, con):
        """Create a pooled dedicated connection.

        pool: the corresponding PooledDB instance
        con: the underlying SteadyDB connection

        """
        # basic initialization to make finalizer work
        self._con = None
        # proper initialization of the connection
        if not con.threadsafety():
            raise NotSupportedError("Database module is not thread-safe.")
        self._pool = pool
        self._con = con

    def close(self):
        """Close the pooled dedicated connection."""
        # Instead of actually closing the connection,
        # return it to the pool for future reuse.
        if self._con:
            self._pool.cache(self._con)
            self._con = None

    def __getattr__(self, name):
        """Proxy all members of the class."""
        if self._con:
            return getattr(self._con, name)
        else:
            raise InvalidConnection

    def __del__(self):
        """Delete the pooled connection."""
        try:
            self.close()
        except Exception:
            pass


class SharedDBConnection:
    """Auxiliary class for shared connections."""

    def __init__(self, con):
        """Create a shared connection.

        con: the underlying SteadyDB connection

        """
        self.con = con
        self.shared = 1

    def __lt__(self, other):
        if self.con._transaction == other.con._transaction:
            return self.shared < other.shared
        else:
            return not self.con._transaction

    def __le__(self, other):
        if self.con._transaction == other.con._transaction:
            return self.shared <= other.shared
        else:
            return not self.con._transaction

    def __eq__(self, other):
        return (self.con._transaction == other.con._transaction
            and self.shared == other.shared)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        return other.__lt__(self)

    def __ge__(self, other):
        return other.__le__(self)

    def share(self):
        """Increase the share of this connection."""
        self.shared += 1

    def unshare(self):
        """Decrease the share of this connection."""
        self.shared -= 1


class PooledSharedDBConnection:
    """Auxiliary proxy class for pooled shared connections."""

    def __init__(self, pool, shared_con):
        """Create a pooled shared connection.

        pool: the corresponding PooledDB instance
        con: the underlying SharedDBConnection

        """
        # basic initialization to make finalizer work
        self._con = None
        # proper initialization of the connection
        con = shared_con.con
        if not con.threadsafety() > 1:
            raise NotSupportedError("Database connection is not thread-safe.")
        self._pool = pool
        self._shared_con = shared_con
        self._con = con

    def close(self):
        """Close the pooled shared connection."""
        # Instead of actually closing the connection,
        # unshare it and/or return it to the pool.
        if self._con:
            self._pool.unshare(self._shared_con)
            self._shared_con = self._con = None

    def __getattr__(self, name):
        """Proxy all members of the class."""
        if self._con:
            return getattr(self._con, name)
        else:
            raise InvalidConnection

    def __del__(self):
        """Delete the pooled connection."""
        try:
            self.close()
        except Exception:
            pass
