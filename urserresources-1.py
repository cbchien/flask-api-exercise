from app import security, user_datastore, api_version
import datetime, re, ast, json
from database import db_session
from flask import request, jsonify
from flask_restful import Resource
from flask_security import Security, login_required, current_user
from flask_security.utils import hash_password, verify_password, login_user, logout_user
from models import User, Role, Logging, Supplier
from utils import check_member_role, render_admin_client_structure, render_manager_client_structure, render_user_client_structure

class RegisterMember(Resource):
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
        if "application/json" in request.headers["Content-Type"]:
            email = request.json["email"]
            password = request.json["password"]
            username = request.json.get("username")
            current_login_ip = request.remote_addr
            
            ####### NEED TO UPDATE TO DYNAMICALLY SEARCH AND INDEX INPUT FROM CLIENT  ######
            # try:
            #     suppliers = request.json["suppliers"]
            # except:
            #     suppliers_list = Supplier.query.order_by(Supplier.email).all()
            #     data = [supplier.as_dict() for supplier in suppliers_list]
            #     print(data)
            suppliers_list = Supplier.query.order_by(Supplier.email).all()
            data = [supplier.as_dict() for supplier in suppliers_list]

            company = request.json.get("company")
            contact = request.json.get("contact")
            content = render_user_client_structure()

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
        elif len(password) < 6:
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
            suppliers = { "data": data },
            company = company,
            contact = contact,
            content = content,
            )
        db_session.commit()
        user_datastore.add_role_to_user(email, "user")
        db_session.commit()
        roles = user_datastore.find_user(email=email).roles
        user = User.query.filter_by(email=email).first()
        return {
                "version": api_version,
                "message": "User {} created.".format(email),
                "data": {
                    "email": "{}".format(email),
                    "roles":list(map(lambda x: x.name, roles)),
                    "suppliers": user.suppliers,
                    "company": company,
                    "contact": contact
                }
            }, 200

class ChangeMemberPassword(Resource):
    """Change a member's password \n
    return {message} and {data} 

    :param string email: Member's email as primary account identifier \n
    :param string current_password: User's current password \n
    :param string new_password: At least 6 digits \n
    :param array new_password_retype: Retype new password
    """
    def post(self):
        email = request.json["email"]
        current_password = request.json["current_password"]
        new_password = request.json["new_password"]
        new_password_retype = request.json["new_password_retype"]
        user = User.query.filter_by(email=email).first()
        if verify_password(current_password, user.password) and new_password == new_password_retype and len(current_password) > 5:
            user_datastore.find_user(email=email).password = hash_password(new_password)
            db_session.commit()
        return {
            "version": api_version,
            "message":"Member password for {} has been updated".format(email),
            "data": {
                "email": "{}".format(email),
            }
        }, 200

class ChangeMemberStatus(Resource):
    """Change a member's active status \n
    return {message} and {data} 

    :param string email: Member's email as primary account identifier
    """
    def post(self):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401

        email = request.json["email"]
        user = User.query.filter_by(email=email).first()
        if user:
            if user.active == 1:
                user.active = 0
            elif user.active == 0:
                user.active = 1
            db_session.commit()
            return {
                "version": api_version,
                "message":"Member status for {} is changed to {}".format(email, user.active),
                "data": {
                    "email": email,
                    "active": user.active
                }
            }, 200
        return {
                "version": api_version,
                "message":"Member {} does not exist".format(email),
                "data": {}
            }, 404

class EditMemberInfo(Resource):
    """Change a member's information \n
    return {message} and {data} 

    :param string username: Member's email as primary account identifier \n
    :param array suppliers: An array of suppilers' ID \n
    :param string contact: Member's phone number \n
    :param string company: The company the member belongs to
    """
    def post(self):
        if "application/json" in request.headers["Content-Type"]:
            email = request.json["email"]
            username = request.json.get("username")
            suppliers = request.json.get("suppliers")
            contact = request.json.get("contact")
            company = request.json.get("company")
            user = User.query.filter_by(email=email).first()
            if user:
                if username is not None:
                    user.username = username
                if company is not None:
                    user.company = company
                if contact is not None:
                    user.contact = str(contact)
                if suppliers is not None:
                    user.suppliers = str(suppliers)
                db_session.commit()
                return {
                    "version": api_version,
                    "message":"Update {} member info".format(email),
                    "data": {
                        "email": email,
                        "username": user.username,
                        "suppliers": {"data":user.suppliers},
                        "company": user.company,
                        "contact": user.contact
                    }
                }, 200
        return {
                "version": api_version,
                "message":"Check header and data type",
                "data": {}
            }, 404

class Member(Resource):
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
        if "application/json" in request.headers["Content-Type"]:
            email = request.json["email"]
            password = request.json["password"]
            username = request.json.get("username")
            current_login_ip = request.remote_addr
            
            ####### NEED TO UPDATE TO DYNAMICALLY SEARCH AND INDEX INPUT FROM CLIENT  ######
            # try:
            #     suppliers = request.json["suppliers"]
            # except:
            #     suppliers_list = Supplier.query.order_by(Supplier.email).all()
            #     data = [supplier.as_dict() for supplier in suppliers_list]
            #     print(data)
            suppliers_list = Supplier.query.order_by(Supplier.email).all()
            data = [supplier.as_dict() for supplier in suppliers_list]

            company = request.json.get("company")
            contact = request.json.get("contact")
            content = render_user_client_structure()

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
        elif len(password) < 6:
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
            suppliers = { "data": data },
            company = company,
            contact = contact,
            content = content,
            )
        db_session.commit()
        user_datastore.add_role_to_user(email, "user")
        db_session.commit()
        roles = user_datastore.find_user(email=email).roles
        user = User.query.filter_by(email=email).first()
        return {
                "version": api_version,
                "message": "User {} created.".format(email),
                "data": {
                    "email": "{}".format(email),
                    "roles":list(map(lambda x: x.name, roles)),
                    "suppliers": user.suppliers,
                    "company": company,
                    "contact": contact
                }
            }, 200

    """Return information for a member \n
    return {message} and {data} 

    :param string email: Member's email as primary account identifier \n
    """
    def get(self):
        if "application/json" in request.headers["Content-Type"]:
                    email = request.json["email"]
        user = User.query.filter_by(email=email).first()
        return {
                "version": api_version,
                "message": "User {}.".format(email),
                "data": {
                    "email": "{}".format(email),
                    "roles":list(map(lambda x: x.name, roles)),
                    "suppliers": user.suppliers,
                    "company": company,
                    "contact": contact
                }
            }, 200

    """Change a member's information \n
    return {message} and {data} 

    :param string username: Member's email as primary account identifier \n
    :param array suppliers: An array of suppilers' ID \n
    :param string contact: Member's phone number \n
    :param string company: The company the member belongs to
    """
    def put(self):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401

        if "application/json" in request.headers["Content-Type"]:
            email = request.json["email"]
            username = request.json.get("username")
            suppliers = request.json.get("suppliers")
            contact = request.json.get("contact")
            company = request.json.get("company")
            active = request.json.get("active")
            user = User.query.filter_by(email=email).first()
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
                db_session.commit()
                user_updated = User.query.filter_by(email=email).first()
                return {
                    "version": api_version,
                    "message":"Update {} member info".format(email),
                    "data": {
                        "email": email,
                        "username": user_updated.username,
                        "suppliers": {"data":user_updated.suppliers},
                        "company": user_updated.company,
                        "contact": user_updated.contact,
                        "active": user_updated.active
                    }
                }, 200
        return {
                "version": api_version,
                "message":"Check header and data type",
                "data": {}
            }, 404


            
class LoginMember(Resource):
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
                        "suppliers": suppliers_list,
                        "roles": list(map(lambda x: x.name, roles)),
                    },
                    "content": [user.content]
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

class LogoutMember(Resource):
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

class DisplayAllMember(Resource):
    """Display all member \n
    return {message} and {data} 
    """
    def get(self):
        all_user = User.query.filter_by(active=True).all()
        #one_user = User.query.filter_by(active=True).first()
        # order_user = User.query.order_by(User.username).all()
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

class DisplayMemberOpsHistory(Resource):