# 🚀 GPUCloud Per-Pod IAM & Logging

This document describes the new **Per-Pod IAM** feature that provides complete isolation and security for each GPUCloud pod.

## 🎯 **Overview**

The Per-Pod IAM feature automatically creates:
- **Individual IAM roles** for each pod
- **Unique instance profiles** for each pod  
- **CloudWatch log groups** for centralized logging
- **Complete resource isolation** between pods
- **Zero manual configuration** required

## 🏗️ **Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Pod 1    │    │   User Pod 2    │    │   User Pod 3    │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │IAM Role 1   │ │    │ │IAM Role 2   │ │    │ │IAM Role 3   │ │
│ │Profile 1    │ │    │ │Profile 2    │ │    │ │Profile 3    │ │
│ │Log Group 1  │ │    │ │Log Group 2  │ │    │ │Log Group 3  │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │Permissions      │
                    │Boundary        │
                    │(Safety Rail)   │
                    └─────────────────┘
```

## 🚀 **Quick Start**

### **Step 1: One-Time Setup**

Run the setup script to create the permissions boundary and control plane policy:

```bash
# Make sure you have AWS admin credentials
python3 setup_pod_iam_infrastructure.py
```

### **Step 2: Update Environment**

Add the new configuration to your `.env` file:

```bash
# Per-Pod IAM Configuration
AWS_POD_PERMISSIONS_BOUNDARY=arn:aws:iam::YOUR-ACCOUNT-ID:policy/gpucloud-pod-permissions-boundary
ENABLE_PER_POD_IAM=true
ENABLE_PER_POD_LOGGING=true
S3_BUCKET=gpucloud-data  # Optional
```

### **Step 3: Run Database Migration**

```bash
cd apps/api
alembic upgrade head
```

### **Step 4: Restart Services**

```bash
./gpucloud.sh restart
```

## 🔐 **Security Features**

### **Permissions Boundary**
- **Denies dangerous actions**: `iam:*`, `sts:AssumeRole`, `ec2:*`, `eks:*`, `rds:*`
- **Allows necessary actions**: `ssm:*`, `logs:*`, `s3:*` (scoped)
- **Prevents privilege escalation**: No role assumption or IAM modification

### **Per-Pod Isolation**
- **Unique IAM roles**: Each pod gets its own role with minimal permissions
- **Scoped access**: Pods can only access their own CloudWatch logs and S3 data
- **No cross-pod access**: Complete isolation between user pods

### **Resource Tagging**
- **Customer ID**: Links resources to specific users
- **Pod ID**: Unique identifier for each pod
- **Product**: Identifies GPUCloud resources
- **Created-by**: Tracks resource creation

## 📊 **What Gets Created Per Pod**

### **1. IAM Role**
```json
{
  "RoleName": "gpucloud-pod-123",
  "PermissionsBoundary": "arn:aws:iam::ACCOUNT:policy/gpucloud-pod-permissions-boundary",
  "Tags": [
    {"Key": "customer-id", "Value": "456"},
    {"Key": "pod-id", "Value": "123"},
    {"Key": "product", "Value": "gpucloud"}
  ]
}
```

### **2. Instance Profile**
```json
{
  "InstanceProfileName": "gpucloud-pod-123",
  "Roles": ["gpucloud-pod-123"],
  "Tags": [
    {"Key": "customer-id", "Value": "456"},
    {"Key": "pod-id", "Value": "123"},
    {"Key": "product", "Value": "gpucloud"}
  ]
}
```

### **3. CloudWatch Log Group**
```json
{
  "logGroupName": "/gpucloud/456/123",
  "retentionInDays": 14,
  "tags": {
    "customer-id": "456",
    "pod-id": "123",
    "product": "gpucloud"
  }
}
```

### **4. EC2 Instance**
```json
{
  "InstanceId": "i-1234567890abcdef0",
  "IamInstanceProfile": {"Name": "gpucloud-pod-123"},
  "Tags": [
    {"Key": "customer-id", "Value": "456"},
    {"Key": "pod-id", "Value": "123"},
    {"Key": "product", "Value": "gpucloud"},
    {"Key": "created-by", "Value": "gpucloud-pod-creator"}
  ]
}
```

## 🔧 **API Endpoints**

### **Pod Creation (Automatic)**
```bash
POST /v1/catalog/aws/launch
{
  "id": "aws:us-east-1:t3.micro"
}
```

**Response includes:**
```json
{
  "id": 123,
  "status": "running",
  "instance_type": "t3.micro",
  "role_name": "gpucloud-pod-123",
  "role_arn": "arn:aws:iam::ACCOUNT:role/gpucloud-pod-123",
  "instance_profile": "gpucloud-pod-123",
  "log_group": "/gpucloud/456/123"
}
```

### **CloudWatch Logs**
```bash
# Get pod logs
GET /v1/logs/pods/123/cloudwatch?limit=100

# Get log streams
GET /v1/logs/pods/123/cloudwatch/streams
```

### **Pod Information**
```bash
GET /v1/pods
```

**Response includes:**
```json
{
  "id": 123,
  "status": "running",
  "role_name": "gpucloud-pod-123",
  "role_arn": "arn:aws:iam::ACCOUNT:role/gpucloud-pod-123",
  "instance_profile": "gpucloud-pod-123",
  "log_group": "/gpucloud/456/123",
  "uses_per_pod_iam": true
}
```

## 🚀 **Advanced Features**

### **S3 Integration**
If `S3_BUCKET` is configured, pods get scoped S3 access:

```json
{
  "Sid": "S3PrefixRW",
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
  "Resource": "arn:aws:s3:::gpucloud-data/456/*"
}
```

### **CloudWatch Logging**
Pods can write to their own log groups:

```json
{
  "Sid": "LogsPod",
  "Effect": "Allow",
  "Action": ["logs:PutLogEvents", "logs:CreateLogStream"],
  "Resource": "arn:aws:logs:region:account:log-group:/gpucloud/456/123:*"
}
```

### **SSM Access**
Full SSM capabilities for terminal access:

```json
{
  "Sid": "SSMCore",
  "Effect": "Allow",
  "Action": [
    "ssmmessages:CreateControlChannel",
    "ssmmessages:CreateDataChannel",
    "ec2messages:*"
  ],
  "Resource": "*"
}
```

## 🔍 **Monitoring & Debugging**

### **Check Pod IAM Status**
```bash
# View pod details with IAM info
curl -H "Authorization: Bearer $TOKEN" \
  https://your-domain/v1/pods
```

### **View CloudWatch Logs**
```bash
# Get recent logs
curl -H "Authorization: Bearer $TOKEN" \
  "https://your-domain/v1/logs/pods/123/cloudwatch?limit=50"
```

### **AWS Console**
- **IAM**: View individual pod roles and policies
- **CloudWatch**: Browse pod-specific log groups
- **EC2**: See tagged instances with IAM profiles

## 🛡️ **Security Best Practices**

### **1. Permissions Boundary**
- **Never remove**: The permissions boundary is your safety rail
- **Review regularly**: Ensure it blocks all dangerous actions
- **Test thoroughly**: Verify new services can't escalate privileges

### **2. Resource Cleanup**
- **Automatic cleanup**: Failed pods automatically clean up IAM resources
- **Manual verification**: Check AWS console for orphaned resources
- **Regular audits**: Review IAM roles and policies monthly

### **3. Access Control**
- **Principle of least privilege**: Pods get minimal required permissions
- **Customer isolation**: No cross-customer resource access
- **Audit logging**: All actions logged to CloudWatch

## 🚨 **Troubleshooting**

### **Common Issues**

#### **1. Permissions Boundary Not Found**
```bash
Error: Could not find permissions boundary
```
**Solution**: Run `setup_pod_iam_infrastructure.py` first

#### **2. Control Plane Insufficient Permissions**
```bash
Error: AccessDenied when creating IAM role
```
**Solution**: Attach `gpucloud-control-plane-policy` to your backend role

#### **3. Pod Creation Fails**
```bash
Error: Failed to create IAM role
```
**Solution**: Check AWS credentials and ensure IAM permissions

#### **4. CloudWatch Logs Not Accessible**
```bash
Error: Log group not found
```
**Solution**: Verify `ENABLE_PER_POD_LOGGING=true` in config

### **Debug Commands**

```bash
# Check IAM setup
aws iam get-policy --policy-arn arn:aws:iam::ACCOUNT:policy/gpucloud-pod-permissions-boundary

# List pod roles
aws iam list-roles --path-prefix /gpucloud-pod-

# Check CloudWatch log groups
aws logs describe-log-groups --log-group-name-prefix /gpucloud/
```

## 📈 **Performance & Scaling**

### **Resource Limits**
- **IAM Roles**: 1000 per account (soft limit)
- **Instance Profiles**: 1000 per account (soft limit)
- **CloudWatch Log Groups**: 5000 per account (soft limit)

### **Cleanup Strategy**
- **Automatic cleanup**: Failed pods clean up resources
- **Manual cleanup**: Use `delete_pod` endpoint for complete removal
- **Batch operations**: Consider bulk cleanup for inactive pods

### **Cost Optimization**
- **Log retention**: 14-day retention by default
- **Resource tagging**: Easy cost allocation and tracking
- **Monitoring**: CloudWatch metrics for resource usage

## 🔮 **Future Enhancements**

### **Planned Features**
1. **Dynamic Policy Generation**: Based on pod requirements
2. **Cross-Region Support**: Pods in multiple AWS regions
3. **Advanced Monitoring**: CloudWatch dashboards and alarms
4. **Compliance Features**: Policy validation and enforcement
5. **Backup & Recovery**: IAM role backup and restoration

### **Integration Opportunities**
1. **AWS Config**: Compliance monitoring and reporting
2. **CloudTrail**: Detailed API call logging
3. **GuardDuty**: Threat detection and response
4. **Security Hub**: Centralized security findings

## 📚 **Additional Resources**

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [CloudWatch Logs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/)
- [EC2 Instance Profiles](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html)
- [Permissions Boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html)

---

**🎉 With Per-Pod IAM, every pod gets enterprise-grade security with zero manual configuration!**


