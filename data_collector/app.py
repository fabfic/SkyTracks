import os
from flask import Flask, jsonify, request
import psycopg
import logging
import grpc
from apscheduler.schedulers.background import BackgroundScheduler

import generated.user_service_pb2 as user_service_pb2
import generated.user_service_pb2_grpc as user_service_pb2_grpc

from logging_utils import setup_logging
from db_utils import PostgresDB
from error_handling_utils import (BaseError, ServiceUnavailableError, BadRequestError, handle_error)
from flight_collector_job import scheduled_fetch_flights

app = Flask(__name__)


setup_logging()
logger = logging.getLogger(__name__)


FLASK_PORT = int(os.getenv("FLASK_PORT", "6000"))


db = PostgresDB()


def check_email_exists(email: str) -> bool:
    """
    gRPC to check if the email exists
    """
    host = os.getenv("USER_MANAGER_HOST", "user_manager")
    port = os.getenv("GRPC_SERVER_PORT", "5051")
    with grpc.insecure_channel(f'{host}:{port}') as channel:  # indirizzo del servizio gRPC
        stub = user_service_pb2_grpc.UserServiceStub(channel)
        request = user_service_pb2.EmailRequest(email=email)
        response = stub.CheckEmail(request)
        return response.exists


def validate_request(request: dict, function: str | None = None) -> dict:
    """
    Validate the incoming requests.

    Args:
    - req_data (dict): The request data containing headers and JSON body.

    Raises:
    - BadRequestError for missing/invalid headers or body fields.
    """
    if function in ['get_average']:
        req_data = dict(request.args)
        logger.info(f"Query string parameters: {req_data}")
    else:    
        try:
            req_data = request.get_json(force=True)
        except Exception:
            raise BadRequestError("Invalid JSON body")
        
    if not req_data.get("email") or not isinstance(req_data.get("email"), str):
        raise BadRequestError("Missing or invalid email in request")

    if not req_data.get("airport_code") or not isinstance(req_data.get("airport_code"), str) or len(req_data.get("airport_code")) != 4:
        raise BadRequestError("Missing or invalid airport_code in request")
    
    # Check if email exists via gRPC
    if not check_email_exists(req_data.get("email")):
        raise BadRequestError("The provided email does not correspond to any existing user")
    
    if function == 'get_average' and (not req_data.get("days") or not isinstance(req_data.get("days"), str) or not req_data.get("days").isdigit() or int(req_data.get("days")) <= 0):
        raise BadRequestError("Missing or invalid days in query string parameters")

    return {
        "email" : req_data.get("email"),
        "airport_code" : req_data.get("airport_code"),
        "days": int(req_data.get("days")) if function == 'get_average' else None
    }


@app.post('/user-interests')
def create_user_interests():
    """
    Handles POST /user-interests to associate a new airport with a user.
    """
    try:

        logger.info("Received user interests association request, validating payload...")

        data = validate_request(request)

        logger.info(f"Payload validated")

        email = data.get("email")
        airport_code = data.get("airport_code")

        logger.info("Associating new airport with user in the database...")

        db.add_interest(email, airport_code)
        
        logger.info("New airport associated successfully")
        
        return jsonify({"message": "New airport associated successfully"}), 201

    except psycopg.errors.UniqueViolation:
        return handle_error(BadRequestError("There is already an interest for this airport for the given user"))
    
    except (psycopg.OperationalError, psycopg.InterfaceError, psycopg.DatabaseError) as e:
        logger.error("Database error occurred: %s", e)
        return handle_error(ServiceUnavailableError())

    except Exception as e:
        if not isinstance(e, BaseError):    
            logger.error("Unexpected error occurred: %s", e)
        return handle_error(e)


@app.delete('/user-interests')
def delete_user_interests():
    """
    Handle DELETE /user-interests to remove an existing airport interest.
    """

    try:
        logger.info("Received interest removal request, validating request payload...")

        data = validate_request(request)

        logger.info(f"Payload validated")

        email = data.get("email")
        airport_code = data.get("airport_code")

        logger.info("Removing airport from user's interests in the database...")

        deleted_rows = db.remove_interest(email, airport_code)

        if deleted_rows == 0:
            raise BadRequestError("Airport interest not found for the given user")

        logger.info("Airport removed from user's interests successfully")

        return jsonify({"message": "Airport removed from user's interests successfully"}), 200
    
    except (psycopg.OperationalError, psycopg.InterfaceError, psycopg.DatabaseError) as e:
        logger.error("Database error occurred: %s", e)
        return handle_error(ServiceUnavailableError())

    except Exception as e:
        if not isinstance(e, BaseError):
            logger.error("Unexpected error occurred: %s", e)
        return handle_error(e)
    

@app.get('/user-interests')
def get_user_interests():
    """
    Retrieves list of user interests for a given user using email query parameter.
    """
    try:
        logger.info("Received user interests retrieval request, validating request parameters...")

        email = request.args.get("email")
        if not email or not isinstance(email, str):
            raise BadRequestError("Missing or invalid 'email' query parameter")
        if not check_email_exists(email):
            raise BadRequestError("The provided email does not correspond to any existing user")

        logger.info("Request parameters validated, retrieving user interests from the database...")

        interests = db.get_user_interests(email)

        if not interests:
            logger.info("No interests found for the given user")
            return jsonify({"message": "No interests found for this user"}), 200

        return jsonify({"interests": interests}), 200

    except (psycopg.OperationalError, psycopg.InterfaceError, psycopg.DatabaseError) as e:
        logger.error("Database error occurred: %s", e)
        return handle_error(ServiceUnavailableError())

    except Exception as e:
        if not isinstance(e, BaseError):
            logger.error("Unexpected error occurred: %s", e)
        return handle_error(e)


@app.get('/user-interests/lastflights/<airport_code>')
def last_flights(airport_code: str):
    """
    Retrieve last departure and arrival flights for a given airport.
    The airport_code is provided as a path parameter.
    """
    try:

        logger.info("Received last flights retrieval request, validating request parameters...")

        if not airport_code or not isinstance(airport_code, str) or len(airport_code) != 4:
            raise BadRequestError("Missing or invalid airport_code in the path")
        
        logger.info("Request parameters validated, retrieving last flights from the database...")

        flights = db.get_last_flights_for_airport(airport_code)

        if not flights["last_departure"] and not flights["last_arrival"]:
            logger.info("No flights found for the given airport")
            return jsonify({"message": "No flights found for this airport"}), 200

        logger.info("Last flights retrieved successfully")

        return jsonify(flights), 200

    except (psycopg.OperationalError, psycopg.InterfaceError, psycopg.DatabaseError) as e:
        logger.error("Database error occurred: %s", e)
        return handle_error(ServiceUnavailableError())

    except Exception as e:
        if not isinstance(e, BaseError):
            logger.error("Unexpected error occurred: %s", e)
        return handle_error(e)
    

@app.get('/user-interests/traffic-average')
def get_airport_traffic_average():
    """
    Returns average daily arrivals and departures for a user airport.
    """
    try:
        logger.info("Received airport traffic average request, validating request parameters...")

        data = validate_request(request, function='get_average')

        email = data.get("email")
        airport_code = data.get("airport_code")
        days = data.get("days")

        user_airports = db.get_user_interests(email)
        if airport_code not in user_airports:
            raise BadRequestError("Airport not associated with the given user")
        
        logger.info("Request parameters validated, retrieving average traffic data from the database...")

        averages = db.get_average_flights(airport_code, days)

        return jsonify(averages), 200

    except (psycopg.OperationalError, psycopg.InterfaceError, psycopg.DatabaseError) as e:
        logger.error("Database error occurred: %s", e)
        return handle_error(ServiceUnavailableError())

    except Exception as e:
        if not isinstance(e, BaseError):
            logger.error("Unexpected error occurred: %s", e)
        return handle_error(e)



if __name__ == '__main__':
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_fetch_flights, 'interval', hours=int(os.getenv("FLIGHT_FETCH_INTERVAL_HOURS", 12)))
    scheduler.start()

    app.run(host = '0.0.0.0', port = FLASK_PORT, debug = False)