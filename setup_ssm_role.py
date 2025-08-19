#!/usr/bin/env python3
"""
Setup script for AWS SSM IAM role and instance profile
This script creates the necessary IAM resources for EC2 instances to use SSM
"""

import boto3
import json
from botocore.exceptions import ClientError

def create_ssm_role():
    """Create IAM role for SSM access"""
    
    # Initialize IAM client
    iam = boto3.client('iam')
    
    # Trust policy for EC2 instances
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    # SSM managed policy ARN
    ssm_policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
    
    try:
        # Create the role
        role_name = "GPUCloud-SSM-Role"
        print(f"Creating IAM role: {role_name}")
        
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for EC2 instances to use AWS Systems Manager"
        )
        
        role_arn = response['Role']['Arn']
        print(f"Created role: {role_arn}")
        
        # Attach SSM managed policy
        print("Attaching SSM managed policy...")
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn=ssm_policy_arn
        )
        
        print("SSM policy attached successfully")
        
        # Create instance profile
        profile_name = "GPUCloud-SSM-Profile"
        print(f"Creating instance profile: {profile_name}")
        
        response = iam.create_instance_profile(
            InstanceProfileName=profile_name
        )
        
        profile_arn = response['InstanceProfile']['Arn']
        print(f"Created instance profile: {profile_arn}")
        
        # Add role to instance profile
        print("Adding role to instance profile...")
        iam.add_role_to_instance_profile(
            InstanceProfileName=profile_name,
            RoleName=role_name
        )
        
        print("Role added to instance profile successfully")
        
        print("\n" + "="*50)
        print("SETUP COMPLETE!")
        print("="*50)
        print(f"Role Name: {role_name}")
        print(f"Role ARN: {role_arn}")
        print(f"Instance Profile Name: {profile_name}")
        print(f"Instance Profile ARN: {profile_arn}")
        print("\nAdd this to your .env file:")
        print(f"AWS_INSTANCE_PROFILE={profile_name}")
        print("="*50)
        
        return profile_name
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"Role or profile already exists. Checking current setup...")
            
            # Get existing role
            try:
                role_response = iam.get_role(RoleName=role_name)
                print(f"Role exists: {role_response['Role']['Arn']}")
                
                # Get existing instance profile
                profile_response = iam.get_instance_profile(InstanceProfileName=profile_name)
                print(f"Instance profile exists: {profile_response['InstanceProfile']['Arn']}")
                
                print(f"\nUse this in your .env file:")
                print(f"AWS_INSTANCE_PROFILE={profile_name}")
                
                return profile_name
                
            except ClientError as e2:
                print(f"Error checking existing resources: {e2}")
                return None
        else:
            print(f"Error creating IAM resources: {e}")
            return None

if __name__ == "__main__":
    print("Setting up AWS SSM IAM role and instance profile...")
    print("Make sure you have AWS credentials configured!")
    print()
    
    profile_name = create_ssm_role()
    
    if profile_name:
        print(f"\nSetup completed successfully!")
        print(f"Instance profile name: {profile_name}")
    else:
        print("\nSetup failed. Check the error messages above.")
