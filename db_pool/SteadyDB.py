import sys

__version__ = '1.2'

try:
    baseint = (int, long)
except NameError:  
    baseint = int
try:
    callable
except NameError:  
    def callable(obj):
        return any('__call__' in cls.__dict__ for cls in type(obj).__mro__)


class SteadyDBError(Exception):
    """General SteadyDB error."""


class InvalidCursor(SteadyDBError):
    """Database cursor is invalid."""


def connect(creator, maxusage=None, setsession=None,
        failures=None, ping=1, closeable=True, *args, **kwargs):

    return SteadyDBConnection(creator, maxusage, setsession,
        failures, ping, closeable, *args, **kwargs)


class SteadyDBConnection:
    """A "tough" version of connections."""

    version = __version__

    def __init__(self, creator, maxusage=None, setsession=None,
            failures=None, ping=1, closeable=True, *args, **kwargs):
        """Create a "tough" connection."""
        # basic initialization to make finalizer work
        self._con = None
        self._closed = True
        # proper initialization of the connection
        try:
            self._creator = creator.connect
            self._dbapi = creator
        except AttributeError:
            # try finding the DB module via the connection creator
            self._creator = creator
            try:
                self._dbapi = creator.dbapi
            except AttributeError:
                try:
                    self._dbapi = sys.modules[creator.__module__]
                    if self._dbapi.connect != creator:
                        raise AttributeError
                except (AttributeError, KeyError):
                    self._dbapi = None
        try:
            self._threadsafety = creator.threadsafety
        except AttributeError:
            try:
                self._threadsafety = self._dbapi.threadsafety
            except AttributeError:
                self._threadsafety = None
        if not callable(self._creator):
            raise TypeError("%r is not a connection provider." % (creator,))
        if maxusage is None:
            maxusage = 0
        if not isinstance(maxusage, baseint):
            raise TypeError("'maxusage' must be an integer value.")
        self._maxusage = maxusage
        self._setsession_sql = setsession
        if failures is not None and not isinstance(
                failures, tuple) and not issubclass(failures, Exception):
            raise TypeError("'failures' must be a tuple of exceptions.")
        self._failures = failures
        self._ping = ping if isinstance(ping, int) else 0
        self._closeable = closeable
        self._args, self._kwargs = args, kwargs
        self._store(self._create())

    def _create(self):
        """Create a new connection using the creator function."""
        con = self._creator(*self._args, **self._kwargs)
        try:
            try:
                if self._dbapi.connect != self._creator:
                    raise AttributeError
            except AttributeError:
                try:
                    mod = con.__module__
                except AttributeError:
                    mod = None
                while mod:
                    try:
                        self._dbapi = sys.modules[mod]
                        if not callable(self._dbapi.connect):
                            raise AttributeError
                    except (AttributeError, KeyError):
                        pass
                    else:
                        break
                    i = mod.rfind('.')
                    if i < 0:
                        mod = None
                    else:
                        mod = mod[:i]
                else:
                    try:
                        mod = con.OperationalError.__module__
                    except AttributeError:
                        mod = None
                    while mod:
                        try:
                            self._dbapi = sys.modules[mod]
                            if not callable(self._dbapi.connect):
                                raise AttributeError
                        except (AttributeError, KeyError):
                            pass
                        else:
                            break
                        i = mod.rfind('.')
                        if i < 0:
                            mod = None
                        else:
                            mod = mod[:i]
                    else:
                        self._dbapi = None
            if self._threadsafety is None:
                try:
                    self._threadsafety = self._dbapi.threadsafety
                except AttributeError:
                    try:
                        self._threadsafety = con.threadsafety
                    except AttributeError:
                        pass
            if self._failures is None:
                try:
                    self._failures = (self._dbapi.OperationalError,
                        self._dbapi.InternalError)
                except AttributeError:
                    try:
                        self._failures = (self._creator.OperationalError,
                            self._creator.InternalError)
                    except AttributeError:
                        try:
                            self._failures = (con.OperationalError,
                                con.InternalError)
                        except AttributeError:
                            raise AttributeError(
                                "Could not determine failure exceptions"
                                " (please set failures or creator.dbapi).")
            if isinstance(self._failures, tuple):
                self._failure = self._failures[0]
            else:
                self._failure = self._failures
            self._setsession(con)
        except Exception as error:
            # the database module could not be determined
            # or the session could not be prepared
            try:  # close the connection first
                con.close()
            except Exception:
                pass
            raise error  # reraise the original error again
        return con

    def _setsession(self, con=None):
        """Execute the SQL commands for session preparation."""
        if con is None:
            con = self._con
        if self._setsession_sql:
            cursor = con.cursor()
            for sql in self._setsession_sql:
                cursor.execute(sql)
            cursor.close()

    def _store(self, con):
        """Store a database connection for subsequent use."""
        self._con = con
        self._transaction = False
        self._closed = False
        self._usage = 0

    def _close(self):
        """Close the tough connection.

        You can always close a tough connection with this method
        and it will not complain if you close it more than once.

        """
        if not self._closed:
            try:
                self._con.close()
            except Exception:
                pass
            self._transaction = False
            self._closed = True

    def _reset(self, force=False):
        """Reset a tough connection.

        Rollback if forced or the connection was in a transaction.

        """
        if not self._closed and (force or self._transaction):
            try:
                self.rollback()
            except Exception:
                pass

    def _ping_check(self, ping=1, reconnect=True):
        """Check whether the connection is still alive using ping().

        If the the underlying connection is not active and the ping
        parameter is set accordingly, the connection will be recreated
        unless the connection is currently inside a transaction.

        """
        if ping & self._ping:
            try:  # if possible, ping the connection
                alive = self._con.ping()
            except (AttributeError, IndexError, TypeError, ValueError):
                self._ping = 0  # ping() is not available
                alive = None
                reconnect = False
            except Exception:
                alive = False
            else:
                if alive is None:
                    alive = True
                if alive:
                    reconnect = False
            if reconnect and not self._transaction:
                try:  # try to reopen the connection
                    con = self._create()
                except Exception:
                    pass
                else:
                    self._close()
                    self._store(con)
                    alive = True
            return alive

    def dbapi(self):
        """Return the underlying DB-API 2 module of the connection."""
        if self._dbapi is None:
            raise AttributeError("Could not determine DB-API 2 module"
                " (please set creator.dbapi).")
        return self._dbapi

    def threadsafety(self):
        """Return the thread safety level of the connection."""
        if self._threadsafety is None:
            if self._dbapi is None:
                raise AttributeError("Could not determine threadsafety"
                    " (please set creator.dbapi or creator.threadsafety).")
            return 0
        return self._threadsafety

    def close(self):
        """Close the tough connection.

        You are allowed to close a tough connection by default
        and it will not complain if you close it more than once.

        You can disallow closing connections by setting
        the closeable parameter to something false.  In this case,
        closing tough connections will be silently ignored.

        """
        if self._closeable:
            self._close()
        elif self._transaction:
            self._reset()

    def begin(self, *args, **kwargs):
        """Indicate the beginning of a transaction.

        During a transaction, connections won't be transparently
        replaced, and all errors will be raised to the application.

        If the underlying driver supports this method, it will be called
        with the given parameters (e.g. for distributed transactions).

        """
        self._transaction = True
        try:
            begin = self._con.begin
        except AttributeError:
            pass
        else:
            begin(*args, **kwargs)

    def commit(self):
        """Commit any pending transaction."""
        self._transaction = False
        try:
            self._con.commit()
        except self._failures as error:  # cannot commit
            try:  # try to reopen the connection
                con = self._create()
            except Exception:
                pass
            else:
                self._close()
                self._store(con)
            raise error  # reraise the original error

    def rollback(self):
        """Rollback pending transaction."""
        self._transaction = False
        try:
            self._con.rollback()
        except self._failures as error:  # cannot rollback
            try:  # try to reopen the connection
                con = self._create()
            except Exception:
                pass
            else:
                self._close()
                self._store(con)
            raise error  # reraise the original error

    def cancel(self):
        """Cancel a long-running transaction.

        If the underlying driver supports this method, it will be called.

        """
        self._transaction = False
        try:
            cancel = self._con.cancel
        except AttributeError:
            pass
        else:
            cancel()

    def ping(self, *args, **kwargs):
        """Ping connection."""
        return self._con.ping(*args, **kwargs)

    def _cursor(self, *args, **kwargs):
        """A "tough" version of the method cursor()."""
        # The args and kwargs are not part of the standard,
        # but some database modules seem to use these.
        transaction = self._transaction
        if not transaction:
            self._ping_check(2)
        try:
            if self._maxusage:
                if self._usage >= self._maxusage:
                    # the connection was used too often
                    raise self._failure
            cursor = self._con.cursor(*args, **kwargs)  # try to get a cursor
        except self._failures as error:  # error in getting cursor
            try:  # try to reopen the connection
                con = self._create()
            except Exception:
                pass
            else:
                try:  # and try one more time to get a cursor
                    cursor = con.cursor(*args, **kwargs)
                except Exception:
                    pass
                else:
                    self._close()
                    self._store(con)
                    if transaction:
                        raise error  # reraise the original error again
                    return cursor
                try:
                    con.close()
                except Exception:
                    pass
            if transaction:
                self._transaction = False
            raise error  # reraise the original error again
        return cursor

    def cursor(self, *args, **kwargs):
        """Return a new Cursor Object using the connection."""
        return SteadyDBCursor(self, *args, **kwargs)

    def __del__(self):
        """Delete the steady connection."""
        try:
            self._close()  # make sure the connection is closed
        except Exception:
            pass


class SteadyDBCursor:
    """A "tough" version of DB-API 2 cursors."""

    def __init__(self, con, *args, **kwargs):
        """Create a "tough" DB-API 2 cursor."""
        # basic initialization to make finalizer work
        self._cursor = None
        self._closed = True
        # proper initialization of the cursor
        self._con = con
        self._args, self._kwargs = args, kwargs
        self._clearsizes()
        try:
            self._cursor = con._cursor(*args, **kwargs)
        except AttributeError:
            raise TypeError("%r is not a SteadyDBConnection." % (con,))
        self._closed = False

    def setinputsizes(self, sizes):
        """Store input sizes in case cursor needs to be reopened."""
        self._inputsizes = sizes

    def setoutputsize(self, size, column=None):
        """Store output sizes in case cursor needs to be reopened."""
        self._outputsizes[column] = size

    def _clearsizes(self):
        """Clear stored input and output sizes."""
        self._inputsizes = []
        self._outputsizes = {}

    def _setsizes(self, cursor=None):
        """Set stored input and output sizes for cursor execution."""
        if cursor is None:
            cursor = self._cursor
        if self._inputsizes:
            cursor.setinputsizes(self._inputsizes)
        for column, size in self._outputsizes.items():
            if column is None:
                cursor.setoutputsize(size)
            else:
                cursor.setoutputsize(size, column)

    def close(self):
        """Close the tough cursor.

        It will not complain if you close it more than once.

        """
        if not self._closed:
            try:
                self._cursor.close()
            except Exception:
                pass
            self._closed = True

    def _get_tough_method(self, name):
        """Return a "tough" version of the given cursor method."""
        def tough_method(*args, **kwargs):
            execute = name.startswith('execute')
            con = self._con
            transaction = con._transaction
            if not transaction:
                con._ping_check(4)
            try:
                if con._maxusage:
                    if con._usage >= con._maxusage:
                        # the connection was used too often
                        raise con._failure
                if execute:
                    self._setsizes()
                method = getattr(self._cursor, name)
                result = method(*args, **kwargs)  # try to execute
                if execute:
                    self._clearsizes()
            except con._failures as error:  # execution error
                if not transaction:
                    try:
                        cursor2 = con._cursor(
                            *self._args, **self._kwargs)  # open new cursor
                    except Exception:
                        pass
                    else:
                        try:  # and try one more time to execute
                            if execute:
                                self._setsizes(cursor2)
                            method = getattr(cursor2, name)
                            result = method(*args, **kwargs)
                            if execute:
                                self._clearsizes()
                        except Exception:
                            pass
                        else:
                            self.close()
                            self._cursor = cursor2
                            con._usage += 1
                            return result
                        try:
                            cursor2.close()
                        except Exception:
                            pass
                try:  # try to reopen the connection
                    con2 = con._create()
                except Exception:
                    pass
                else:
                    try:
                        cursor2 = con2.cursor(
                            *self._args, **self._kwargs)  # open new cursor
                    except Exception:
                        pass
                    else:
                        if transaction:
                            self.close()
                            con._close()
                            con._store(con2)
                            self._cursor = cursor2
                            raise error  # raise the original error again
                        error2 = None
                        try:  # try one more time to execute
                            if execute:
                                self._setsizes(cursor2)
                            method2 = getattr(cursor2, name)
                            result = method2(*args, **kwargs)
                            if execute:
                                self._clearsizes()
                        except error.__class__:  # same execution error
                            use2 = False
                            error2 = error
                        except Exception as error:  # other execution errors
                            use2 = True
                            error2 = error
                        else:
                            use2 = True
                        if use2:
                            self.close()
                            con._close()
                            con._store(con2)
                            self._cursor = cursor2
                            con._usage += 1
                            if error2:
                                raise error2  # raise the other error
                            return result
                        try:
                            cursor2.close()
                        except Exception:
                            pass
                    try:
                        con2.close()
                    except Exception:
                        pass
                if transaction:
                    self._transaction = False
                raise error  # reraise the original error again
            else:
                con._usage += 1
                return result
        return tough_method

    def __getattr__(self, name):
        """Inherit methods and attributes of underlying cursor."""
        if self._cursor:
            if name.startswith(('execute', 'call')):
                # make execution methods "tough"
                return self._get_tough_method(name)
            else:
                return getattr(self._cursor, name)
        else:
            raise InvalidCursor

    def __del__(self):
        """Delete the steady cursor."""
        try:
            self.close()  # make sure the cursor is closed
        except Exception:
            pass
