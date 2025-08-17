#!/bin/bash

# GPUCloud Minimal Setup Script
# This script sets up the minimal environment needed to run GPUCloud

set -e

echo "🚀 GPUCloud Minimal Setup"
echo "=========================="

# Check if we're in the right directory
if [ ! -f "gpucloud.sh" ]; then
    echo "❌ Error: Please run this script from the GPUCloud root directory"
    exit 1
fi

# Check if running as root for system package installation
if [ "$EUID" -eq 0 ]; then
    echo "❌ Error: Please don't run this script as root. It will use sudo when needed."
    exit 1
fi

# Function to install system packages
install_system_packages() {
    echo "📦 Installing system packages..."
    
    # Update package list
    sudo apt update
    
    # Install required packages
    sudo apt install -y python3 python3-venv python3-pip nodejs npm postgresql postgresql-contrib redis-server nginx
    
    echo "✅ System packages installed"
}

# Function to setup PostgreSQL
setup_database() {
    echo "🗄️  Setting up PostgreSQL database..."
    
    # Create database and user
    sudo -u postgres psql -c "CREATE DATABASE gpucloud;" 2>/dev/null || echo "Database already exists"
    sudo -u postgres psql -c "CREATE USER gpucloud WITH PASSWORD 'gpucloud';" 2>/dev/null || echo "User already exists"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE gpucloud TO gpucloud;" 2>/dev/null || echo "Privileges already granted"
    
    echo "✅ Database setup complete"
}

# Function to setup Nginx
setup_nginx() {
    echo "🌐 Setting up Nginx..."
    
    # Copy configuration
    sudo cp nginx/gpucloud.conf /etc/nginx/sites-available/gpucloud
    
    # Enable site
    if [ ! -L "/etc/nginx/sites-enabled/gpucloud" ]; then
        sudo ln -s /etc/nginx/sites-available/gpucloud /etc/nginx/sites-enabled/
    fi
    
    # Remove default site if it exists
    if [ -L "/etc/nginx/sites-enabled/default" ]; then
        sudo rm /etc/nginx/sites-enabled/default
    fi
    
    # Test configuration
    if sudo nginx -t; then
        sudo systemctl restart nginx
        sudo systemctl enable nginx
        echo "✅ Nginx setup complete"
    else
        echo "❌ Nginx configuration test failed"
        exit 1
    fi
}

# Function to setup Redis
setup_redis() {
    echo "🔴 Setting up Redis..."
    
    sudo systemctl start redis-server
    sudo systemctl enable redis-server
    
    # Test connection
    if redis-cli ping &> /dev/null; then
        echo "✅ Redis setup complete"
    else
        echo "❌ Redis setup failed"
        exit 1
    fi
}

# Check and install system packages
echo "📋 Checking system packages..."
if ! command -v python3 &> /dev/null || ! command -v node &> /dev/null || ! command -v psql &> /dev/null || ! command -v redis-cli &> /dev/null || ! command -v nginx &> /dev/null; then
    echo "⚠️  Some system packages are missing. Installing them now..."
    install_system_packages
else
    echo "✅ All system packages are installed"
fi

# Setup system services
setup_database
setup_redis
setup_nginx

# Create virtual environment
echo "🐍 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
cd apps/web
npm install
cd ../..

# Build frontend
echo "🔨 Building frontend..."
cd apps/web
npm run build
cd ../..

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x gpucloud.sh
chmod +x start_production.sh

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "   Please copy env.template to .env and configure your environment variables:"
    echo "   cp env.template .env"
    echo "   nano .env"
    echo ""
    echo "   Required variables:"
    echo "   - DATABASE_URL"
    echo "   - JWT_SECRET"
    echo "   - AWS_* variables for pod provisioning"
    echo ""
    echo "   See QUICK_START.md for detailed instructions"
    echo ""
fi

# Check database connection
echo "🗄️  Checking database connection..."
if [ -f ".env" ]; then
    source .env
    if command -v psql &> /dev/null; then
        # Extract database info from DATABASE_URL
        if [[ $DATABASE_URL =~ postgresql://([^:]+):([^@]+)@([^:]+):([^/]+)/(.+) ]]; then
            DB_USER="${BASH_REMATCH[1]}"
            DB_PASS="${BASH_REMATCH[2]}"
            DB_HOST="${BASH_REMATCH[3]}"
            DB_PORT="${BASH_REMATCH[4]}"
            DB_NAME="${BASH_REMATCH[5]}"
            
            if PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
                echo "✅ Database connection successful"
            else
                echo "⚠️  Warning: Cannot connect to database. Please check your DATABASE_URL in .env"
            fi
        fi
    fi
fi

# Check Redis connection
echo "🔴 Checking Redis connection..."
if redis-cli ping &> /dev/null; then
    echo "✅ Redis connection successful"
else
    echo "⚠️  Warning: Cannot connect to Redis. Please ensure Redis is running:"
    echo "   sudo systemctl start redis-server"
fi

# Check Nginx configuration
echo "🌐 Checking Nginx configuration..."
if sudo nginx -t &> /dev/null; then
    echo "✅ Nginx configuration is valid"
    
    # Check if our site is enabled
    if [ -L "/etc/nginx/sites-enabled/gpucloud" ]; then
        echo "✅ GPUCloud Nginx site is enabled"
    else
        echo "⚠️  Warning: GPUCloud Nginx site is not enabled. Please run:"
        echo "   sudo cp nginx/gpucloud.conf /etc/nginx/sites-available/gpucloud"
        echo "   sudo ln -s /etc/nginx/sites-available/gpucloud /etc/nginx/sites-enabled/"
        echo "   sudo systemctl restart nginx"
    fi
else
    echo "❌ Nginx configuration is invalid. Please check your configuration."
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Configure your .env file with your AWS credentials and database settings"
echo "2. Run: ./gpucloud.sh start"
echo ""
echo "For detailed instructions, see QUICK_START.md"
echo ""
echo "Access URLs:"
echo "- Frontend: http://$(hostname -I | awk '{print $1}')"
echo "- API: http://$(hostname -I | awk '{print $1}')/v1/"
echo "- Health: http://$(hostname -I | awk '{print $1}')/health"

