from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext import mutable
import sqlalchemy.types as types
from sqlalchemy import Text
import json, pymysql
from db_pool import PooledDB

engine = create_engine('mysql://root@localhost/localwarehouse?charset=utf8', \
                       convert_unicode=True, encoding='utf-8')
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

class JsonEncodedDict(types.TypeDecorator):
    """Enables JSON storage by encoding and decoding on the fly."""
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is None:
            return '{}'
        else:
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return {}
        else:
            return json.loads(value)
            
mutable.MutableDict.associate_with(JsonEncodedDict)

def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    import models
    Base.metadata.create_all(bind=engine)


# DB Connection Pool From @Jimmy Wang
class ReturnModuleRequestException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'ReturnModuleRequestException: %s' % self.message

# DB Pool from Jimmy Wang
class Client(object):
    '''
    '''
    HOST = '' # IP or domain
    PORT = 3306
    USER = '' # db username
    PASSWD = '' # db password
    DB = '' # db name
    CHARSET= 'utf8'  
    #CHARSET= 'utf8mb4'
    CURSORCLASS = pymysql.cursors.DictCursor

    def __init__(self):
        self.pool = self._init_db_pool_session()

    def _init_db_pool_session(self):
        try:
            pool = PooledDB.PooledDB( pymysql, 
                             1,
                             host = self.HOST,
                             port = self.PORT,
                             user = self.USER,
                             passwd = self.PASSWD,
                             db = self.DB,
                             charset= self.CHARSET,
                             cursorclass= self.CURSORCLASS
                        )     
        except Exception as e:
            raise ReturnModuleRequestException("build connection pool error:{}".format(e))
        return pool


    def _requests(self,query,**params):
        '''
            :resp - return the change row , type is int 
            :response - return the select data
            :cur - dynamic cursor
        '''

        conn = self.pool.connection()
        cur = conn.cursor()

        resp = cur.execute(query)
        response = cur.fetchall()

        conn.commit()
        cur.close()
        conn.close()

        result = self._handle_response(resp,response)
        
        return result


    def _handle_response(self,resp,response):
        ''' Internal helper for handling API responses from the remote server.
            Raises the appropriate exceptions when necessary;
            If all the things is normal ,handler will returns the correct response.
            
            : response - match for datatable format
        '''
        data = dict()
        if response and isinstance(response, list):
            # response is not empty and type is list
            data["data"] = response
        elif isinstance(response, tuple):
            # response is empty and the empty will be tuple via cur.fetchall
            data["data"] = []
        else:
            # response isn't above condition
            raise ReturnModuleRequestException("Handling Response Format Error")

        if resp and isinstance(resp, int):
            data["resp"] = resp
        else:
            data["resp"] = int(-1)

        return data
