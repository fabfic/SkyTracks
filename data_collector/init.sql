CREATE TABLE IF NOT EXISTS user_interests (
    user_email VARCHAR(255) NOT NULL,
    airport_code CHAR(4) NOT NULL,
    PRIMARY KEY (user_email, airport_code)
);

CREATE TABLE IF NOT EXISTS flights (
    departure_airport CHAR(4),
    arrival_airport CHAR(4),
    direction VARCHAR(10) NOT NULL,
    flight_icao CHAR(6) PRIMARY KEY,
    callsign VARCHAR(10) NOT NULL,
    departure_time TIMESTAMP,
    arrival_time TIMESTAMP
);