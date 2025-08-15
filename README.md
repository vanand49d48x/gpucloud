# GPUCloud - RunPod Style MVP

A modern, scalable GPU cloud computing platform built with FastAPI, Next.js, and **real AWS infrastructure**. Now running successfully on Linux with full EC2 instance provisioning and per-minute billing.

## 🏗️ Architecture

- **API**: FastAPI (Python 3.10+) with PostgreSQL and Redis
- **Web**: Next.js 14 with TypeScript and Tailwind CSS
- **Worker**: RQ worker system for async job processing
- **Infrastructure**: **Real AWS EC2 provisioning** with boto3
- **Billing**: Per-minute credit deduction system
- **Common**: Shared Pydantic models and utilities

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

### Running the Services

#### Start Database Services
```bash
docker compose up -d postgres redis
```

#### Start FastAPI Server
```bash
source venv/bin/activate
uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8080
```
The API will be available at `http://localhost:8080`

#### Start RQ Worker (in separate terminal)
```bash
source venv/bin/activate
export PYTHONPATH=$PWD
python -m apps.api.workers
```

#### Stop Database Services
```bash
docker compose down
```

## 🆕 **NEW: Real AWS Infrastructure**

### ✅ **What's Working Now:**

- **Real EC2 Instance Provisioning** - No more fake IPs!
- **Per-Minute Billing** - Credits deducted every 60 seconds
- **Automatic Teardown** - Instances terminated when credits run out
- **Real SSH Access** - Connect to actual running instances
- **Stable Worker System** - No more macOS fork() crashes

### 🚀 **Instance Types Available:**

- **t3.micro** - For testing (low cost)
- **g5.xlarge** - GPU instances (when ready for production)

### 💳 **Billing System:**

- **Prepaid credits** - Users must have sufficient balance
- **Per-minute charges** - Based on hourly_rate_cents / 60
- **Atomic operations** - No double-spending possible
- **Auto-cleanup** - Instances stopped when credits depleted

## 📁 Project Structure

```
.
├─ apps/
│  ├─ api/              # FastAPI backend with real AWS provisioning
│  ├─ agent/            # VM management agent
│  └─ web/              # Next.js frontend
├─ infra/
│  ├─ packer/           # AMI building templates
│  └─ terraform/aws/    # AWS infrastructure
├─ packages/
│  └─ common/           # Shared models
├─ ops/                 # Helper scripts
├─ docker-compose.yml   # Local development
├─ Makefile            # Build commands
└─ README.md
```

## 🔧 Development

### API Development
- FastAPI with automatic OpenAPI documentation
- SQLModel for database models
- Alembic for migrations
- Redis for job queues (RQ)
- **Real AWS EC2 provisioning with boto3**

### Worker System
- **RQ worker for async job processing**
- **EC2 instance lifecycle management**
- **Per-minute billing and metering**
- **Automatic cleanup on errors**

### Infrastructure
- **Real AWS EC2 instances** (not stubs)
- Terraform for AWS resource management
- Packer for custom AMI creation
- Single-module approach for simplicity

## 🧪 Testing

### API Health Check
```bash
curl http://localhost:8080/healthz
# Expected: {"ok": true, "version": "0.1.0"}
```

### Create and Test a Pod
```bash
# 1. Create user and get token
TOKEN=$(curl -s -X POST http://localhost:8080/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"test1234"}' | \
  python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')

# 2. Add credits to user
PGPASSWORD=gpucloud psql -h localhost -U gpucloud -d gpucloud \
  -c "UPDATE credits SET balance_cents=5000 WHERE user_id=1;"

# 3. Create a pod (launches real EC2 instance)
curl -s -X POST http://localhost:8080/v1/pods \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"template_id":"vllm-llama-3.1-8b"}'

# 4. Check pod status
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/v1/pods

# 5. Stop the pod (terminates EC2 instance)
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/v1/pods/<POD_ID>/stop
```

### Database Connection
```bash
# PostgreSQL should be accessible on localhost:5432
# Redis should be accessible on localhost:6379
```

### RQ Queue Status
```bash
source venv/bin/activate
rq info -u redis://localhost:6379/0
```

## 📚 Current Status & Next Steps

### ✅ **Completed:**
1. **Real AWS Infrastructure** - EC2 provisioning working
2. **Per-Minute Billing** - Credit deduction system implemented
3. **Worker System** - Stable RQ worker on Linux
4. **Database Integration** - Full pod lifecycle tracking
5. **Authentication** - JWT-based auth system

### 🚧 **In Progress:**
1. **GPU Instance Types** - Ready to scale from t3.micro to g5.xlarge
2. **Monitoring** - Basic health checks implemented

### 📋 **Next Steps:**
1. **Stripe Integration** - Implement prepaid credit purchases
2. **GPU Quota Management** - Handle AWS GPU instance limits
3. **Web Dashboard** - Frontend for pod management
4. **CI/CD** - Automated testing and deployment
5. **Production Deployment** - Scale up infrastructure

## 🔐 **Security & AWS Setup**

### **Required AWS Permissions:**
- EC2: Launch, terminate, describe instances
- IAM: Instance profile access
- VPC: Subnet and security group access

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

**🎉 Now running real AWS infrastructure with per-minute billing!**
