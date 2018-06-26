import os
from flask import Flask, json, request, jsonify, render_template, send_from_directory, url_for
from flask_security import Security, login_required, roles_required, roles_accepted, SQLAlchemySessionUserDatastore, current_user
from flask_security.utils import hash_password
from flask_restful import Api
from database import db_session, init_db
from models import User, Role, Logging, Supplier

# Create app
app = Flask(__name__, static_folder="./client/static", template_folder="./client")
app.config["DEBUG"] = True
app.config["SECRET_KEY"] = "super-secret"
app.config["SECRET_KEY"] = "super-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql://root@localhost/localwarehouse"
app.config["SECURITY_PASSWORD_HASH"] = "pbkdf2_sha512"
app.config["SECURITY_PASSWORD_SALT"] = "wwefafvbdmyumdhngfrdefrthyjukmi"
app.config["SECURITY_LOGIN_URL"] = "/flask-login"
#app.config["WTF_CSRF_ENABLED"] = False

# Set up flask restful
api = Api(app)
api_version = 0.1

# Setup Flask-Security
user_datastore = SQLAlchemySessionUserDatastore(db_session, User, Role)
security = Security(app, user_datastore)

# Logging feature
from time import strftime
from logging.handlers import RotatingFileHandler
import logging
import traceback
handler = RotatingFileHandler('app.log', maxBytes=50000, backupCount=3)
logger = logging.getLogger('werkzeug')
# getLogger(__name__):   decorators loggers to file + werkzeug loggers to stdout
# getLogger('werkzeug'): decorators loggers to file + nothing to stdout
logger.setLevel(logging.ERROR)
logger.addHandler(handler)

# Create a user to test with
@app.before_first_request
def create_users_and_roles():
    from utils import render_admin_client_structure, render_manager_client_structure, render_user_client_structure
    init_db()
    if not user_datastore.get_user("admin@gmail.com"):
        user_datastore.create_user(email="admin@gmail.com", password=hash_password("123456"))
    if not user_datastore.get_user("manager@gmail.com"):
        user_datastore.create_user(email="manager@gmail.com", password=hash_password("123456"))
    if not user_datastore.get_user("user1@gmail.com"):
        user_datastore.create_user(email="user1@gmail.com", password=hash_password("123456"))
    if not user_datastore.get_user("user2@gmail.com"):
        user_datastore.create_user(email="user2@gmail.com", password=hash_password("123456"))
    user_datastore.find_or_create_role(name="admin", description="Top level access")
    user_datastore.find_or_create_role(name="manager", description="Second level access")
    user_datastore.find_or_create_role(name="user", description="Third level access")
    db_session.commit()
    user_datastore.add_role_to_user("admin@gmail.com", "admin")
    user_datastore.add_role_to_user("manager@gmail.com", "manager")
    user_datastore.add_role_to_user("user1@gmail.com", "user")
    user_datastore.add_role_to_user("user2@gmail.com", "user")
    db_session.commit()
    # if Supplier.query.filter_by(supplier_company="CompanyA"):
    #     S1 = Supplier("CompanyA", "Bob", "companyA@company.com","1234567")
    #     db_session.add(S1)
    # if Supplier.query.filter_by(supplier_company="CompanyB"):
    #     S2 = Supplier("CompanyB", "Tom", "companyB@company.com","5678923")
    #     db_session.add(S2)
    # if Supplier.query.filter_by(supplier_company="CompanyC"):
    #     S3 = Supplier("CompanyC", "Amy", "companyC@company.com","8734523")
    #     db_session.add(S3)
    db_session.commit()

@app.login_manager.unauthorized_handler
def unauth_handler():
    return jsonify(success=False,
                   data={'login_required': True},
                   message='Authorization required to access this page'), 401

@app.after_request
def after_request(response):
    """ Logging after every request. """
    # 500 is logged via @app.errorhandler.
    if response.status_code != 500:
        timestamp = strftime('[%Y-%b-%d %H:%M]')
        try:
            message = response.json.get('message')
        except:
            if response.status_code > 499:
                message = 'Server error'
            elif response.status_code > 399:
                message = 'Client error'
            else:
                message = 'Undefined message'
        try:
            email = current_user.email
        except:
            email = 'AnonymousUser'

        ######## Add logic to filter out /static/ requests ########
        logger.error('%s, %s, %s, %s, %s, %s, %s, %s', timestamp, request.remote_addr, request.method, request.scheme, request.full_path, response.status, email, message)
        new_log = Logging(email, request.remote_addr, request.method, request.scheme, request.full_path, response.status, message)
        db_session.add(new_log)
        db_session.commit()
    return response

# @app.errorhandler(Exception)
# def exceptions(e):
#     """ Logging after every Exception. """
#     timestamp = strftime('[%Y-%b-%d %H:%M]')
#     trace = traceback.format_exc()
#     try:
#         email = current_user.email
#     except:
#         email = 'AnonymousUser'
#     logger.error('%s, %s, %s, %s, %s, %s, %s, %s', timestamp, request.remote_addr, request.method, request.scheme, request.full_path, '500', email, trace)
#     new_log = Logging(email, request.remote_addr, request.method, request.scheme, request.full_path, '500', 'Server Error')
#     db_session.add(new_log)
#     db_session.commit()
#     return traceback, 500

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'client'),
                               'favicon.ico', mimetype='image/x-icon')

@app.route('/service-worker.js')
def service_worker_js():
    return send_from_directory(os.path.join(app.root_path, 'client'),
                               'service-worker.js')

@app.route("/")
def home():
    # if not current_user.is_authenticated:
    #     return app.login_manager.unauthorized()
    # return 'Welcome to SSP' # redirect to front end static files 
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("index.html")

# List of APIs
import views, roleresources, userresources
api.add_resource(roleresources.AddMemberRole, '/api/addrole')
api.add_resource(roleresources.RemoveMemberRole, '/api/removerole')
api.add_resource(roleresources.GetAllRole, '/api/getallroles')
api.add_resource(roleresources.CreateNewRole, '/api/createnewrole')

api.add_resource(userresources.Member, '/api/member/<member_id>')  #[POST, GET, PUT]
api.add_resource(userresources.MemberList, '/api/member') #[GET]
api.add_resource(userresources.MemberChangePassword, '/api/member/changepassword') #[POST]
api.add_resource(userresources.MemberLogin, '/api/userlogin') #[POST]
api.add_resource(userresources.MemberLogout, '/api/userlogout') #[POST]

api.add_resource(userresources.OpsHistory, '/api/opshistory/<member_id>')  #[GET]
api.add_resource(userresources.OpsHistoryList, '/api/opshistory/all')  #[GET]

# api.add_resource(userresources.RegisterMember, '/api/register')
# api.add_resource(userresources.ChangeMemberStatus, '/api/changestatus')
# api.add_resource(userresources.EditMemberInfo, '/api/editinfo') 
# api.add_resource(userresources.DisplayAllMember, '/api/getalluser')
# api.add_resource(userresources.DisplayMemberOpsHistory, '/api/getopshistory')


if __name__ == "__main__":
    app.run(port=5000)
    # app.add_url_rule('/favicon.ico',
    #              redirect_to=url_for('static', filename='favicon.ico'))