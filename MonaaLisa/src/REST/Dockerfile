
# Flask API Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN echo "✅ Building the REST Dockerfile!" > /build-log.txt


# Install system dependencies (recommended)
RUN apt-get update && apt-get install -y gcc

# Copy requirements and install them
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["ECHO", '"Im running"']

# Copy the app code after installing dependencies
COPY . .

# Run using gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
