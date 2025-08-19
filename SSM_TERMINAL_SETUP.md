# AWS Systems Manager (SSM) Terminal Setup

This document explains how to set up and use the new **SSM-based terminal system** for multi-user, secure terminal access to EC2 instances.

## 🚀 **What We've Built**

### **Before (SSH-based):**
- ❌ **Single user only** - hardcoded SSH key
- ❌ **Security group changes** - need to open port 22
- ❌ **SSH key management** - complex key distribution
- ❌ **IP restrictions** - users need specific IP access

### **After (SSM-based):**
- ✅ **Multi-user support** - any number of users can connect
- ✅ **No security groups** - uses AWS internal networking
- ✅ **No SSH keys** - uses AWS IAM roles for security
- ✅ **Secure by default** - AWS handles authentication
- ✅ **Scalable** - works with any number of users

## 🔧 **Setup Steps**

### **Step 1: Create IAM Role and Instance Profile**

Run the setup script to create the required AWS resources:

```bash
cd mypods
python setup_ssm_role.py
```

This will create:
- **IAM Role**: `GPUCloud-SSM-Role` with SSM permissions
- **Instance Profile**: `GPUCloud-SSM-Profile` for EC2 instances

### **Step 2: Update Environment Variables**

Add the instance profile name to your `.env` file:

```bash
AWS_INSTANCE_PROFILE=GPUCloud-SSM-Profile
```

### **Step 3: Restart Services**

Restart your services to pick up the new configuration:

```bash
./gpucloud.sh restart
```

## 🧪 **Testing the Setup**

### **Test SSM Session Creation**

Run the test script to verify SSM is working:

```bash
python test_ssm_terminal.py
```

Enter an existing EC2 instance ID to test the connection.

### **Test in Web Interface**

1. **Deploy a new pod** - it will automatically use the SSM-enabled configuration
2. **Click the Terminal button** - should connect via SSM instead of SSH
3. **No more security group updates** - connection should work immediately

## 🔍 **How It Works**

### **Backend (FastAPI)**
- **WebSocket endpoint**: `/v1/pods/{pod_id}/terminal`
- **SSM session management**: Creates isolated sessions per user
- **User isolation**: Each user gets their own terminal session
- **No SSH keys**: Uses AWS IAM roles and SSM

### **Frontend (Next.js)**
- **WebSocket connection**: Connects to backend terminal endpoint
- **Real-time communication**: Commands and output via WebSocket
- **User-friendly interface**: Same terminal experience, better security

### **AWS Infrastructure**
- **EC2 instances**: Launched with SSM-enabled IAM role
- **SSM agent**: Automatically installed and running on instances
- **IAM permissions**: Instances can create SSM sessions
- **Internal networking**: No public port 22 needed

## 🚨 **Troubleshooting**

### **Common Issues**

#### **1. "SSM agent is not running"**
- **Cause**: Instance doesn't have the required IAM role
- **Solution**: Ensure `AWS_INSTANCE_PROFILE` is set and restart services

#### **2. "Failed to create SSM session"**
- **Cause**: Instance not running or SSM agent not ready
- **Solution**: Wait for instance to fully start, then try again

#### **3. "Access denied" errors**
- **Cause**: IAM role permissions insufficient
- **Solution**: Verify the role has `AmazonSSMManagedInstanceCore` policy

### **Debugging Steps**

1. **Check IAM role**: Verify `GPUCloud-SSM-Role` exists and has SSM policy
2. **Check instance profile**: Ensure `GPUCloud-SSM-Profile` is attached to instances
3. **Check SSM agent**: Verify agent is running on instances
4. **Check logs**: Look at backend logs for detailed error messages

## 🔒 **Security Benefits**

### **Multi-User Isolation**
- Each user gets their own SSM session
- No shared SSH keys or credentials
- Sessions are isolated and secure

### **AWS Security**
- Uses AWS IAM roles for authentication
- No public SSH ports needed
- All communication via AWS internal network

### **Audit Trail**
- All SSM sessions are logged by AWS
- User actions are tracked and auditable
- No SSH key management overhead

## 📚 **API Endpoints**

### **WebSocket Terminal**
```
GET /v1/pods/{pod_id}/terminal?instance_id={instance_id}&token={token}
```

### **Terminal Status**
```
GET /v1/pods/{pod_id}/terminal/status
```

### **Security Group Update** (Legacy - not needed for SSM)
```
POST /v1/pods/{pod_id}/security-group/update
```

## 🎯 **Next Steps**

### **Immediate**
1. ✅ Run `setup_ssm_role.py`
2. ✅ Set `AWS_INSTANCE_PROFILE` in `.env`
3. ✅ Restart services with `./gpucloud.sh restart`
4. ✅ Test with a new pod deployment

### **Future Enhancements**
- **Session persistence**: Save terminal sessions across page reloads
- **Command history**: Store and retrieve command history
- **File transfer**: Add file upload/download capabilities
- **Multi-tab support**: Allow multiple terminal sessions per user

## 🤝 **Support**

If you encounter issues:

1. **Check the logs**: Look at backend and frontend console logs
2. **Verify AWS setup**: Ensure IAM role and instance profile exist
3. **Test SSM manually**: Use `test_ssm_terminal.py` to isolate issues
4. **Check instance status**: Verify EC2 instances are running and SSM-ready

---

**🎉 Congratulations!** You now have a **multi-user, secure, scalable terminal system** that works with any number of users without SSH key management headaches.
