# GPUCloud Quick Start Guide

## Prerequisites
- Ubuntu 22.04+ or similar Linux distribution
- Python 3.9+
- Node.js 18+
- PostgreSQL
- Redis
- Nginx
- AWS CLI configured with appropriate permissions

## Minimal Setup (Checkout & Run)

### 1. Clone and Setup
```bash
git clone https://github.com/vanand49d48x/gpucloud.git
cd gpucloud

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
cd apps/web
npm install
cd ../..
```

### 2. Environment Configuration
Create `.env` file in the root directory:
```bash
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/gpucloud

# JWT Secret (generate a secure random string)
JWT_SECRET=your-secure-jwt-secret-here

# AWS Configuration (required for pod provisioning)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_VPC_ID=vpc-xxxxxxxxx
AWS_SUBNET_ID=subnet-xxxxxxxxx
AWS_SECURITY_GROUP_ID=sg-xxxxxxxxx
AWS_SSH_KEY_NAME=your-ssh-key-name
AWS_INSTANCE_PROFILE=your-instance-profile-name
BASE_AMI_ID=ami-xxxxxxxxx

# Optional: Customize pricing
MARKUP_MULTIPLIER=1.5
```

### 3. Database Setup
```bash
# Create database and user
sudo -u postgres psql
CREATE DATABASE gpucloud;
CREATE USER gpucloud WITH PASSWORD 'gpucloud';
GRANT ALL PRIVILEGES ON DATABASE gpucloud TO gpucloud;
\q

# Run database migrations (if any)
# TODO: Add migration commands when available
```

### 4. Redis Setup
```bash
# Install Redis
sudo apt update
sudo apt install redis-server

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 5. Nginx Setup
```bash
# Install Nginx
sudo apt install nginx

# Copy configuration
sudo cp nginx/gpucloud.conf /etc/nginx/sites-available/gpucloud
sudo ln -s /etc/nginx/sites-available/gpucloud /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default site

# Test and restart Nginx
sudo nginx -t
sudo systemctl restart nginx
```

### 6. Build Frontend
```bash
cd apps/web
npm run build
cd ../..
```

### 7. Start Services
```bash
# Make script executable
chmod +x gpucloud.sh

# Start all services
./gpucloud.sh start
```

## Access URLs
- **Frontend**: http://your-server-ip (port 80)
- **API**: http://your-server-ip/v1/ (proxied through Nginx)
- **Health Check**: http://your-server-ip/health

## Troubleshooting
- Check logs: `./gpucloud.sh logs`
- Restart services: `./gpucloud.sh restart`
- Stop all: `./gpucloud.sh stop`
- Check status: `./gpucloud.sh status`

## Required AWS Permissions
Your AWS user/role needs these permissions:
- EC2: Create, describe, start, stop, terminate instances
- VPC: Describe VPCs, subnets, security groups
- IAM: Pass instance profiles
- EC2: Create/modify security groups
- EC2: Create/modify key pairs

## Security Notes
- Change default JWT_SECRET in production
- Use strong database passwords
- Configure firewall rules appropriately
- Consider using SSL certificates for HTTPS
- Restrict AWS IAM permissions to minimum required

