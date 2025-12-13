from apscheduler.schedulers.background import BackgroundScheduler
from logging_utils import setup_logging
import logging
import time
import requests
import os
from datetime import datetime
from db_utils import PostgresDB
from opensky_auth import get_opensky_token

setup_logging()
logger = logging.getLogger(__name__)

db = PostgresDB()

FLIGHTS_DIRECTION = "all" # can be "arrival", "departure", or "all"


def fetch_flights_for_airport(airport_code: str, direction: str) -> tuple:
    
    hours_interval = int(os.getenv("FLIGHT_FETCH_INTERVAL_HOURS", "12"))
    end_time = int(time.time())
    start_time = end_time - hours_interval * 3600

    token = get_opensky_token()
    
    url = f"https://opensky-network.org/api/flights/{direction}"

    flights = requests.get(
        url = url,
        params = {"airport": airport_code, "begin": start_time, "end": end_time},
        headers = {"Authorization": f"Bearer {token}"},
        timeout = 10
    )

    flights.raise_for_status()

    return flights.json()


###################################
###SCHEDULED FLIGHT FETCHING JOB###
###################################

def scheduled_fetch_flights():

    logger.info("Running scheduled OpenSky fetch...")

    airports = db.get_all_interested_airports()

    for airport in airports:
        try:
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
