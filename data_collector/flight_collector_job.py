from apscheduler.schedulers.background import BackgroundScheduler
from logging_utils import setup_logging
import logging
import time
import requests
import os
from datetime import datetime
from db_utils import PostgresDB
from opensky_auth import get_opensky_token
from circuit_braker import CircuitBreaker, CircuitBreakerOpenException


setup_logging()
logger = logging.getLogger(__name__)

db = PostgresDB()

FLIGHTS_DIRECTION = "all" # can be "arrival", "departure", or "all"


failure_threshold = int(os.getenv("OPENSKY_CB_FAILURE_THRESHOLD", "5"))
recovery_timeout = int(os.getenv("OPENSKY_CB_RECOVERY_TIMEOUT", "30"))

opensky_cb = CircuitBreaker(
    failure_threshold=failure_threshold,
    recovery_timeout=recovery_timeout,
    expected_exception=requests.exceptions.RequestException
)


def fetch_flights_for_airport(airport_code: str, direction: str) -> tuple:
    """
    Fetches flights for a given airport from the OpenSky Network API.import circuit_braker
    Args:
        airport_code (str): The ICAO code of the airport.
        direction (str): "arrival" or "departure".
    Returns:
        tuple: A list of flight data dictionaries.
    """
    
    hours_interval = int(os.getenv("FLIGHT_FETCH_INTERVAL_HOURS", "12"))
    end_time = int(time.time())
    start_time = end_time - hours_interval * 3600

    token = get_opensky_token()
    
    url = f"https://opensky-network.org/api/flights/{direction}"

    def request():
        response = requests.get(
            url = url,
            params = {"airport": airport_code, "begin": start_time, "end": end_time},
            headers = {"Authorization": f"Bearer {token}"},
            timeout = 10
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return []
        else:
            response.raise_for_status()

    try:
        flights = opensky_cb.call(request)

    except CircuitBreakerOpenException:
        logger.error(f"Circuit breaker is open. Skipping OpenSky request for {airport_code} ({direction})")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"RequestException: {e}")
        raise RuntimeError(f"OpenSky request failed: {e}")

    logger.info(f" {len(flights)} voli ricevuti per {airport_code} ({direction})")

    return flights



###################################
###SCHEDULED FLIGHT FETCHING JOB###
###################################

def scheduled_fetch_flights():
    """
    Scheduled job to fetch flights for all interested airports and store them in the database.
    """

    logger.info("Running scheduled OpenSky fetch...")

    try:
    
        airports = db.get_all_interested_airports()

        for airport in airports:
                if FLIGHTS_DIRECTION in {"arrival", "all"}:
                    
                    arrivals = fetch_flights_for_airport(airport, "arrival")
                    
                    for flight in arrivals:
                        db.insert_flight(
                            departure_airport = flight.get("estDepartureAirport") if flight.get("estDepartureAirport") else None,
                            arrival_airport = airport,
                            direction = "arrival", 
                            flight_icao = flight.get("icao24"),
                            callsign = flight.get("callsign"),
                            departure_time = datetime.fromtimestamp(flight.get("firstSeen")) if flight.get("firstSeen") else None,
                            arrival_time = datetime.fromtimestamp(flight.get("lastSeen")) if flight.get("lastSeen") else None
                        )
                
                if FLIGHTS_DIRECTION in {"departure", "all"}:

                    departures = fetch_flights_for_airport(airport, "departure")
                    
                    for flight in departures:
                        db.insert_flight(
                            departure_airport = airport, 
                            arrival_airport = flight.get("estArrivalAirport") if flight.get("estArrivalAirport") else None,
                            direction = "departure", 
                            flight_icao = flight.get("icao24"),
                            callsign = flight.get("callsign"),
                            departure_time = datetime.fromtimestamp(flight.get("firstSeen")) if flight.get("firstSeen") else None,
                            arrival_time = datetime.fromtimestamp(flight.get("lastSeen")) if flight.get("lastSeen") else None
                        )
            
                logger.info(f"Fetched and stored {len(arrivals) + len(departures)} flights for airport: {airport}")

    except Exception as e:
        logger.error(f"Error fetching flights for {airport}: {e}")

    logger.info("Scheduled job complete.")
