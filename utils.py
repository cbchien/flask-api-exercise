from flask_security import current_user
from app import user_datastore
import datetime
import ast

def check_member_role(roles, email):
    """Check a member's viewing authorization.
    return Boolean
    
    :param roles: A list of acceptable roles
    :param email: Email of the person who will perform the action
    """
    required_roles = roles
    user_roles = user_datastore.find_user(email=email).roles
    for user_role in user_roles:
        if user_role in required_roles:
            return True
    return False

def check_member_supplier(id, email):
    """Check a member's viewing supplier authorization.
    return Boolean
    
    :param id: id
    :param email: Email of the person who will perform the action
    """
    suppliers = user_datastore.find_user(email=email).suppliers
    if id in suppliers:
        return True
    return False

def render_admin_client_structure():
    """
    Return admin structure for the client side display
    """
    admin_structure = {
            "authority":{
                "user_mgmt": ["main_create_btn", "user_edit_btn", "user_resetpw_btn", "user_ophistory_btn"],
                "role_mgmt":["main_create_btn", "role_edit_btn"],
            },
            "outbound":{
		        "outbound_orders": ["main_download_btn"],
	        },
            "somepage":{
                "some_stuff": ["stuff1", "stuff2"],
            },
            "some_other_page":{
                "some_other_stuff":["stuff3"],
            },
        }
    return admin_structure

def render_manager_client_structure():
    """
    Return base structure for the client side display
    This is the limited view for basic user/member
    """
    manager_structure = {
            "authority":{
                "user_mgmt": ["user_edit_btn", "user_resetpw_btn"],
            },
            "somepage":{
                "some_stuff": ["stuff1", "stuff2"],
            },
            "some_other_page1":{
                "some_other_stuff":["stuff3"],
            },
        }
    return manager_structure

def render_user_client_structure():
    """
    Return base structure for the client side display
    This is the limited view for basic user/member
    """
    user_structure = {
            "authority":{
                "user_mgmt": ["user_edit_btn", "user_resetpw_btn"],
            },
            "somepage":{
                "some_stuff": ["stuff1", "stuff2"],
            },
        }
    return user_structure
