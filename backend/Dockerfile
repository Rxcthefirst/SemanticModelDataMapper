FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install RDFMap core library
# Option 1: If RDFMap is published to PyPI
RUN pip install --no-cache-dir semantic-rdf-mapper

# Option 2: If mounting local development version
# (Uncomment and use with docker-compose volumes)
# COPY ../../src/rdfmap /app/rdfmap-core
# RUN pip install -e /app/rdfmap-core

# Copy application code
COPY . .

# Create directories
RUN mkdir -p /app/uploads /app/data

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

