# GPUCloud - RunPod Style MVP

A modern, scalable GPU cloud computing platform built with FastAPI, Next.js, and **real AWS infrastructure**. Now running successfully with full EC2 instance provisioning, per-minute billing, a professional web dashboard, and **production-grade infrastructure with Nginx, SSL, and comprehensive monitoring**.

## 🏗️ Architecture

- **API**: FastAPI (Python 3.10+) with PostgreSQL and Redis
- **Web**: Next.js 14 with TypeScript and Tailwind CSS
- **Worker**: RQ worker system for async job processing
- **Infrastructure**: **Real AWS EC2 provisioning** with boto3
- **Billing**: Per-minute credit deduction system
- **Dashboard**: Professional dark-themed UI with real-time pod management
- **Production**: **Nginx reverse proxy with SSL, rate limiting, and security headers**
- **Monitoring**: **Comprehensive health monitoring and auto-recovery system**

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose
- **AWS CLI with proper credentials configured**
- **SSH key pair for EC2 instances**

### Setup

1. **Clone and setup environment:**
   ```bash
   git clone <your-repo>
   cd mypods
   cp .env.example .env
   # Edit .env with your AWS configuration
   ```

2. **Configure AWS credentials:**
   ```bash
   aws configure
   # Set your AWS Access Key ID, Secret Access Key, and region
   ```

3. **Update .env with your AWS infrastructure:**
   ```bash
   AWS_REGION=us-east-1
   AWS_SUBNET_ID=subnet-your-subnet-id
   AWS_SECURITY_GROUP_ID=sg-your-security-group
   AWS_SSH_KEY_NAME=your-key-name
   AWS_INSTANCE_PROFILE=your-instance-profile
   BASE_AMI_ID=ami-your-ubuntu-ami
   ```

## 🎯 **Complete App Setup & Run Commands**

### **Option 1: Production Setup with Nginx (Recommended)**

```bash
# 1. Set up Nginx with SSL and production configuration
sudo chmod +x setup_nginx.sh
sudo ./setup_nginx.sh

# 2. Start all services with comprehensive management
chmod +x gpucloud.sh
./gpucloud.sh start
```

### **Option 2: Manual Service Management**

```bash
# 1. Start the Backend API Server:
cd /home/paperspace/mypods
source venv/bin/activate && export PYTHONPATH=$PWD && uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8080

# 2. Start the Frontend Dashboard (in a new terminal):
cd /home/paperspace/mypods/apps/web
npm install
npm run dev

# 3. Start the Background Worker (in another new terminal):
cd /home/paperspace/mypods
source venv/bin/activate && export PYTHONPATH=$PWD && python -m apps.api.workers

# 4. Start Redis (if not running):
redis-server
```

## 🛡️ **Production Management Script**

We've created a comprehensive service management script that handles everything:

```bash
# Start all services
./gpucloud.sh start

# Check service status
./gpucloud.sh status

# View service logs
./gpucloud.sh logs

# Restart all services
./gpucloud.sh restart

# Stop all services
./gpucloud.sh stop

# Get help
./gpucloud.sh help
```

## 📱 **Access Your App:**

- **Frontend Dashboard**: https://184.105.5.179
- **Backend API**: https://184.105.5.179/v1/
- **API Health**: https://184.105.5.179/v1/health
- **System Health**: https://184.105.5.179/healthz
- **API Docs**: https://184.105.5.179/docs

## 🔑 **Test Credentials:**
- **Email**: test2@example.com
- **Password**: password123

## 🆕 **Current Working Features:**

### ✅ **Backend (Fully Functional):**
- **Real EC2 Instance Provisioning** - AWS integration working
- **Per-Minute Billing** - Credits deducted every 60 seconds
- **Automatic Teardown** - Instances terminated when credits run out
- **AWS Catalog API** - Instance types with pricing and markup
- **Credit System** - User balance management
- **Pod Lifecycle** - Create, monitor, terminate pods
- **Authentication** - JWT-based login system
- **Seamless Start/Stop** - Simple buttons that handle instance lifecycle
- **Health Monitoring** - Comprehensive system health checks

### ✅ **Frontend (Professional Dashboard):**
- **Dark Theme UI** - Modern, professional design
- **Real-time Pod Management** - Live status updates
- **Authentication** - Login/signup with persistence
- **Pod Operations** - Launch new pods, terminate existing ones
- **Credit Display** - Show user balance
- **Responsive Design** - Works on all devices
- **Start/Stop Buttons** - Intuitive pod lifecycle management

### ✅ **Production Infrastructure:**
- **Nginx Reverse Proxy** - SSL termination, rate limiting, security headers
- **Load Balancing** - Ready for multiple backend servers
- **Security Headers** - XSS protection, CSRF, content security policy
- **Rate Limiting** - 10 req/s for API, 30 req/s for web
- **Gzip Compression** - Optimized static file delivery
- **Health Monitoring** - Auto-recovery for stuck pods
- **Service Management** - Comprehensive start/stop/restart scripts

### 🚀 **Instance Types Available:**
- **t1.micro** - For testing (low cost)
- **t3.micro** - General purpose
- **g5.xlarge** - GPU instances (when ready for production)

### 💳 **Billing System:**
- **Prepaid credits** - Users must have sufficient balance
- **Per-minute charges** - Based on hourly_rate_cents / 60
- **Atomic operations** - No double-spending possible
- **Auto-cleanup** - Instances stopped when credits depleted

## 🛡️ **Production Safeguards**

### **Enhanced Worker System:**
- **Auto-restart** - Workers restart automatically if stuck
- **Health monitoring** - Background health checks every 30 seconds
- **Timeout protection** - Jobs timeout after 5 minutes
- **Retry logic** - Exponential backoff for failed operations

### **Pod Lifecycle Protection:**
- **Stuck pod detection** - Identifies pods stuck in intermediate states
- **Auto-recovery** - Automatically recovers stuck pods
- **Instance verification** - Checks AWS instance status
- **Graceful degradation** - Falls back to safe states on errors

### **Database & Queue Protection:**
- **Connection pooling** - Efficient database connections
- **Queue monitoring** - Tracks job status and worker health
- **Transaction safety** - Rollback on errors
- **Resource cleanup** - Automatic cleanup of failed resources

## 📁 Project Structure

```
.
├─ apps/
│  ├─ api/              # FastAPI backend with real AWS provisioning
│  │  ├─ app/          # Main API application
│  │  ├─ workers/      # RQ worker for provisioning
│  │  └─ migrations/   # Database migrations
│  ├─ agent/            # VM management agent
│  └─ web/              # Next.js frontend dashboard
│     ├─ app/          # Next.js app directory
│     ├─ components/   # React components
│     └─ contexts/     # Authentication context
├─ nginx/               # Production Nginx configuration
├─ infra/
│  ├─ packer/           # AMI building templates
│  └─ terraform/aws/    # AWS infrastructure
├─ packages/
│  └─ common/           # Shared models
├─ ops/                 # Helper scripts
├─ docker-compose.yml   # Local development
├─ Makefile            # Build commands
├─ gpucloud.sh         # Production service management
├─ setup_nginx.sh      # Nginx setup script
└─ README.md
```

## 🔧 Development

### API Development
- FastAPI with automatic OpenAPI documentation
- SQLModel for database models
- Alembic for migrations
- Redis for job queues (RQ)
- **Real AWS EC2 provisioning with boto3**
- **Comprehensive health monitoring and auto-recovery**

### Worker System
- **RQ worker for async job processing**
- **EC2 instance lifecycle management**
- **Per-minute billing and metering**
- **Automatic cleanup on errors**
- **Enhanced error handling and retry logic**

### Frontend Development
- **Next.js 14** with TypeScript
- **Tailwind CSS** for styling
- **React Context** for state management
- **Real-time updates** with periodic polling
- **Professional dark theme UI**

### Infrastructure
- **Real AWS EC2 instances** (not stubs)
- **Production Nginx** with SSL and security
- Terraform for AWS resource management
- Packer for custom AMI creation
- Single-module approach for simplicity

## 🧪 Testing

### API Health Check
```bash
# Basic health check
curl -k https://184.105.5.179/healthz

# System health with detailed status
curl -k https://184.105.5.179/v1/health

# Service management
./gpucloud.sh status
```

### Create and Test a Pod
```bash
# 1. Create user and get token
TOKEN=$(curl -s -X POST https://184.105.5.179/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"test1234"}' | \
  python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')

# 2. Add credits to user
PGPASSWORD=gpucloud psql -h localhost -U gpucloud -d gpucloud \
  -c "UPDATE credits SET balance_cents=5000 WHERE user_id=1;"

# 3. Create a pod (launches real EC2 instance)
curl -s -X POST https://184.105.5.179/v1/catalog/aws/launch \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"instance_type":"t1.micro"}'

# 4. Check pod status
curl -s -H "Authorization: Bearer $TOKEN" https://184.105.5.179/v1/pods

# 5. Stop the pod (terminates EC2 instance)
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  https://184.105.5.179/v1/pods/<POD_ID>/stop
```

### Database Connection
```bash
# PostgreSQL should be accessible on localhost:5432
# Redis should be accessible on localhost:6379
```

### RQ Queue Status
```bash
source venv/bin/activate
rq info --url redis://localhost:6379
```

## 📚 Current Status & Next Steps

### ✅ **Completed:**
1. **Real AWS Infrastructure** - EC2 provisioning working
2. **Per-Minute Billing** - Credit deduction system implemented
3. **Worker System** - Stable RQ worker on Linux
4. **Database Integration** - Full pod lifecycle tracking
5. **Authentication** - JWT-based auth system
6. **Professional Dashboard** - Complete frontend with real-time updates
7. **AWS Catalog API** - Instance types and pricing
8. **Seamless UX** - Start/stop buttons that handle instance lifecycle
9. **Production Nginx** - SSL, security headers, rate limiting
10. **Health Monitoring** - Auto-recovery for stuck pods
11. **Service Management** - Comprehensive start/stop scripts

### 🚧 **In Progress:**
1. **GPU Instance Types** - Ready to scale from t1.micro to g5.xlarge
2. **Advanced Monitoring** - CloudWatch integration

### 📋 **Next Steps:**
1. **Stripe Integration** - Implement prepaid credit purchases
2. **GPU Quota Management** - Handle AWS GPU instance limits
3. **CI/CD** - Automated testing and deployment
4. **Production Deployment** - Scale up infrastructure
5. **Advanced Analytics** - Usage metrics and cost optimization

## 🔐 **Security & Production Setup**

### **Nginx Security Features:**
- **SSL/TLS encryption** (self-signed initially, Let's Encrypt ready)
- **Rate limiting** - API: 10 req/s, Web: 30 req/s
- **Security headers** - XSS protection, CSRF, content security policy
- **DDoS protection** - Request buffering and timeout handling
- **Access control** - Deny access to sensitive files

### **Required AWS Permissions:**
- EC2: Launch, terminate, describe instances
- IAM: Instance profile access
- VPC: Subnet and security group access
- Pricing: Get product pricing information

### **Network Configuration:**
- Subnet with auto-assign public IPs enabled
- Security group allowing SSH (port 22)
- Proper IAM instance profile for EC2 permissions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly (including AWS integration)
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

---

**🎉 Now running real AWS infrastructure with per-minute billing, a professional web dashboard, and production-grade infrastructure!**

**🚀 To get started: Use the production management script `./gpucloud.sh start`!**

**🛡️ Production-ready with Nginx, SSL, monitoring, and comprehensive safeguards!**
