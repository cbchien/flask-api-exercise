from app import security, user_datastore, api_version
from database import db_session
from flask import request, jsonify
from flask_restful import Resource
from flask_security import Security, login_required, current_user
from models import Role, User
from utils import check_member_role, render_admin_client_structure, render_manager_client_structure, render_user_client_structure


class AddMemberRole(Resource):
    """Add authorization role to member\n
    return {message} and {data} 

    :param string email: Member's email as primary account identifier \n
    :param string role: Member's email as primary account identifier 
    """
    def post(self):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401

        if request.headers["Content-Type"] == "application/json":
            email = request.json["email"]
            role = request.json["role"]
            user = User.query.filter_by(email=email).first()
            # Change content render structure on role add
            if user and role == "admin":
                user_datastore.add_role_to_user(email, role)
                user.content = render_admin_client_structure()
                db_session.commit()
            if user and role == "manager":
                user_datastore.add_role_to_user(email, role)
                user.content = render_manager_client_structure()
                db_session.commit()
            return {
                "version": api_version,
                "message": "{} is assigned with {} role".format(email, role),
                "data": {
                    "email": email,
                    "roles": list(map(lambda x: x.name, user.roles)),
                    "content": user.content
                }
            }, 200
        return {
            "version": api_version,
            "message": "{} does not exist".format(email),
            "data": {}
        }, 404

class RemoveMemberRole(Resource):
    """Remove authorization role to member\n
    return {message} and {data} 

    :param string email: Member's email as primary account identifier \n
    :param string role: Member's email as primary account identifier 
    """
    def post(self):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401
        if request.headers["Content-Type"] == "application/json":
            email = request.json["email"]
            role = request.json["role"]
            user = User.query.filter_by(email=email).first()
            # Reset to basic view after removed from either admin or manager role
            if user and role == "admin" or user and role == "manager":
                user_datastore.add_role_to_user(email, role)
                user.content = render_user_client_structure()
                db_session.commit()
                user_datastore.remove_role_from_user(email, role)
                db_session.commit()
                return {
                    "version": api_version,
                    "message": "{} is removed from {} role".format(email, role),
                    "data": {
                        "email": email,
                        "roles": list(map(lambda x: x.name, user.roles)),
                        "content": user.content
                    }
                }, 200
            return {
                "version": api_version,
                "message": "{} does not exist".format(email),
                "data": {}
            }, 404

class GetAllRole(Resource):
    """Return a list of roles\n
    return {message} and {data} 
    """
    def get(self):
        all_roles = Role.query.order_by(Role.id).all()
        data = [role.as_dict() for role in all_roles]
        return {
            "version": api_version,
            "message": "Get all role",
            "data": {
                "roles": data
            }
        }, 200

class CreateNewRole(Resource):
    def post(self):
        # Set default role render structure
        admin_role = Role.query.filter_by(name="admin").first()
        admin_role.render_structure = render_admin_client_structure()
        manager_role = Role.query.filter_by(name="manager").first()
        manager_role.render_structure = render_manager_client_structure()
        user_role = Role.query.filter_by(name="user").first()
        user_role.render_structure = render_user_client_structure()
        db_session.commit()
        if request.headers["Content-Type"] == "application/json":
            new_role_name = request.json["new_role_name"]
            if Role.query.filter_by(name=new_role_name).first():
                return {
                    "version": api_version,
                    "message": "Role {} exist in database already".format(new_role_name),
                    "data": {
                        "role": new_role_name,
                        "render_structure": Role.query.filter_by(name=new_role_name).first().render_structure
                }
            }, 422
            user_datastore.find_or_create_role(new_role_name)
            db_session.commit()
            new_role = Role.query.filter_by(name=new_role_name).first()
            new_role.description = "this new role"
            new_role.render_structure = render_user_client_structure()
            db_session.commit()

            return {
                "version": api_version,
                "message": "Created new role: {}".format(new_role_name),
                "data": {
                    "role": new_role_name,
                    "render_structure": [new_role.render_structure]
                }
            }, 200
        return {
            "version": api_version,
            "message": "Check data input",
            "data": {}
        }, 404