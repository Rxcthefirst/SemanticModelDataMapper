#!/bin/bash

# RDFMap Web UI - Quick Start Script
# This script will set up and start the web application

set -e  # Exit on error

echo "🚀 RDFMap Web UI - Quick Start"
echo "================================"
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check for Docker Compose (try v2 first, then v1)
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "   Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env

    # Generate a random secret key
    if command -v openssl &> /dev/null; then
        SECRET_KEY=$(openssl rand -hex 32)
        # Replace the placeholder in .env file
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/change-me-in-production-use-openssl-rand-hex-32/$SECRET_KEY/" .env
        else
            # Linux
            sed -i "s/change-me-in-production-use-openssl-rand-hex-32/$SECRET_KEY/" .env
        fi
        echo "✅ Generated secure SECRET_KEY"
    else
        echo "⚠️  Could not generate SECRET_KEY (openssl not found)"
        echo "   Please edit .env and set a secure SECRET_KEY"
    fi
    echo ""
else
    echo "✅ .env file already exists"
    echo ""
fi

# Create required directories
echo "📁 Creating required directories..."
mkdir -p uploads data
echo "✅ Directories created"
echo ""

# Check if ports are available
echo "🔍 Checking if required ports are available..."
PORTS_BUSY=0

if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 8080 (UI) is already in use"
    PORTS_BUSY=1
fi

if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 8000 (API) is already in use"
    PORTS_BUSY=1
fi

if lsof -Pi :5432 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 5432 (PostgreSQL) is already in use"
    PORTS_BUSY=1
fi

if [ $PORTS_BUSY -eq 1 ]; then
    echo ""
    echo "❌ Some ports are already in use. Please stop those services first."
    echo "   Or edit docker-compose.yml to use different ports."
    exit 1
fi

echo "✅ All required ports are available"
echo ""

# Stop any existing containers
echo "🧹 Stopping any existing containers..."
$DOCKER_COMPOSE down 2>/dev/null || true
echo ""

# Build and start containers
echo "🏗️  Building Docker containers (this may take a few minutes)..."
$DOCKER_COMPOSE build

echo ""
echo "🚀 Starting services..."
$DOCKER_COMPOSE up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Wait for API to be ready
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "✅ API is ready!"
        break
    fi
    echo -n "."
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo ""
    echo "⚠️  API did not start in time. Check logs with:"
    echo "   $DOCKER_COMPOSE logs api"
    exit 1
fi

echo ""
echo ""
echo "=========================================="
echo "✨ RDFMap Web UI is now running!"
echo "=========================================="
echo ""
echo "📍 Access points:"
echo "   • Web UI:        http://localhost:8080"
echo "   • API Docs:      http://localhost:8000/api/docs"
echo "   • Health Check:  http://localhost:8000/api/health"
echo ""
echo "📊 View logs:"
echo "   $DOCKER_COMPOSE logs -f"
echo ""
echo "🛑 Stop services:"
echo "   $DOCKER_COMPOSE down"
echo ""
echo "🔧 Restart services:"
echo "   $DOCKER_COMPOSE restart"
echo ""
echo "📚 Documentation:"
echo "   • Quick Start:   WEB_UI_QUICKSTART.md"
echo "   • Architecture:  docs/WEB_UI_ARCHITECTURE.md"
echo ""
echo "🎉 Happy mapping!"
echo ""

