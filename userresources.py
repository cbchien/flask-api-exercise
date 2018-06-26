from app import security, user_datastore, api_version
import datetime, re, ast, json
from database import db_session
from flask import request, jsonify, session
from flask_restful import Resource
from flask_security import Security, login_required, current_user
from flask_security.utils import hash_password, verify_password, login_user, logout_user
from models import User, Role, Logging, Supplier
from utils import check_member_role, render_admin_client_structure, render_manager_client_structure, render_user_client_structure

class MemberChangePassword(Resource):
    """Change a member's password \n
    return {message} and {data} 

    :param string email: Member's email as primary account identifier \n
    :param string current_password: User's current password \n
    :param string new_password: At least 6 digits \n
    :param array new_password_retype: Retype new password
    """
    def post(self):
        email = request.json["email"]
        # For future use if members can change their own password
        # current_password = request.json["current_password"]
        new_password = request.json["new_password"]
        new_password_retype = request.json["new_password_retype"]
        user = User.query.filter_by(email=email).first()
        # if verify_password(current_password, user.password) and new_password == new_password_retype and len(current_password) > 5:
        if new_password == new_password_retype and len(new_password) > 5:
            user_datastore.find_user(email=email).password = hash_password(new_password)
            db_session.commit()
        return {
            "version": api_version,
            "message":"Member password for {} has been updated".format(email),
            "data": {
                "email": "{}".format(email),
            }
        }, 200

class MemberList(Resource):
    def get(self):
        all_user = User.query.order_by(User.id).all()
        #all_user = User.query.filter_by(active=True).all()
        #one_user = User.query.filter_by(active=True).first()
        #formated_all_user = list(map(lambda x: x.email, all_user))
        data = [user.as_dict() for user in all_user]
        for i in data:
            try:
                i["suppliers"] = ast.literal_eval(i["suppliers"])
            except:
                pass
        return {
            "version": api_version,
            "message": 'All active user',
            "data": data
        }, 200

    """Register for a new member \n
    return {message} and {data} 

    :param string email: Member's email as primary account identifier \n
    :param string password: At least 6 digits \n
    :param string username: A user defined username \n
    :param array suppliers: A array of supplier ID. Default N/A \n
    :param string company: The company that the member belongs to \n
    :param string contact: Member's contact number
    """
    def post(self):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401

        if "application/json" in request.headers["Content-Type"]:
            email = request.json["email"]
            print('\n\n\n\n',email,'\n\n\n\n')
            password = request.json["password"]
            username = request.json.get("username")
            current_login_ip = request.remote_addr
            company = request.json.get("company")
            contact = request.json.get("contact")
            address = request.json.get("address")
            roles = request.json.get("role")
            
            ####### NEED TO UPDATE TO DYNAMICALLY SEARCH AND INDEX INPUT FROM CLIENT  ######
            try:
                suppliers = request.json["suppliers"]
            except:
                # suppliers_list = Supplier.query.order_by(Supplier.email).all()
                # data = [supplier.as_dict() for supplier in suppliers_list]
                suppliers = []
                pass
            # suppliers_list = Supplier.query.order_by(Supplier.email).all()
            # data = [supplier.as_dict() for supplier in suppliers_list]

        if user_datastore.get_user(email):
            return {
                "version": api_version,
                "message": "User {} exist. Please login".format(email),
                "data": {}
            }, 422 
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return {
                "version": api_version,
                "message": "Please check your email format.",
                "data": {}
            }, 422
        elif len(password) < 6 or not password:
            return {
                "version": api_version,
                "message": "Password must be at least 6 characters long.",
                "data": {}
            }, 422 
   
        # create user and add user role as default
        user_datastore.create_user(
            email = email, 
            password = hash_password(password),
            username = username,
            current_login_ip = current_login_ip,
            suppliers = str(suppliers),
            company = company,
            contact = contact,
            address = address
            )
        db_session.commit()
        if roles and Role.query.filter_by(name=roles).first():
            user_datastore.add_role_to_user(email, roles)
        else:
            user_datastore.add_role_to_user(email, "user")
        db_session.commit()
        roles = user_datastore.find_user(email=email).roles
        user = User.query.filter_by(email=email).first()
        return {
                "version": api_version,
                "message": "User {} created.".format(email),
                "data": {
                    "id": user.id,
                    "email": user.email,
                    "roles":list(map(lambda x: x.name, roles)),
                    "suppliers": ast.literal_eval(user.suppliers),
                    "company": user.company,
                    "contact": user.contact,
                    "address": user.address,
                    "active": user.active
                }
            }, 200

class Member(Resource):
    """Display member info with given member id \n
    return {message} and {data} 
    """
    def get(self, member_id):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401

        user = User.query.filter_by(id=member_id).first()
        # order_user = User.query.order_by(User.username).all()
        data = user.as_dict()
        data["suppliers"] = ast.literal_eval(data["suppliers"])
        data["roles"] = list(map(lambda x: x.name, user.roles))
        return {
            "version": api_version,
            "message": 'User id: {} - {}'.format(user.id,user.email),
            "data": data
        }, 200

    """Change a member's information \n
    return {message} and {data} 

    :param string username: Member's email as primary account identifier \n
    :param array suppliers: An array of suppilers' ID \n
    :param string contact: Member's phone number \n
    :param string company: The company the member belongs to \n
    :param boolean: Member active status
    """
    def put(self, member_id):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401

        if "application/json" in request.headers["Content-Type"]:
            username = request.json.get("username")
            suppliers = request.json.get("suppliers")
            contact = request.json.get("contact")
            company = request.json.get("company")
            active = request.json.get("active")
            address = request.json.get("address")
            role = request.json.get("role")
            user = User.query.filter_by(id=member_id).first()
            if user:
                if username is not None:
                    user.username = username
                if company is not None:
                    user.company = company
                if contact is not None:
                    user.contact = str(contact)
                if suppliers is not None:
                    user.suppliers = str(suppliers)
                if active is not None:
                    user.active = active
                if address is not None:
                    user.address = address
                if role is not None and Role.query.filter_by(name=role).first():
                    role_list = list(map(lambda x: x.name, user.roles))
                    user_datastore.remove_role_from_user(user.email, str(role_list[0]))
                    db_session.commit()
                    user_datastore.add_role_to_user(user.email, role)
                db_session.commit()
                user_updated = User.query.filter_by(id=member_id).first()
                return {
                    "version": api_version,
                    "message":"Update {}(id: {}) info".format(user_updated.email, user_updated.id),
                    "data": {
                        "id": user_updated.id,
                        "email": user_updated.email,
                        "username": user_updated.username,
                        "suppliers": ast.literal_eval(user_updated.suppliers),
                        "company": user_updated.company,
                        "contact": user_updated.contact,
                        "address": user_updated.address,
                        "active": user_updated.active,
                        "role": list(map(lambda x: x.name, user_updated.roles))
                    }
                }, 200
        return {
                "version": api_version,
                "message":"Check header and data type",
                "data": {}
            }, 404
            
class MemberLogin(Resource):
    """Change a member's information \n
    return {message} and {data} 

    :param string email: Member's email as primary account identifier \n
    :param string password: Member's password
    """
    def post(self):
        if "application/json" in request.headers["Content-Type"]:
            email = request.json["email"]
            password = request.json["password"]
            user = user_datastore.find_user(email=email)
            if user and verify_password(password, user.password):
                login_user(user)
                roles = user.roles
                user.login_count += 1
                user.last_login_ip = user.current_login_ip
                user.current_login_ip = request.remote_addr
                user.last_login_at = user.current_login_at
                user.current_login_at = datetime.datetime.now()
                db_session.commit()
                try:
                    suppliers_list = user.suppliers
                except:
                    print("something is wrong")
                return {
                    "version": api_version,
                    "message": "Successfully logged in as {}".format(email),
                    "data": {
                        "email": email,
                        "username": user.username,
                        "company": user.company,
                        "contact": user.contact,
                        "address": user.address,
                        "suppliers": ast.literal_eval(suppliers_list),
                        "roles": list(map(lambda x: x.name, roles)),
                    }
                }, 200
            return {
                "version": api_version,
                "message": "Please check your log in credentials for {}".format(email),
                "data": {}
                }, 401
        else:
            return {
                "version": api_version,
                "message": "Please check your input type",
                "data": {}
            }, 404

class MemberLogout(Resource):
    """Logout member \n
    return {message} and {data} 
    """
    @login_required
    def post(self):
        logout_user()
        return {
                    "version": api_version,
                    "message": "Successfully logged out",
                    "data": {}
                }, 200

class OpsHistoryList(Resource):
    """Display all operation history
       Limited to 300 entries
    """
    def get(self):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401
        
        ops_history = Logging.query.order_by(Logging.timestampe.desc()).limit(300)
        data = [log.as_dict() for log in ops_history]
        return {
            "version": api_version,
            "message": 'Ops history',
            "data": data
        }, 200

class OpsHistory(Resource):
    """Display member's operation history \n
    return {message} and {data} 

    :param string email: Member's email as primary account identifier \n
    """
    def get(self, member_id):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401

        if "application/json" in request.headers["Content-Type"]:
            user = user_datastore.find_user(id=member_id)
            ops_history = Logging.query.filter_by(email=user.email).all()
            data = [log.as_dict() for log in ops_history]
            return {
                "version": api_version,
                "message": 'Ops history for {} (User id {})'.format(user.email, user.id),
                "data": data
            }, 200
        return {
            "version": api_version,
            "message": "Please check your input data type",
            "data": {}
        }, 404



