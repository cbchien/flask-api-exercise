import datetime, json
from database import Base, JsonEncodedDict
from flask_security import UserMixin, RoleMixin
from sqlalchemy import create_engine
from sqlalchemy.orm import relationship, backref
from sqlalchemy import Boolean, DateTime, Column, Integer, \
                       String, ForeignKey
from werkzeug.security import generate_password_hash, check_password_hash

class RolesUsers(Base):
    __tablename__ = 'roles_users'
    id = Column(Integer(), primary_key=True)
    user_id = Column('user_id', Integer(), ForeignKey('user.id'))
    role_id = Column('role_id', Integer(), ForeignKey('role.id'))

class Role(Base, RoleMixin):
    __tablename__ = 'role'
    id = Column(Integer(), primary_key=True)
    name = Column(String(80), unique=True)
    description = Column(String(255))
    label = Column(String(255))
    render_structure = Column(JsonEncodedDict)

    # Unused __init__. Use Flask-Security find_or_create_role()
    # def __init__(self, name):
    #     self.name = name
    #     self.description = description
    #     self.render_structure = render_structure
    
    def __repr__(self):
        return '%r' %(self.id)
    
    def as_dict(self):
        data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        return data
        
class User(Base, UserMixin):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True)
    username = Column(String(255))
    password = Column(String(255))
    last_login_at = Column(DateTime(), default=datetime.datetime.now())
    current_login_at = Column(DateTime(), default=datetime.datetime.now())
    last_login_ip = Column(String(100))
    current_login_ip = Column(String(100))
    login_count = Column(Integer, default=1)
    active = Column(Boolean(), default=1)
    contact = Column(String(100))
    suppliers = Column(JsonEncodedDict) #The compnaies the member handles 
    company = Column(String(255)) #The compnay the member works for 
    content = Column(JsonEncodedDict)
    confirmed_at = Column(DateTime(), default=datetime.datetime.now()) # Saved for future Approval functionality
    roles = relationship('Role', secondary='roles_users',
                         backref=backref('user', lazy='dynamic'))
    
    def __repr__(self):
        return '%r %r' %(self.email, self.login_count)

    def as_dict(self):
        data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        del(data["password"])
        del(data["confirmed_at"])
        data["last_login_at"] = str(data["last_login_at"])
        data["current_login_at"] = str(data["current_login_at"])
        data["roles"] = list(map(lambda x: x.name, self.roles)),
        return data

class Logging(Base):
    __tablename__ = 'logging'
    id = Column(Integer, primary_key=True)
    email = Column(String(255))
    request_remote_addr = Column(String(255))
    method = Column(String(255))
    scheme = Column(String(255))
    full_path = Column(String(100))
    status = Column(String(100))
    message = Column(String(255))
    timestampe = Column(DateTime(), default=datetime.datetime.now())

    def __init__(self, email, request_remote_addr, method, scheme, full_path, status, message):
        self.email = email
        self.request_remote_addr = request_remote_addr
        self.method = method
        self.scheme = scheme
        self.full_path = full_path
        self.status = status
        self.message = message

    def as_dict(self):
        data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        data["timestampe"] = str(data["timestampe"])
        return data

    def __repr__(self):
        return '%r %r %r %r %r' %(self.request_remote_addr, self.method, self.scheme, self.full_path, self.status)

class Supplier(Base):
    __tablename__ = 'supplier'
    id = Column(Integer, primary_key=True)
    supplier_company = Column(String(255))
    representitive = Column(String(255))
    email = Column(String(255))
    contact = Column(String(255))
    created_at = Column(DateTime(), default=datetime.datetime.now())

    def __init__(self, supplier_company, representitive, email, contact):
        self.supplier_company = supplier_company
        self.representitive = representitive
        self.email = email
        self.contact = contact

    def as_dict(self):
        data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        del(data["created_at"])
        return data