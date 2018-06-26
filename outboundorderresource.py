from app import api_version, client, app
from database import db_session
from models import User, OutboundDownload
import pymysql, os
from flask_restful import Resource
from flask import jsonify, json, request, send_from_directory, Response
from flask_security import roles_accepted, current_user
from utils import check_member_role, check_member_supplier
from datetime import date, datetime
from sqlalchemy import update
from json import dumps
import pandas as pd

class OutboundOrderList(Resource):
    """Return a list of outound order for a supplier from warehouse_tw\n
    return {message} and {data} 
    """
    # @roles_accepted('admin')
    def get(self, supplier_id):
        page = request.args.get('_page')
        limit = request.args.get('_limit')
        keyword = request.args.get('keyword')

        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401

        if not client:
            return {
                "version": api_version,
                "message": "Server database error"
            }, 500

        # Select data from query_table_sop table from warehouse_tw
        if keyword:
            query_table_sop = """
                SELECT 
                    main_table.*,
                    CASE WHEN main_table.order_status = 'COMPLETED' AND return_info.return_status = 'REFUND_PAID'
                        THEN 'UPDATED STATUS'
                        ELSE main_table.order_status
                        END AS 'integrated_order_status'
                FROM (
                    SELECT 
                        table_ssu.item_id,
                        table_ssu.supplier_id,
                        table_op.ordersn,
                        table_op.order_time AS 'create_time',
                        CONCAT(table_op.item_name, "_", table_op.variation_name) AS "sku_name",
                        table_op.item_id + "_" + table_op.variation_id AS "sku_id",
                        table_op.item_id AS 'supplier_sku_id',
                        table_op.variation_quantity_purchased AS 'quantity',
                        table_op.variation_original_price AS 'orig_sale_prince',
                        table_op.variation_discounted_price AS 'current_sale_price',
                        table_op.order_status
                        FROM (
                            SELECT distinct
                                item_id,
                                supplier_id
                            FROM twk_table_ssu table_ssu
                            WHERE supplier_id="{}"
                        ) AS table_ssu

                    INNER JOIN (
                            SELECT table_sop.*, table_oi.order_status
                            FROM table_sop
                        LEFT JOIN s_table_oi table_oi
                        ON table_sop.ordersn=table_oi.ordersn
                        WHERE (
                            table_sop.ordersn IN ('{}')
                            OR table_sop.item_id IN ('{}')
                            )
                        ORDER BY order_time DESC
                        ) AS table_op
                    ON table_ssu.item_id=table_op.item_id

                    LIMIT {}, {}
                ) AS main_table
                
                LEFT JOIN ( SELECT ordersn AS table_ro, status AS return_status FROM table_sri WHERE status = "REFUND_PAID") return_info
                ON main_table.ordersn=return_info.table_ro
            """.format(supplier_id, keyword, keyword, (int(page)-1)*int(limit), int(limit)+1)
        if not keyword:
            keyword="all"
            query_table_sop = """
                SELECT 
                    main_table.*,
                    CASE WHEN main_table.order_status = 'COMPLETED' AND return_info.return_status = 'REFUND_PAID'
                        THEN 'COMPLETED_REFUND_PAID'
                        ELSE main_table.order_status
                        END AS 'integrated_order_status'
                FROM (
                    SELECT 
                        table_ssu.item_id,
                        table_ssu.supplier_id,
                        table_op.ordersn,
                        table_op.order_time AS 'create_time',
                        CONCAT(table_op.item_name, "_", table_op.variation_name) AS "sku_name",
                        table_op.item_id + "_" + table_op.variation_id AS "sku_id",
                        table_op.item_id AS 'supplier_sku_id',
                        table_op.variation_quantity_purchased AS 'quantity',
                        table_op.variation_original_price AS 'orig_sale_prince',
                        table_op.variation_discounted_price AS 'current_sale_price',
                        table_op.order_status
                        FROM (
                            SELECT distinct
                                item_id,
                                supplier_id
                            FROM twk_table_ssu table_ssu
                            WHERE supplier_id="{}"
                        ) AS table_ssu

                    INNER JOIN (
                            SELECT table_sop.*, table_oi.order_status
                            FROM table_sop
                        LEFT JOIN s_table_oi table_oi
                        ON table_sop.ordersn=table_oi.ordersn
                        ORDER BY order_time DESC
                        ) AS table_op
                    ON table_ssu.item_id=table_op.item_id

                    LIMIT {}, {}
                ) AS main_table
                
                LEFT JOIN ( SELECT ordersn AS table_ro, status AS return_status FROM table_sri WHERE status = "REFUND_PAID") return_info
                ON main_table.ordersn=return_info.table_ro
            """.format(supplier_id, (int(page)-1)*int(limit), int(limit)+1)

        response_table_sop = client._requests(query_table_sop)

        count = 1
        for i in response_table_sop["data"]:
            i["create_time"] = str(i["create_time"])
            i["index"] = (int(page)-1)*int(limit) + count
            count = count + 1

        # query_s_table_oi = """
        #     SELECT supplier_id, supplier_name FROM table_tsp 
        #     INNER JOIN (SELECT supplier_id FROM table_tsp LIMIT 10) AS my_results USING(supplier_id);
        # """
        
        return {
                "version": api_version,
                "message": "Get outbound order {}. Page:{} Limit:{} Keyword:{}".format(supplier_id, page, limit, keyword),
                "data": response_table_sop["data"]
            }, 200

class OutboundOrderDownload(Resource):
    """Return a list of outound order for a supplier from warehouse_tw\n
    limit to 30000 entries \n
    automatically creates xlsx file and save entry information in database
    an absolute path as url can be used to download the file
    return {message} and {data} 
    """
    def get(self, supplier_id):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401

        if check_member_supplier(supplier_id, current_user.email) == False:
            return {
                "message": 'Missing authorization to view info for this supplier',
            }, 401

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        keyword = request.args.get('keyword')

        if start_date and end_date and start_date>end_date:
            return {
                "version": api_version,
                "message": "Please check your date input. Start date is greater than end date.",
                "data": {}
            }, 422

        # Select data from query_table_sop table from warehouse_tw
        if keyword:
            query_table_sop = """
                SELECT 
                    main_table.*,
                    CASE WHEN main_table.order_status = 'COMPLETED' AND return_info.return_status = 'REFUND_PAID'
                        THEN 'COMPLETED_REFUND_PAID'
                        ELSE main_table.order_status
                        END AS 'integrated_order_status'
                FROM (
                    SELECT 
                        table_ssu.item_id,
                        table_ssu.supplier_id,
                        table_op.ordersn,
                        table_op.order_time AS 'create_time',
                        CONCAT(table_op.item_name, "_", table_op.variation_name) AS "sku_name",
                        table_op.item_id + "_" + table_op.variation_id AS "sku_id",
                        table_op.item_id AS 'supplier_sku_id',
                        table_op.variation_quantity_purchased AS 'quantity',
                        table_op.variation_original_price AS 'orig_sale_prince',
                        table_op.variation_discounted_price AS 'current_sale_price',
                        table_op.order_status
                        FROM (
                            SELECT distinct
                                item_id,
                                supplier_id
                            FROM twk_table_ssu table_ssu
                            WHERE supplier_id="{}"
                        ) AS table_ssu

                    INNER JOIN (
                            SELECT table_sop.*, table_oi.order_status
                            FROM table_sop
                        LEFT JOIN s_table_oi table_oi
                        ON table_sop.ordersn=table_oi.ordersn
                        WHERE (
                            (table_sop.ordersn IN ('{}') OR table_sop.item_id IN ('{}'))
                            AND (table_sop.order_time BETWEEN '{}' AND '{}')
                            )
                        ORDER BY order_time DESC
                        ) AS table_op
                    ON table_ssu.item_id=table_op.item_id

                    LIMIT 30000
                ) AS main_table
                
                LEFT JOIN ( SELECT ordersn AS table_ro, status AS return_status FROM table_sri WHERE status = "REFUND_PAID") return_info
                ON main_table.ordersn=return_info.table_ro
            """.format(supplier_id, keyword, keyword, start_date, end_date)
        if not keyword:
            keyword='all'
            query_table_sop = """
                SELECT 
                    main_table.*,
                    CASE WHEN main_table.order_status = 'COMPLETED' AND return_info.return_status = 'REFUND_PAID'
                        THEN 'COMPLETED_REFUND_PAID'
                        ELSE main_table.order_status
                        END AS 'integrated_order_status'
                FROM (
                    SELECT 
                        table_ssu.item_id,
                        table_ssu.supplier_id,
                        table_op.ordersn,
                        table_op.order_time AS 'create_time',
                        CONCAT(table_op.item_name, "_", table_op.variation_name) AS "sku_name",
                        table_op.item_id + "_" + table_op.variation_id AS "sku_id",
                        table_op.item_id AS 'supplier_sku_id',
                        table_op.variation_quantity_purchased AS 'quantity',
                        table_op.variation_original_price AS 'orig_sale_prince',
                        table_op.variation_discounted_price AS 'current_sale_price',
                        table_op.order_status
                        FROM (
                            SELECT distinct
                                item_id,
                                supplier_id
                            FROM twk_table_ssu table_ssu
                            WHERE supplier_id="{}"
                        ) AS table_ssu

                    INNER JOIN (
                            SELECT table_sop.*, table_oi.order_status
                            FROM table_sop
                        LEFT JOIN s_table_oi table_oi
                        ON table_sop.ordersn=table_oi.ordersn
                        WHERE table_sop.order_time BETWEEN '{}' AND '{}'
                        ORDER BY order_time DESC
                        ) AS table_op
                    ON table_ssu.item_id=table_op.item_id

                    LIMIT 30000
                ) AS main_table
                
                LEFT JOIN ( SELECT ordersn AS table_ro, status AS return_status FROM table_sri WHERE status = "REFUND_PAID") return_info
                ON main_table.ordersn=return_info.table_ro
            """.format(supplier_id, start_date, end_date)

        response_table_sop = client._requests(query_table_sop)

        for i in response_table_sop["data"]:
            i["create_time"] = str(i["create_time"])

        # Download as xlsx
        df = pd.DataFrame(response_table_sop["data"])
        file_path=app.root_path + os.path.sep + "download" + os.path.sep
        file_name ="outbound_{}_{}_{}_{}.xlsx".format(supplier_id, start_date, end_date, keyword)
        df.to_excel(file_path + file_name, sheet_name= 'outbound', index=False) 

        # Save information to database
        exist_search_entry = OutboundDownload.query.filter_by(supplier=supplier_id). \
                            filter_by(start_date=start_date). \
                            filter_by(end_date=end_date). \
                            filter_by(keyword=keyword).first()
        if exist_search_entry:
            exist_search_entry.created_at = datetime.now()
            db_session.commit()
            print("update time to {}".format(datetime.now()))
        else:
            new_xlsx_entry = OutboundDownload(supplier_id, start_date, end_date, keyword, file_name)
            db_session.add(new_xlsx_entry)
            db_session.commit()
            print("created new entry")

        return {
                "version": api_version,
                "message": "download outbound {} {} {}".format(start_date, end_date, keyword),
                # "data": response_table_sop["data"]
                "data": {
                    "url": "/download_outbound/{}".format(file_name),
                    "start_date": start_date,
                    "end_date": end_date,
                    "supplier_id": supplier_id,
                    "filename": file_name
                }
            }, 200

class OutboundOrderDownloadList(Resource):
    """Return a list of existing xlsx file a supplier generated from warehouse_tw\n
    return {message} and {data} 
    """
    
    def get(self, supplier_id):
        if check_member_role(["admin"], current_user.email) == False:
            return {
                "message": 'Missing authorization to retrieve content',
            }, 401
        if check_member_supplier(supplier_id, current_user.email) == False:
            return {
                "message": 'Missing authorization to view info for this supplier',
            }, 401

        all_download = OutboundDownload.query.filter_by(supplier=supplier_id).all()
        data = [download.as_dict() for download in all_download]

        # Finds up to the 10 most recent entries for every user with inner query. Then deletes everything not returned by the inner query.
        result = OutboundDownload.query.filter_by(supplier=supplier_id). \
                order_by(OutboundDownload.created_at.desc()). \
                slice(2,(len(all_download)))

        sq = OutboundDownload.query.filter_by(supplier=supplier_id). \
                order_by(OutboundDownload.created_at.desc()). \
                limit(2). \
                with_for_update()

        q = update(OutboundDownload).where(OutboundDownload.supplier == sq.as_scalar()).values({"active": False})
        db_session.execute(q)
        db_session.commit()
        print(q)
        all_download2 = OutboundDownload.query.filter_by(supplier=supplier_id).all()

        result2 = OutboundDownload.query.filter_by(supplier=supplier_id).count()
        resultdata = [download.as_dict() for download in all_download2]
        # print(result2)
        # print(len(all_download))
        return {
                "version": api_version,
                "message": "downloadable outbound file for supplier: {}".format(supplier_id),
                "data": resultdata
            }, 200