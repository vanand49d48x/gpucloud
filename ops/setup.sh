#!/bin/bash
# GPUCloud Development Environment Setup

set -e

echo "🚀 Setting up GPUCloud development environment..."

# Check if Python 3.11+ is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3.11+ is required but not installed"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is required but not installed"
    exit 1
fi

echo "✅ Prerequisites check passed"

# Start database services
echo "🐘 Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 5

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
cd apps/api
python3 -m pip install -e .
cd ../..

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
cd apps/web
npm install
cd ../..

echo "✅ Setup complete! You can now run:"
echo "  make run.api    # Start the FastAPI server"
echo "  make run.web    # Start the Next.js dev server"
echo "  make db.up      # Start database services"
echo "  make db.down    # Stop database services"
