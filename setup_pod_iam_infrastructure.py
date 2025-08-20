#!/usr/bin/env python3
"""
One-time setup script for GPUCloud per-pod IAM infrastructure
This script creates the permissions boundary and grants necessary permissions to the control plane
"""

import boto3
import json
import os
from botocore.exceptions import ClientError

def setup_pod_iam_infrastructure():
    """Setup the one-time IAM infrastructure for per-pod IAM roles"""
    
    # Initialize clients
    iam = boto3.client('iam')
    sts = boto3.client('sts')
    
    # Get account ID
    account_id = sts.get_caller_identity()["Account"]
    print(f"Setting up IAM infrastructure for account: {account_id}")
    
    # 1. Create permissions boundary policy
    boundary_policy_name = "gpucloud-pod-permissions-boundary"
    boundary_policy_arn = f"arn:aws:iam::{account_id}:policy/{boundary_policy_name}"
    
    try:
        # Read the permissions boundary document
        with open('infra/iam/pod-permissions-boundary.json', 'r') as f:
            boundary_document = json.load(f)
        
        print(f"Creating permissions boundary policy: {boundary_policy_name}")
        iam.create_policy(
            PolicyName=boundary_policy_name,
            PolicyDocument=json.dumps(boundary_document),
            Description="Permissions boundary for GPUCloud pod IAM roles"
        )
        print(f"✅ Created permissions boundary: {boundary_policy_arn}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"✅ Permissions boundary already exists: {boundary_policy_arn}")
        else:
            print(f"❌ Error creating permissions boundary: {e}")
            return False
    
    # 2. Create control plane role policy (if it doesn't exist)
    control_plane_policy_name = "gpucloud-control-plane-policy"
    control_plane_policy_arn = f"arn:aws:iam::{account_id}:policy/{control_plane_policy_name}"
    
    control_plane_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "iam:CreateRole",
                    "iam:TagRole",
                    "iam:PutRolePolicy",
                    "iam:CreateInstanceProfile",
                    "iam:AddRoleToInstanceProfile",
                    "iam:PassRole"
                ],
                "Resource": [
                    f"arn:aws:iam::{account_id}:role/gpucloud-pod-*",
                    f"arn:aws:iam::{account_id}:instance-profile/gpucloud-pod-*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:RunInstances",
                    "ec2:CreateTags",
                    "ec2:DescribeInstances",
                    "ec2:StartInstances",
                    "ec2:StopInstances",
                    "ec2:TerminateInstances",
                    "ec2:ModifyVolume",
                    "ec2:DescribeVolumes"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:PutRetentionPolicy",
                    "logs:DescribeLogGroups"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ssm:StartSession",
                    "ssm:DescribeInstanceInformation",
                    "ssm:SendCommand",
                    "ssm:GetCommandInvocation"
                ],
                "Resource": "*"
            }
        ]
    }
    
    try:
        print(f"Creating control plane policy: {control_plane_policy_name}")
        iam.create_policy(
            PolicyName=control_plane_policy_name,
            PolicyDocument=json.dumps(control_plane_policy),
            Description="Policy for GPUCloud control plane to manage pod resources"
        )
        print(f"✅ Created control plane policy: {control_plane_policy_arn}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"✅ Control plane policy already exists: {control_plane_policy_arn}")
        else:
            print(f"❌ Error creating control plane policy: {e}")
            return False
    
    print("\n" + "="*60)
    print("🎉 POD IAM INFRASTRUCTURE SETUP COMPLETE!")
    print("="*60)
    print(f"Permissions Boundary: {boundary_policy_arn}")
    print(f"Control Plane Policy: {control_plane_policy_arn}")
    print("\nNext steps:")
    print("1. Attach the control plane policy to your backend role/user")
    print("2. Update your .env file with the boundary ARN:")
    print(f"   AWS_POD_PERMISSIONS_BOUNDARY={boundary_policy_arn}")
    print("3. Restart your GPUCloud services")
    print("="*60)
    
    return True

if __name__ == "__main__":
    print("Setting up GPUCloud per-pod IAM infrastructure...")
    print("Make sure you have AWS credentials configured with admin permissions!")
    print()
    
    success = setup_pod_iam_infrastructure()
    
    if success:
        print("\n✅ Setup completed successfully!")
    else:
        print("\n❌ Setup failed. Check the error messages above.")
        exit(1)


