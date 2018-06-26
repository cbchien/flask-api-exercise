from app import app, security
from flask_security import login_required, roles_required, roles_accepted

@app.route("/view/admin")
@roles_required("admin")
def admin_home():
    return "This is a data for API for Admin only. Superuser!"

@app.route("/view/manager")
@roles_required("manager")
def manager_home():
    return "This API is for Manager only. Just for manager."

@app.route("/view/user")
@roles_required("user")
def user_home():
    return "This API is for User only. Personal."

@app.route("/view/dashboard")
@roles_accepted("admin", "manager")
def dashboard_home():
    return "Some API for Admin and Manager"