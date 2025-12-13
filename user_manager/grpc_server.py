import os
import grpc
from concurrent import futures
import logging

import generated.user_service_pb2 as user_service_pb2
import generated.user_service_pb2_grpc as user_service_pb2_grpc

from db_utils import PostgresDB
from logging_utils import setup_logging


setup_logging()
logger = logging.getLogger(__name__)

db = PostgresDB()

class UserServiceServicer(user_service_pb2_grpc.UserServiceServicer):

    def CheckEmail(self, request, context):
        """
        gRPC method to check if an email exists in the database.
        """
        email = request.email
        logger.info(f"Received gRPC email existence check for {email}")

        try:
            exists = db.user_exists_by_email(email)
        except Exception as e:
            logger.error(f"Database error while checking email: {e}")
            context.set_details("Database error")
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            return user_service_pb2.EmailResponse(exists=False)

        return user_service_pb2.EmailResponse(exists=exists)


def serve():
    """
    Starts the gRPC server to handle user-related requests.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    user_service_pb2_grpc.add_UserServiceServicer_to_server(UserServiceServicer(), server)

    port = os.getenv("GRPC_SERVER_PORT", "5051")
    server.add_insecure_port(f"[::]:{port}")
    logger.info(f"Starting gRPC server on port {port}...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
