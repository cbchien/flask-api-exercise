from app import api_version, client
from models import User
import pymysql, ast
# from utils import Client
from flask_restful import Resource
from flask import jsonify, json
from datetime import date, datetime
from json import dumps

class SupplierList(Resource):
    """Return a list of suppliers from warehouse_tw\n
    show first 1000 entries
    return {message} and {data} 
    """
    def get(self):
        tempDict = []
        length_query = """
            SELECT COUNT(*) FROM table_tsp
        """

        query = """
            SELECT id, supplier_name FROM table_tsp LIMIT 1000
        """

        if not client:
            return {
                "version": api_version,
                "message": "Server database error"
            }, 500
        response1 = client._requests(length_query)
        response2 = client._requests(query)
        for i in response2["data"]:
            tempDict.append({
                "id": i["id"],
                "supplier_company": i["supplier_name"],
            })
        return {
            "version": api_version,
            "message": "Get supplier list",
            "total": response1["data"][0]["COUNT(*)"],
            "data": tempDict
        }, 200

class SupplierListMember(Resource):
    """
    Return a list of suppliers from warehouse_tw for a specific member\n
    return {message} and {data} 
    """
    def get(self, member_id):
        tempDict = []
        user = User.query.filter_by(id=member_id).first()
        suppliers = ast.literal_eval(user.suppliers)
        if not client:
            return {
                "version": api_version,
                "message": "Server database error"
            }, 500
        for supplier in suppliers:
            query = """
                SELECT supplier_name FROM table_tsp WHERE id={}
            """.format(supplier)
            response = client._requests(query)
            tempDict.append({
                "id": supplier,
                "supplier_company": response["data"][0]["supplier_name"]
            })
        return {
            "version": api_version,
            "message": 'suppliers for {} (User id: {})'.format(user.email, user.id),
            "data": tempDict
        }, 200    