# 🧪 **UI Test Checklist for Per-Pod IAM**

## **Pre-Test Setup**

### **1. Run Infrastructure Test**
```bash
# Test that everything is configured correctly
python3 test_per_pod_iam_setup.py
```

**Expected Output:**
- ✅ All environment variables set
- ✅ AWS connectivity working
- ✅ Permissions boundary exists
- ✅ Control plane permissions working
- ✅ CloudWatch permissions working
- ✅ EC2 permissions working

### **2. Start Services**
```bash
./gpucloud.sh start
```

**Check:**
- Backend API running on port 8080
- Frontend running on port 3000
- Worker processes running
- No error messages in logs

## **🧪 UI Testing Steps**

### **Step 1: Login & Verify Configuration**
1. **Open Web UI**: Navigate to your GPUCloud dashboard
2. **Login**: Use existing credentials or create new user
3. **Check Environment**: Verify no error messages about missing IAM configuration

**Expected Result:**
- ✅ Login successful
- ✅ Dashboard loads without errors
- ✅ No IAM-related error messages

### **Step 2: Create New Pod (Per-Pod IAM Test)**
1. **Navigate to Pods**: Click on "Pods" in the sidebar
2. **Click "Deploy New Pod"** or similar button
3. **Select Instance Type**: Choose `t3.micro` (cheapest for testing)
4. **Click Deploy**: Start the pod creation process

**Watch for:**
- ✅ Pod status changes from "pending" → "starting" → "running"
- ✅ No error messages about IAM roles or permissions
- ✅ Backend logs show IAM role creation messages

**Expected Backend Logs:**
```
[INFO] Creating pod 123 for customer 456
[INFO] Created log group: /gpucloud/456/123
[INFO] Created IAM role: arn:aws:iam::ACCOUNT:role/gpucloud-pod-123
[INFO] Created inline policy for role: gpucloud-pod-123
[INFO] Created instance profile: gpucloud-pod-123
[INFO] Launched EC2 instance: i-1234567890abcdef0
[INFO] Pod 123 provisioned successfully with per-pod IAM
```

### **Step 3: Verify Pod Details**
1. **Check Pod List**: View the newly created pod
2. **Verify IAM Info**: Look for new fields in pod details

**Expected Pod Data:**
```json
{
  "id": 123,
  "status": "running",
  "instance_type": "t3.micro",
  "role_name": "gpucloud-pod-123",
  "role_arn": "arn:aws:iam::ACCOUNT:role/gpucloud-pod-123",
  "instance_profile": "gpucloud-pod-123",
  "log_group": "/gpucloud/456/123",
  "uses_per_pod_iam": true
}
```

### **Step 4: Test CloudWatch Logs**
1. **Click on Pod**: Select the running pod
2. **Look for Logs Tab**: Should show CloudWatch logs option
3. **View Logs**: Click to see pod-specific logs

**Expected Result:**
- ✅ CloudWatch logs endpoint accessible
- ✅ Log entries visible (may be empty initially)
- ✅ Log group name matches pod

### **Step 5: Test Terminal Access**
1. **Click Terminal**: Open web terminal for the pod
2. **Verify SSM Connection**: Should connect via AWS SSM

**Expected Result:**
- ✅ Terminal opens successfully
- ✅ SSM session established
- ✅ Can run basic commands (e.g., `ls`, `pwd`)

### **Step 6: Verify AWS Console**
1. **Open AWS Console**: Navigate to IAM section
2. **Check IAM Roles**: Look for `gpucloud-pod-123` role
3. **Check Instance Profiles**: Look for `gpucloud-pod-123` profile
4. **Check CloudWatch**: Look for `/gpucloud/456/123` log group

**Expected AWS Resources:**
- ✅ IAM Role: `gpucloud-pod-123` with permissions boundary
- ✅ Instance Profile: `gpucloud-pod-123` with role attached
- ✅ CloudWatch Log Group: `/gpucloud/456/123`
- ✅ EC2 Instance: Tagged with pod metadata

### **Step 7: Test Pod Operations**
1. **Stop Pod**: Click stop button
2. **Start Pod**: Click start button
3. **Delete Pod**: Click delete button

**Expected Results:**
- ✅ Stop: Pod stops, instance preserved, IAM resources intact
- ✅ Start: Pod starts, uses existing IAM role and profile
- ✅ Delete: Pod deleted, IAM resources cleaned up

## **🔍 What to Look For**

### **Success Indicators**
- ✅ Pod creation completes in 2-5 minutes
- ✅ No IAM permission errors in backend logs
- ✅ AWS resources created with correct naming
- ✅ Pod shows `uses_per_pod_iam: true`
- ✅ CloudWatch logs accessible
- ✅ Terminal access works via SSM

### **Failure Indicators**
- ❌ Pod stuck in "starting" status
- ❌ Backend errors about IAM permissions
- ❌ Missing IAM fields in pod data
- ❌ CloudWatch logs not accessible
- ❌ Terminal connection failures

### **Common Issues & Solutions**

#### **1. Pod Stuck in "Starting"**
**Check:**
- Backend logs for IAM creation errors
- AWS console for failed resource creation
- Worker process logs for timeout issues

**Solution:**
- Verify permissions boundary exists
- Check control plane IAM permissions
- Restart worker processes

#### **2. IAM Role Creation Fails**
**Check:**
- Backend logs for specific error messages
- AWS credentials and permissions
- Permissions boundary policy

**Solution:**
- Run `setup_pod_iam_infrastructure.py`
- Verify backend role has control plane policy
- Check AWS account limits

#### **3. CloudWatch Logs Not Accessible**
**Check:**
- Pod has `log_group` field populated
- Backend has CloudWatch permissions
- Log group exists in AWS console

**Solution:**
- Verify `ENABLE_PER_POD_LOGGING=true`
- Check CloudWatch IAM permissions
- Restart backend service

## **📊 Testing Metrics**

### **Performance Benchmarks**
- **Pod Creation Time**: Should be 2-5 minutes (including IAM setup)
- **IAM Resource Creation**: Should be 30-60 seconds
- **EC2 Launch Time**: Should be 1-3 minutes
- **SSM Agent Ready**: Should be 1-2 minutes after instance running

### **Resource Usage**
- **IAM Roles**: 1 per pod
- **Instance Profiles**: 1 per pod  
- **CloudWatch Log Groups**: 1 per pod
- **EC2 Instances**: 1 per pod (when running)

## **🎯 Test Completion Checklist**

- [ ] Infrastructure test passes
- [ ] Services start without errors
- [ ] Pod creation completes successfully
- [ ] Pod shows per-pod IAM information
- [ ] CloudWatch logs are accessible
- [ ] Terminal access works via SSM
- [ ] AWS console shows created resources
- [ ] Pod stop/start operations work
- [ ] Pod deletion cleans up resources
- [ ] No error messages in any logs

## **🚀 Next Steps After Testing**

1. **Scale Testing**: Create multiple pods to test isolation
2. **Permission Testing**: Verify pods can't access other pod resources
3. **Logging Testing**: Generate some application logs to see in CloudWatch
4. **Performance Testing**: Test with larger instance types
5. **Cleanup Testing**: Verify all resources are properly cleaned up

---

**💡 Tip: Keep the backend logs open in a terminal while testing to see real-time IAM creation messages!**
