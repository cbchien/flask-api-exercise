from app import security, user_datastore, api_version
from database import db_session
from flask import request, jsonify
from flask_restful import Resource
from flask_security import Security, login_required, current_user
from models import Role, User
from utils import check_member_role, render_admin_client_structure, render_manager_client_structure, render_user_client_structure


class RoleList(Resource):
    """Return a list of roles\n
    return {message} and {data} 
    """
    def get(self):
        all_roles = Role.query.order_by(Role.id).all()
        data = [role.as_dict() for role in all_roles]
        return {
            "version": api_version,
            "message": "Get all roles",
            "data": data
        }, 200

    def post(self):
        # Set default role render structure
        # admin_role = Role.query.filter_by(name="admin").first()
        # admin_role.label = "Admin"
        # admin_role.render_structure = render_admin_client_structure()
        # manager_role = Role.query.filter_by(name="manager").first()
        # manager_role.label = "Manager"
        # manager_role.render_structure = render_manager_client_structure()
        # user_role = Role.query.filter_by(name="user").first()
        # user_role.label = "Normal User"
        # user_role.render_structure = render_user_client_structure()
        # db_session.commit()
        if "application/json" in request.headers["Content-Type"]:
            new_role_name = request.json["new_role_name"]
            render_structure = request.json["render_structure"]
            description = request.json["description"]
            label = request.json["label"]
            exist_role = Role.query.filter_by(name=new_role_name).first()
            if exist_role:
                return {
                    "version": api_version,
                    "message": "Role {} exist in database already".format(new_role_name),
                    "data": {
                        "role": exist_role.name,
                        "description": exist_role.description,
                        "label": exist_role.label,
                        "render_structure": exist_role.render_structure
                }
            }, 422
            user_datastore.find_or_create_role(new_role_name)
            db_session.commit()

            new_role = Role.query.filter_by(name=new_role_name).first()
            if description:
                new_role.description = description
            else:
                new_role.description = "A brand new role"

            if label:
                new_role.label = label
            else:
                new_role.label = new_role_name
            
            if render_structure:
                new_role.render_structure = render_structure
            else:
                new_role.render_structure = render_user_client_structure()
            db_session.commit()

            updated_new_role = Role.query.filter_by(name=new_role_name).first()

            return {
                "version": api_version,
                "message": "Created new role: {}".format(new_role_name),
                "data": {
                    "role": updated_new_role.name,
                    "label": updated_new_role.label,
                    "description": updated_new_role.description,
                    "render_structure": updated_new_role.render_structure
                    
                }
            }, 200
        return {
            "version": api_version,
            "message": "Check data input",
            "data": {}
        }, 404

class Roles(Resource):
    def get(self, role_id):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401

        role = Role.query.filter_by(id=role_id).first()
        data = role.as_dict()
        return {
            "version": api_version,
            "message": 'Role id: {} - {}'.format(role.id,role.label),
            "data": data
        }, 200    

    def put(self, role_id):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401

        if "application/json" in request.headers["Content-Type"]:
            description = request.json.get("description")
            label = request.json.get("label")
            render_structure = request.json.get("render_structure")
            
            role = Role.query.filter_by(id=role_id).first()
            if role:
                if description is not None:
                    role.description = description
                if label is not None:
                    role.label = label
                if render_structure is not None:
                    role.render_structure = render_structure
                db_session.commit()
                role_updated = Role.query.filter_by(id=role_id).first()
                return {
                    "version": api_version,
                    "message":"Update {}(id: {}) info".format(role_updated.label, role_updated.id),
                    "data": {
                        "id": role_updated.id,
                        "description": role_updated.description,
                        "label": role_updated.label,
                        "render_structure": role_updated.render_structure
                    }
                }, 200
        return {
                "version": api_version,
                "message":"Check header and data type",
                "data": {}
            }, 404



# Unused class
# class AddMemberRole(Resource):
#     """Add authorization role to member\n
#     return {message} and {data} 

#     :param string email: Member's email as primary account identifier \n
#     :param string role: Member's email as primary account identifier 
#     """
#     def post(self):
#         if check_member_role(["admin"], current_user.email) == False:
#             return {
#                 "message": 'Missing authorization to retrieve content',
#             }, 401

#         if "application/json" in request.headers["Content-Type"]:
#             email = request.json["email"]
#             role = request.json["role"]
#             return {
#                 "version": api_version,
#                 "message": "{} is assigned with {} role".format(email, role),
#                 "data": {
#                     "email": email,
#                     "roles": list(map(lambda x: x.name, user.roles))
#                 }
#             }, 200
#         return {
#             "version": api_version,
#             "message": "{} does not exist".format(email),
#             "data": {}
#         }, 404
# # Unused class
# class RemoveMemberRole(Resource):
#     """Remove authorization role to member\n
#     return {message} and {data} 

#     :param string email: Member's email as primary account identifier \n
#     :param string role: Member's email as primary account identifier 
#     """
#     def post(self):
#         if check_member_role(["admin"], current_user.email) == False:
#             return {
#                 "message": 'Missing authorization to retrieve content',
#             }, 401
#         if "application/json" in request.headers["Content-Type"]:
#             email = request.json["email"]
#             role = request.json["role"]
#             return {
#                 "version": api_version,
#                 "message": "{} is removed from {} role".format(email, role),
#                 "data": {
#                     "email": email,
#                     "roles": list(map(lambda x: x.name, user.roles))
#                 }
#             }, 200
#         return {
#             "version": api_version,
#             "message": "{} does not exist".format(email),
#             "data": {}
#         }, 404
