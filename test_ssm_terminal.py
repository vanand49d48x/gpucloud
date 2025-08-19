#!/usr/bin/env python3
"""
Test script for SSM-based terminal functionality
This script tests the basic SSM session creation and management
"""

import boto3
import json
from botocore.exceptions import ClientError

def test_ssm_session(instance_id: str):
    """Test creating an SSM session to an EC2 instance"""
    
    try:
        # Initialize SSM client
        ssm_client = boto3.client('ssm', region_name='us-east-1')
        
        print(f"Testing SSM session creation for instance: {instance_id}")
        
        # Check if instance is running
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        
        if not response['Reservations']:
            print(f"Instance {instance_id} not found")
            return False
            
        instance = response['Reservations'][0]['Instances'][0]
        state = instance['State']['Name']
        
        print(f"Instance state: {state}")
        
        if state != 'running':
            print(f"Instance must be running to create SSM session. Current state: {state}")
            return False
        
        # Check if instance has SSM agent running
        try:
            print("Checking SSM agent status...")
            response = ssm_client.describe_instance_information(
                Filters=[
                    {
                        'Key': 'InstanceIds',
                        'Values': [instance_id]
                    }
                ]
            )
            
            if response['InstanceInformationList']:
                print("✓ SSM agent is running on the instance")
            else:
                print("✗ SSM agent is not running on the instance")
                print("The instance may not have the required IAM role or SSM agent")
                return False
                
        except ClientError as e:
            print(f"Error checking SSM agent: {e}")
            return False
        
        # Try to create a session
        try:
            print("Attempting to create SSM session...")
            response = ssm_client.start_session(
                Target=instance_id,
                DocumentName='AWS-StartInteractiveCommand',
                Parameters={
                    'command': ['/bin/bash'],
                    'workingDirectory': ['/home/ubuntu']
                }
            )
            
            session_id = response['SessionId']
            print(f"✓ SSM session created successfully!")
            print(f"Session ID: {session_id}")
            print(f"Stream URL: {response['StreamUrl']}")
            
            # Terminate the session immediately (just testing)
            print("Terminating test session...")
            ssm_client.terminate_session(SessionId=session_id)
            print("✓ Test session terminated")
            
            return True
            
        except ClientError as e:
            print(f"✗ Failed to create SSM session: {e}")
            return False
            
    except Exception as e:
        print(f"Error testing SSM session: {e}")
        return False

def main():
    """Main test function"""
    print("SSM Terminal Test Script")
    print("=" * 40)
    
    # Get instance ID from user
    instance_id = input("Enter EC2 instance ID to test (or press Enter to skip): ").strip()
    
    if not instance_id:
        print("Skipping SSM test. Make sure to:")
        print("1. Run setup_ssm_role.py to create IAM role")
        print("2. Set AWS_INSTANCE_PROFILE in your .env file")
        print("3. Deploy a new instance with the SSM-enabled role")
        print("4. Test the terminal button in the web interface")
        return
    
    # Test SSM session
    success = test_ssm_session(instance_id)
    
    if success:
        print("\n✓ SSM terminal test passed!")
        print("Your instances should now support web-based terminals")
    else:
        print("\n✗ SSM terminal test failed!")
        print("Check the error messages above and ensure:")
        print("1. IAM role is properly configured")
        print("2. Instance has the required IAM role")
        print("3. SSM agent is running on the instance")

if __name__ == "__main__":
    main()
