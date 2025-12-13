import os
from typing import Tuple
from flask import Flask, request, jsonify
import psycopg
import bcrypt
import logging
from logging_utils import setup_logging
from redis_utils import RedisCache
from db_utils import PostgresDB
from error_handling_utils import (BaseError, ServiceUnavailableError, BadRequestError, handle_error)

app = Flask(__name__)


setup_logging()
logger = logging.getLogger(__name__)


FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))


cache = RedisCache()
db = PostgresDB()


def validate_create_request(req_data: dict) -> dict:
    """
    Validate the incoming POST /user request.

    Args:
    - req_data (dict): The request data containing headers and JSON body.

    Raises:
    - BadRequestError for missing/invalid headers or body fields.
    """

    req_id = req_data.headers.get("request_id")
    if not req_id:
        raise BadRequestError("Missing or invalid request_id in headers")

    try:
        body = req_data.get_json(force=True)
    except Exception:
        raise BadRequestError("Invalid JSON body")

    email = body.get('email')
    password = body.get('password')
    username = body.get('username')

    if not isinstance(email, str):
        raise BadRequestError("Missing or invalid email in body")

    if not isinstance(password, str):
        raise BadRequestError("Missing or invalid password in body")

    if not isinstance(username, str):
        raise BadRequestError("Missing or invalid username in body")

    salt = bcrypt.gensalt()
    password = bcrypt.hashpw(password.encode('utf-8'), salt)

    return {
        "req_id": req_id,
        "email": email,
        "password": password,
        "username": username
    }


def validate_delete_request(req_data: dict, user_id: str) -> Tuple[str, str]:
    """
    Validate the incoming DELETE /user/<user_id> request.

    Args:
    - req_data (dict): The request data containing headers.
    - user_id (str): The user identifier from the URI.

    Raises:
    - BadRequestError for missing request_id or user_id.
    """

    req_id = req_data.headers.get("request_id")

    if not req_id:
        raise BadRequestError("Missing or invalid request_id in headers")

    if not user_id:
        raise BadRequestError("Missing or invalid user_id in URI")
    
    return req_id, user_id


@app.post('/user')
def create_user():
    """
    Handle POST /user to create a new user.
    """

    try:

        logger.info("Received user registration request, checking cache availability...")

        if not cache.is_available():
            raise ServiceUnavailableError()

        logger.info("Cache is available, validating request payload...")

        data = validate_create_request(request)

        logger.info(f"Payload validated | Request ID: {data.get('req_id')}")

        email = data.get("email")
        username = data.get("username")
        password = data.get("password")
        req_id = data.get("req_id")

        cached = cache.get_request_result(req_id)
        if cached:
            logger.info("Request already processed, returning cached response")
            return jsonify(cached["data"]), cached["status"]
        
        logger.info("Creating new user in the database...")

        new_user_id = db.create_user(email, username, password)
        
        success_result = {
            "status": 201,
            "data": {
                "message": "User created successfully",
                "user_id": new_user_id
            }
        }

        cache.save_request_result(req_id, success_result)
        
        logger.info("User created successfully | id=%s", new_user_id)
        
        return jsonify(success_result["data"]), 201

    except psycopg.errors.UniqueViolation:
        error_result = {
            "status": 400,
            "data": {"error": "Email is already being used"}
        }
        cache.save_request_result(req_id, error_result)
        logger.error(error_result["data"]["error"])
        return handle_error(BadRequestError(error_result["data"]["error"]))
    
    except (psycopg.OperationalError, psycopg.InterfaceError, psycopg.DatabaseError) as e:
        logger.error("Database error occurred: %s", e)
        return handle_error(ServiceUnavailableError())

    except Exception as e:
        if not isinstance(e, BaseError):    
            logger.error("Unexpected error occurred: %s", e)
        return handle_error(e)


@app.delete('/user/<user_id>')
def delete_user(user_id):
    """
    Handle DELETE /user/<user_id> to remove an existing user.
    """

    try:
        logger.info("Received user deletion request, checking cache availability...")

        if not cache.is_available():
            raise ServiceUnavailableError()

        logger.info("Cache is available, validating request parameters...")

        req_id, user_id = validate_delete_request(request, user_id)

        logger.info(f"Request parameters validated | Request ID: {req_id}")
        
        cached = cache.get_request_result(req_id)
        if cached:
            logger.info("Request already processed, returning cached response")
            return jsonify(cached["data"]), cached["status"]

        logger.info("Deleting user from the database...")

        deleted_rows = db.delete_user(user_id)

        if deleted_rows == 0:
            error_result = {
                "status": 400,
                "data": {"error": "User not found"}
            }
            logger.error(error_result["data"]["error"])
            cache.save_request_result(req_id, error_result)
            raise BadRequestError(error_result["data"]["error"])

        # User deleted successfully
        success_result = {
            "status": 200,
            "data": {"message": "User deleted successfully"}
        }
        
        logger.info(success_result["data"]["message"])
        
        cache.save_request_result(req_id, success_result)

        return jsonify(success_result["data"]), 200
    
    except (psycopg.OperationalError, psycopg.InterfaceError, psycopg.DatabaseError) as e:
        logger.error("Database error occurred: %s", e)
        return handle_error(ServiceUnavailableError())

    except Exception as e:
        if not isinstance(e, BaseError):
            logger.error("Unexpected error occurred: %s", e)
        return handle_error(e)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=FLASK_PORT)