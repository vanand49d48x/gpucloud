#!/usr/bin/env python3
"""
Quick test script to verify per-pod IAM infrastructure setup
Run this before testing the full flow via UI
"""

import boto3
import os
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_per_pod_iam_setup():
    """Test that the per-pod IAM infrastructure is properly configured"""
    
    print("🧪 Testing Per-Pod IAM Infrastructure Setup...")
    print("=" * 50)
    
    # Check environment variables
    print("\n📋 Environment Configuration:")
    required_vars = [
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY', 
        'AWS_REGION',
        'AWS_POD_PERMISSIONS_BOUNDARY'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value[:20]}..." if len(value) > 20 else f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables: {missing_vars}")
        print("Please set these in your .env file and restart the application.")
        return False
    
    # Test AWS connectivity
    print("\n🔗 Testing AWS Connectivity:")
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ Connected to AWS Account: {identity['Account']}")
        print(f"✅ User/Role: {identity['Arn']}")
    except Exception as e:
        print(f"❌ AWS connection failed: {e}")
        return False
    
    # Test permissions boundary
    print("\n🛡️ Testing Permissions Boundary:")
    try:
        iam = boto3.client('iam')
        boundary_arn = os.getenv('AWS_POD_PERMISSIONS_BOUNDARY')
        
        response = iam.get_policy(PolicyArn=boundary_arn)
        print(f"✅ Permissions boundary exists: {response['Policy']['PolicyName']}")
        print(f"✅ Policy ARN: {response['Policy']['Arn']}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            print(f"❌ Permissions boundary not found: {boundary_arn}")
            print("Run setup_pod_iam_infrastructure.py first!")
            return False
        else:
            print(f"❌ Error checking permissions boundary: {e}")
            return False
    
    # Test control plane permissions
    print("\n🎮 Testing Control Plane Permissions:")
    try:
        # Test creating a temporary role (will be cleaned up)
        test_role_name = "gpucloud-test-role-temp"
        test_policy_name = "gpucloud-test-policy-temp"
        
        # Create test role
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        
        response = iam.create_role(
            RoleName=test_role_name,
            AssumeRolePolicyDocument=str(trust_policy),
            PermissionsBoundary=boundary_arn,
            Description="Temporary test role"
        )
        print(f"✅ Can create IAM roles: {response['Role']['Arn']}")
        
        # Test creating inline policy
        test_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["logs:CreateLogGroup"],
                "Resource": "*"
            }]
        }
        
        iam.put_role_policy(
            RoleName=test_role_name,
            PolicyName=test_policy_name,
            PolicyDocument=str(test_policy)
        )
        print("✅ Can create inline policies")
        
        # Test creating instance profile
        response = iam.create_instance_profile(
            InstanceProfileName=test_role_name
        )
        print(f"✅ Can create instance profiles: {response['InstanceProfile']['Arn']}")
        
        # Test adding role to profile
        iam.add_role_to_instance_profile(
            InstanceProfileName=test_role_name,
            RoleName=test_role_name
        )
        print("✅ Can attach roles to instance profiles")
        
        # Cleanup test resources
        print("\n🧹 Cleaning up test resources...")
        try:
            iam.remove_role_from_instance_profile(
                InstanceProfileName=test_role_name,
                RoleName=test_role_name
            )
            iam.delete_instance_profile(InstanceProfileName=test_role_name)
            iam.delete_role_policy(RoleName=test_role_name, PolicyName=test_policy_name)
            iam.delete_role(RoleName=test_role_name)
            print("✅ Test resources cleaned up successfully")
        except Exception as e:
            print(f"⚠️ Warning: Could not clean up test resources: {e}")
            print("You may need to clean these up manually in the AWS console")
        
    except ClientError as e:
        print(f"❌ Control plane permissions test failed: {e}")
        print("Make sure your backend role has the gpucloud-control-plane-policy attached")
        return False
    
    # Test CloudWatch permissions
    print("\n📊 Testing CloudWatch Permissions:")
    try:
        logs = boto3.client('logs')
        test_log_group = "/gpucloud/test/temp"
        
        response = logs.create_log_group(logGroupName=test_log_group)
        print(f"✅ Can create CloudWatch log groups: {test_log_group}")
        
        # Cleanup test log group
        logs.delete_log_group(logGroupName=test_log_group)
        print("✅ Test log group cleaned up successfully")
        
    except ClientError as e:
        print(f"❌ CloudWatch permissions test failed: {e}")
        return False
    
    # Test EC2 permissions
    print("\n🖥️ Testing EC2 Permissions:")
    try:
        ec2 = boto3.client('ec2')
        response = ec2.describe_regions()
        print(f"✅ Can describe EC2 regions: {len(response['Regions'])} regions available")
        
        # Test describing instance types (lightweight operation)
        response = ec2.describe_instance_types(MaxResults=1)
        print("✅ Can describe EC2 instance types")
        
    except ClientError as e:
        print(f"❌ EC2 permissions test failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 ALL TESTS PASSED! Per-Pod IAM infrastructure is ready.")
    print("=" * 50)
    print("\n🚀 Next steps:")
    print("1. Start your GPUCloud services: ./gpucloud.sh start")
    print("2. Open the web UI and try creating a new pod")
    print("3. Check the AWS console to see the per-pod IAM roles being created")
    print("4. Verify CloudWatch log groups are created for each pod")
    print("\n💡 Tip: Check the backend logs for detailed IAM creation messages")
    
    return True

if __name__ == "__main__":
    print("GPUCloud Per-Pod IAM Setup Test")
    print("Loading environment from .env file...")
    print()
    
    success = test_per_pod_iam_setup()
    
    if not success:
        print("\n❌ Setup test failed. Please fix the issues above before testing via UI.")
        exit(1)
