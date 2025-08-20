# 🔧 **Manual IAM Setup for Per-Pod IAM**

Since your `gpucloud-provisioner` user doesn't have IAM admin permissions, you'll need to create the required policies manually using an AWS admin account.

## 🚀 **Step-by-Step Manual Setup**

### **Prerequisites**
- AWS CLI configured with admin credentials
- Access to AWS account `458178359313`

### **Step 1: Create Permissions Boundary Policy**

```bash
# Create the permissions boundary (safety rail for all pod roles)
aws iam create-policy \
  --policy-name gpucloud-pod-permissions-boundary \
  --policy-document file://infra/iam/pod-permissions-boundary.json \
  --description "Permissions boundary for GPUCloud pod IAM roles"
```

**Expected Output:**
```json
{
  "Policy": {
    "PolicyName": "gpucloud-pod-permissions-boundary",
    "PolicyId": "ANPA...",
    "Arn": "arn:aws:iam::458178359313:policy/gpucloud-pod-permissions-boundary",
    "Path": "/",
    "DefaultVersionId": "v1",
    "AttachmentCount": 0,
    "PermissionsBoundaryUsageCount": 0,
    "IsAttachable": true,
    "CreateDate": "2025-01-15T...",
    "UpdateDate": "2025-01-15T..."
  }
}
```

### **Step 2: Create Control Plane Policy**

```bash
# Create the control plane policy (allows backend to manage pod resources)
aws iam create-policy \
  --policy-name gpucloud-control-plane-policy \
  --policy-document file://control-plane-policy.json \
  --description "Policy for GPUCloud control plane to manage pod resources"
```

**Expected Output:**
```json
{
  "Policy": {
    "PolicyName": "gpucloud-control-plane-policy",
    "PolicyId": "ANPA...",
    "Arn": "arn:aws:iam::458178359313:policy/gpucloud-control-plane-policy",
    "Path": "/",
    "DefaultVersionId": "v1",
    "AttachmentCount": 0,
    "PermissionsBoundaryUsageCount": 0,
    "IsAttachable": true,
    "CreateDate": "2025-01-15T...",
    "UpdateDate": "2025-01-15T..."
  }
}
```

### **Step 3: Attach Control Plane Policy to Your Backend User**

```bash
# Attach the control plane policy to your gpucloud-provisioner user
aws iam attach-user-policy \
  --user-name gpucloud-provisioner \
  --policy-arn arn:aws:iam::458178359313:policy/gpucloud-control-plane-policy
```

**Expected Output:**
```bash
# No output on success
```

### **Step 4: Verify Setup**

```bash
# Check that policies exist
aws iam get-policy --policy-arn arn:aws:iam::458178359313:policy/gpucloud-pod-permissions-boundary
aws iam get-policy --policy-arn arn:aws:iam::458178359313:policy/gpucloud-control-plane-policy

# Check that policy is attached to user
aws iam list-attached-user-policies --user-name gpucloud-provisioner
```

## 🔍 **What These Policies Do**

### **Permissions Boundary Policy**
- **Acts as a safety rail** for all pod IAM roles
- **Prevents dangerous actions** like `iam:*`, `sts:AssumeRole`, `ec2:*`
- **Allows necessary actions** like `ssm:*`, `logs:*`, `s3:*` (scoped)

### **Control Plane Policy**
- **Allows backend to create** pod IAM roles and instance profiles
- **Scoped to pod resources** only (no cross-pod access)
- **Enables EC2 operations** for pod management
- **Permits CloudWatch** log group creation

## 📝 **Update Your .env File**

After creating the policies, add this to your `.env` file:

```bash
# Per-Pod IAM Configuration
AWS_POD_PERMISSIONS_BOUNDARY=arn:aws:iam::458178359313:policy/gpucloud-pod-permissions-boundary
ENABLE_PER_POD_IAM=true
ENABLE_PER_POD_LOGGING=true
S3_BUCKET=gpucloud-data  # Optional
```

## 🧪 **Test the Setup**

After manual setup, run the test script:

```bash
python3 test_per_pod_iam_setup.py
```

**Expected Output:**
```
🧪 Testing Per-Pod IAM Infrastructure Setup...
==================================================

📋 Environment Configuration:
✅ AWS_ACCESS_KEY_ID: AKIA...
✅ AWS_SECRET_ACCESS_KEY: ...
✅ AWS_REGION: us-east-1
✅ AWS_POD_PERMISSIONS_BOUNDARY: arn:aws:iam::458178359313:policy/gpucloud-pod-permissions-boundary

🔗 Testing AWS Connectivity:
✅ Connected to AWS Account: 458178359313
✅ User/Role: arn:aws:iam::458178359313:user/gpucloud-provisioner

🛡️ Testing Permissions Boundary:
✅ Permissions boundary exists: gpucloud-pod-permissions-boundary
✅ Policy ARN: arn:aws:iam::458178359313:policy/gpucloud-pod-permissions-boundary

🎮 Testing Control Plane Permissions:
✅ Can create IAM roles: arn:aws:iam::458178359313:role/gpucloud-test-role-temp
✅ Can create inline policies
✅ Can create instance profiles: arn:aws:iam::458178359313:instance-profile/gpucloud-test-role-temp
✅ Can attach roles to instance profiles

🧹 Cleaning up test resources...
✅ Test resources cleaned up successfully

📊 Testing CloudWatch Permissions:
✅ Can create CloudWatch log groups: /gpucloud/test/temp
✅ Test log group cleaned up successfully

🖥️ Testing EC2 Permissions:
✅ Can describe EC2 regions: 21 regions available
✅ Can describe EC2 instance types

==================================================
🎉 ALL TESTS PASSED! Per-Pod IAM infrastructure is ready.
==================================================
```

## 🚀 **After Setup is Complete**

1. **Run database migration:**
   ```bash
   cd apps/api
   alembic upgrade head
   ```

2. **Restart GPUCloud services:**
   ```bash
   ./gpucloud.sh restart
   ```

3. **Test via UI** using the `UI_TEST_CHECKLIST.md`

## 🔒 **Security Notes**

- **Permissions boundary** prevents privilege escalation
- **Control plane policy** is scoped to only pod resources
- **No cross-pod access** - complete isolation
- **Automatic cleanup** on pod deletion

## 🆘 **Troubleshooting**

### **Policy Creation Fails**
- Ensure you're using admin credentials
- Check AWS account limits
- Verify policy names don't already exist

### **Policy Attachment Fails**
- Verify user exists: `aws iam get-user --user-name gpucloud-provisioner`
- Check for conflicting policies
- Ensure policy ARN is correct

### **Test Script Fails**
- Verify all environment variables are set
- Check that policies were created successfully
- Ensure control plane policy is attached to user

---

**🎯 Once this manual setup is complete, the per-pod IAM feature will work automatically for all future pods!**
