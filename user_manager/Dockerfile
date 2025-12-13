#LABEL Author="fabfic"

FROM python:3.12-slim

WORKDIR /app

COPY . .

# Install libpq (PostgreSQL client library)
RUN apt-get update && apt-get install -y --no-install-recommends \
	libpq5 \
	&& rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000 50051

# Ensure Python can import generated gRPC stubs placed in /app/generated
ENV PYTHONPATH="/app:/app/generated:${PYTHONPATH}"

# Start gRPC server and Flask app together
CMD ["bash", "-c", "python grpc_server.py & python app.py & wait"]