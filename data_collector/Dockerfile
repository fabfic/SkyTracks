FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Ensure Python can import generated gRPC stubs placed in /app/generated
ENV PYTHONPATH="/app:/app/generated:${PYTHONPATH}"

CMD ["python", "app.py"]