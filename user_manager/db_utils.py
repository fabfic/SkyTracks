import psycopg
import os
from typing import Tuple
import uuid


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


    def user_exists_by_id(self, user_id: str) -> bool:
        """
        Checks if a user with the given ID exists.

        Args:
            user_id (str): UUID of the user.

        Returns:
            bool: True if the user exists, False otherwise.
        """
        conn, cur = self.start_connection()
        try:
            cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            result = cur.fetchone()
            return result is not None
        finally:
            self.terminate(conn, cur)


    def user_exists_by_email(self, user_email: str) -> bool:
        """
        Checks if a user exists in the users table by email.

        Args:
            user_email (str): Email of the user.

        Returns:
            bool: True if the user exists, False otherwise.
        """
        conn, cur = self.start_connection()
        try:
            cur.execute(
                "SELECT 1 FROM users WHERE email = %s LIMIT 1",
                (user_email,),
            )
            return cur.fetchone() is not None
        finally:
            self.terminate(conn, cur)


    def create_user(self, email: str, username: str, password: bytes) -> str:
        """
        Inserts a new user in the database.

        Args:
            email (str): User email.
            username (str): User username.
            password (bytes): Hashed password (binary).

        Returns:
            str: The UUID of the newly created user as a string.

        Raises:
            psycopg.errors.UniqueViolation: If email/username already exists.
        """
        conn, cur = self.start_connection()
        user_id = uuid.uuid4()

        try:
            cur.execute(
                "INSERT INTO users (id, email, username, password) VALUES (%s, %s, %s, %s)",
                (user_id, email, username, psycopg.Binary(password)),
            )
            return str(user_id)
        finally:
            self.terminate(conn, cur)


    def delete_user(self, user_id: str) -> int:
        """
        Deletes a user by ID.

        Args:
            user_id (str): UUID of the user.
        """
        conn, cur = self.start_connection()
        try:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            return cur.rowcount
        finally:
            self.terminate(conn, cur)
