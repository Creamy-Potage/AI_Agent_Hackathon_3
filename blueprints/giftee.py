import datetime
from zoneinfo import ZoneInfo
from flask import Blueprint, render_template, Response, request

import sqlalchemy
from db_config import db_conn

import logging
import google.cloud.logging

logger = logging.getLogger()
log_client = google.cloud.logging.Client()
log_client.setup_logging()

giftee_bp = Blueprint('giftee', __name__, template_folder='templates')

@giftee_bp.route('/giftee/list')
def giftee_list():
    query = """
        SELECT
            giftee_uid,
            name,
            relationship,
            area,
            gender,
            number_of_people,
            favorite,
            dislikes,
            caution,
            memo,
            DATE_FORMAT(created_at, '%Y/%m/%d %H:%i:%s') AS created_at,
            DATE_FORMAT(updated_at, '%Y/%m/%d %H:%i:%s') AS updated_at
        FROM
            giftee;
    """
    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            giftees = conn.execute(stmt).fetchall()
    except Exception as e:
        logger.error(e)
        return Response(
             status=500,
             response="transaction error!",
        )

    return render_template('giftee/list.html', giftees=giftees)

@giftee_bp.route('/giftee/detail')
def giftee_detail():
    giftee_uid = request.args.get('giftee_uid', type=int)

    query = """
        SELECT
            giftee_uid,
            name,
            relationship,
            area,
            gender,
            number_of_people,
            favorite,
            dislikes,
            caution,
            memo,
            DATE_FORMAT(created_at, '%Y/%m/%d %H:%i:%s') AS created_at,
            DATE_FORMAT(updated_at, '%Y/%m/%d %H:%i:%s') AS updated_at
        FROM
            giftee
        WHERE
            giftee_uid = :giftee_uid;
    """

    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            res = conn.execute(stmt, parameters={"giftee_uid": giftee_uid})
            giftee = res.fetchone()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('giftee/detail.html',giftee=giftee)

@giftee_bp.route('/giftee/create_input')
def giftee_create_input():
    return render_template('giftee/create_input.html')

@giftee_bp.route('/giftee/create_action', methods=['POST'])
def giftee_create_action():
    name = request.form.get('name')
    relationship = request.form.get('relationship')
    area = request.form.get('area')
    gender = request.form.get('gender')
    number_of_people = request.form.get('number_of_people', type=int)
    favorite = request.form.get('favorite')
    dislikes = request.form.get('dislikes')
    caution = request.form.get('caution')
    memo = request.form.get('memo')

    current_date = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y-%m-%d %H:%M:%S')

    query = """
        INSERT INTO giftee (name, relationship, area, gender, number_of_people, favorite, dislikes, caution, memo, created_at, updated_at)
        VALUES ( :name, :relationship, :area, :gender, :number_of_people, :favorite, :dislikes, :caution, :memo, :created_at, :updated_at)
    """
    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            conn.execute(
                stmt, parameters={
                    "name": name, "relationship": relationship, "area": area, "gender": gender,
                    "number_of_people": number_of_people,
                    "favorite": favorite, "dislikes": dislikes, "caution": caution, "memo": memo,
                    "created_at":current_date, "updated_at":current_date
                }
            )
            conn.commit()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('giftee/create_action.html')

@giftee_bp.route('/giftee/update_input')
def giftee_update_input():
    giftee_uid = request.args.get('giftee_uid', type=int)
    query = """
        SELECT
            giftee_uid,
            name,
            relationship,
            area,
            gender,
            number_of_people,
            favorite,
            dislikes,
            caution,
            memo,
            DATE_FORMAT(created_at, '%Y/%m/%d %H:%i:%s') AS created_at,
            DATE_FORMAT(updated_at, '%Y/%m/%d %H:%i:%s') AS updated_at
        FROM
            giftee
        WHERE
            giftee_uid = :giftee_uid;
    """

    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            res = conn.execute(stmt, parameters={"giftee_uid": giftee_uid})
            giftee = res.fetchone()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    return render_template('giftee/update_input.html', giftee=giftee)

@giftee_bp.route('/giftee/update_action', methods=['POST'])
def giftee_update_action():
    giftee_uid = request.form.get('giftee_uid', type=int)
    name = request.form.get('name')
    relationship = request.form.get('relationship')
    area = request.form.get('area')
    gender = request.form.get('gender')
    number_of_people = request.form.get('number_of_people', type=int)
    favorite = request.form.get('favorite')
    dislikes = request.form.get('dislikes')
    caution = request.form.get('caution')
    memo = request.form.get('memo')
    
    current_date = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y-%m-%d %H:%M:%S')

    query = """
        UPDATE giftee
        SET
            name = :name,
            relationship = :relationship,
            area = :area,
            gender = :gender,
            number_of_people = :number_of_people,
            favorite = :favorite,
            dislikes = :dislikes,
            caution = :caution,
            memo = :memo, 
            updated_at = :updated_at
        WHERE
            giftee_uid = :giftee_uid
    """

    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            conn.execute(
                stmt, parameters={ "giftee_uid": giftee_uid,
                    "name": name, "area": area, "gender": gender,
                    "relationship": relationship, "number_of_people": number_of_people,
                    "favorite": favorite, "dislikes": dislikes, "caution": caution,
                    "memo": memo, "updated_at":current_date
                }
            )
            conn.commit()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    giftee = {
         'giftee_uid' : giftee_uid,
    }
 
    return render_template('giftee/update_action.html', giftee=giftee)

@giftee_bp.route('/giftee/delete_input')
def giftee_delete_input():
    giftee_uid = request.args.get('giftee_uid', type=int)
    query = """
        SELECT
            giftee_uid,
            name,
            relationship,
            area,
            gender,
            number_of_people,
            favorite,
            dislikes,
            caution,
            memo,
            DATE_FORMAT(created_at, '%Y/%m/%d %H:%i:%s') AS created_at,
            DATE_FORMAT(updated_at, '%Y/%m/%d %H:%i:%s') AS updated_at
        FROM
            giftee
        WHERE
            giftee_uid = :giftee_uid;
    """
    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            res = conn.execute(stmt, parameters={"giftee_uid": giftee_uid})
            giftee = res.fetchone()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    return render_template('giftee/delete_input.html', giftee=giftee)

@giftee_bp.route('/giftee/delete_action', methods=['POST'])
def giftee_delete_action():

    giftee_uid = request.form.get('giftee_uid', type=int)

    query = """
        DELETE FROM giftee
        WHERE giftee_uid = :giftee_uid
    """
    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            conn.execute(stmt, parameters={"giftee_uid": giftee_uid})
            conn.commit()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    return render_template('giftee/delete_action.html')
