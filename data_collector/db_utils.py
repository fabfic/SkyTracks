from datetime import datetime
import psycopg
import os
from typing import Tuple


class PostgresDB:
    """
    Wrapper for PostgreSQL database operations.
    This class centralizes database connectivity and some CRUD operations.
    """

    def __init__(self):
        """
        Initializes the database wrapper by loading the DATABASE_URL environment variable.
        """
        self.db_url = os.getenv("DATABASE_URL")


    def start_connection(self) -> Tuple[psycopg.Connection, psycopg.Cursor]:
        """
        Opens a new database connection and returns both the connection
        and a cursor.

        Returns:
            tuple: (connection, cursor)

        Raises:
            psycopg.Error: If the connection fails.
        """
        conn = psycopg.connect(self.db_url)
        cur = conn.cursor()
        return conn, cur


    def terminate(self, conn: psycopg.Connection, cur: psycopg.Cursor) -> None:
        """
        Commits the transaction and safely closes the cursor and connection.

        Args:
            conn (psycopg.Connection): The connection instance.
            cur (psycopg.Cursor): The cursor instance.
        """
        conn.commit()
        cur.close()
        conn.close()


    # ----------------#
    # CRUD OPERATIONS #
    # ----------------#

    def add_interest(self, user_email: str, airport_code: str) -> None:
        """
        Adds an airport to a user's interests.

        Args:
            user_email (str): Email of the user.
            airport_code (str): IATA/ICAO code of the airport.

        Raises:
            psycopg.errors.UniqueViolation: If the airport is already added for this user.
        """
        conn, cur = self.start_connection()
        try:
            cur.execute(
                "INSERT INTO user_interests (user_email, airport_code) VALUES (%s, %s)",
                (user_email, airport_code),
            )
        finally:
            self.terminate(conn, cur)


    def remove_interest(self, user_email: str, airport_code: str) -> int:
        """
        Removes an airport from a user's interests.

        Args:
            user_email (str): Email of the user.
            airport_code (str): IATA/ICAO code of the airport.

        Returns:
            int: Number of rows deleted (0 if none found).
        """
        conn, cur = self.start_connection()
        try:
            cur.execute(
                "DELETE FROM user_interests WHERE user_email = %s AND airport_code = %s",
                (user_email, airport_code),
            )
            return cur.rowcount
        finally:
            self.terminate(conn, cur)
    

    def get_user_interests(self, user_email: str) -> list:
        """
        Retrieves a list of airport codes that a user is interested in.

        Args:
            user_email (str): Email of the user.
        Returns:
            list: List of airport codes.
        """
        conn, cur = self.start_connection()
        try:
            cur.execute(
                "SELECT airport_code FROM user_interests WHERE user_email = %s",
                (user_email,),
            )
            rows = cur.fetchall()
            return [row[0] for row in rows]
        finally:
            self.terminate(conn, cur)

    
    def get_all_interested_airports(self) -> list:
        """
        Retrieves a list of all distinct airport codes that users are interested in.

        Returns:
            list: List of distinct airport codes.
        """
        conn, cur = self.start_connection()
        try:
            cur.execute(
                "SELECT DISTINCT airport_code FROM user_interests"
            )
            rows = cur.fetchall()
            return [row[0] for row in rows]
        finally:
            self.terminate(conn, cur)

    
    def insert_flight(
        self,
        departure_airport: str | None,
        arrival_airport: str,
        direction: str,
        flight_icao: str,
        callsign: str,
        departure_time: datetime | None,
        arrival_time: datetime | None
    ) -> None:
        """
        Inserts a flight record into the database.

        Args:
            departure_airport (str): IATA/ICAO code of the departure airport.
            arrival_airport (str): IATA/ICAO code of the arrival airport.
            direction (str): Direction of the flight ("arrival" or "departure").
            flight_icao (str): ICAO code of the flight.
            callsign (str): Callsign of the flight.
            departure_time (datetime): Scheduled departure time.
            arrival_time (datetime): Scheduled arrival time.
        """
        conn, cur = self.start_connection()
        try:
            cur.execute(
                """INSERT INTO flights 
                (departure_airport, arrival_airport, direction, flight_icao, callsign, departure_time, arrival_time) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (flight_icao) DO NOTHING""",
                (
                    departure_airport,
                    arrival_airport,
                    direction,
                    flight_icao,
                    callsign,
                    departure_time,
                    arrival_time
                ),
            )
        finally:
            self.terminate(conn, cur)


    def get_last_flights_for_airport(self, airport_code: str) -> dict:
        """
        Retrieves the last departure and arrival flights for the given airport.

        Args:
            airport_code (str): ICAO code of the airport.

        Returns:
            dict: {'last_departure': {...}, 'last_arrival': {...}} with flight data, or None if not found.
        """
        conn, cur = self.start_connection()
        try:

            cur.execute(
                """
                SELECT flight_icao, callsign, departure_airport, arrival_airport, departure_time, arrival_time
                FROM flights
                WHERE departure_airport = %s
                ORDER BY departure_time DESC
                LIMIT 1
                """,
                (airport_code,)
            )
            last_departure = cur.fetchone()

            cur.execute(
                """
                SELECT flight_icao, callsign, departure_airport, arrival_airport, departure_time, arrival_time
                FROM flights
                WHERE arrival_airport = %s
                ORDER BY arrival_time DESC
                LIMIT 1
                """,
                (airport_code,)
            )
            last_arrival = cur.fetchone()

            def row_to_dict(row):
                if row:
                    return {
                        "flight_icao": row[0],
                        "callsign": row[1],
                        "departure_airport": row[2] if row[2] else None,
                        "arrival_airport": row[3] if row[3] else None,
                        "departure_time": row[4].isoformat() if row[4] else None,
                        "arrival_time": row[5].isoformat() if row[5] else None
                    }
                return None

            return {
                "last_departure": row_to_dict(last_departure),
                "last_arrival": row_to_dict(last_arrival)
            }

        finally:
            self.terminate(conn, cur)


    def get_average_flights(self, airport_code: str, days: int) -> dict:
        """
        Returns average daily arrivals and departures for an airport.
        """
        conn, cur = self.start_connection()
        try:
            interval = f"{int(days)} days"
            query = f'''
                SELECT
                    COUNT(*) FILTER (
                        WHERE departure_airport = %s
                        AND departure_time >= NOW() - INTERVAL '{interval}'
                    ) AS departures,
                    COUNT(*) FILTER (
                        WHERE arrival_airport = %s
                        AND arrival_time >= NOW() - INTERVAL '{interval}'
                    ) AS arrivals
                FROM flights
            '''
            cur.execute(
                query,
                (
                    airport_code,
                    airport_code,
                ),
            )

            row = cur.fetchone()
            departures, arrivals = row

            return {
                "average_departures": departures / days,
                "average_arrivals": arrivals / days,
            }
        finally:
            self.terminate(conn, cur)
