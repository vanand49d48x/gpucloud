"""
GPUCloud Per-Pod Creator Service
Automatically creates per-pod IAM roles, instance profiles, CloudWatch log groups, and EC2 instances
"""

import boto3
import json
import time
import base64
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError, WaiterError
from .config import settings

logger = logging.getLogger(__name__)

class PodCreator:
    def _get_instance_details(self, instance_id: str) -> dict:
        """Fetch public and private IPs for the given EC2 instance ID."""
        try:
            response = self.ec2.describe_instances(InstanceIds=[instance_id])
            reservations = response.get('Reservations', [])
            if not reservations or not reservations[0]['Instances']:
                logger.warning(f"No instance details found for {instance_id}")
                return {}
            instance = reservations[0]['Instances'][0]
            public_ip = instance.get('PublicIpAddress')
            private_ip = instance.get('PrivateIpAddress')
            return {
                "public_ip": public_ip,
                "private_ip": private_ip
            }
        except Exception as e:
            logger.error(f"Error fetching instance details for {instance_id}: {e}")
            return {}
    """Service for creating fully isolated per-pod infrastructure"""
    
    def __init__(self):
        self.region = settings.AWS_REGION
        self.account_id = None
        self.boundary_arn = None
        
        # Initialize AWS clients
        self.iam = boto3.client('iam', region_name=self.region)
        self.ec2 = boto3.client('ec2', region_name=self.region)
        self.logs = boto3.client('logs', region_name=self.region)
        self.sts = boto3.client('sts', region_name=self.region)
        
        # Get account ID and boundary ARN
        self._initialize_account_info()
    
    def _initialize_account_info(self):
        """Initialize account ID and permissions boundary ARN"""
        try:
            self.account_id = self.sts.get_caller_identity()["Account"]
            self.boundary_arn = getattr(settings, 'AWS_POD_PERMISSIONS_BOUNDARY', 
                                      f"arn:aws:iam::{self.account_id}:policy/gpucloud-pod-permissions-boundary")
            logger.info(f"Initialized PodCreator for account {self.account_id} with boundary {self.boundary_arn}")
        except Exception as e:
            logger.error(f"Failed to initialize account info: {e}")
            raise
    
    def create_pod(self, customer_id: str, pod_id: str, ami_id: str, instance_type: str, 
                   subnet_id: str, sg_id: str, key_name: Optional[str] = None, 
                   volume_size_gb: int = 60) -> Dict[str, Any]:
        """
        Create a fully isolated pod with per-pod IAM role, instance profile, log group, and EC2 instance
        
        Args:
            customer_id: Customer identifier
            pod_id: Unique pod identifier
            ami_id: AMI ID to use
            instance_type: EC2 instance type
            subnet_id: Subnet ID for the instance
            sg_id: Security group ID
            key_name: Optional SSH key name
            volume_size_gb: Root volume size in GB
            
        Returns:
            Dict containing created resource information
        """
        logger.info(f"Creating pod {pod_id} for customer {customer_id}")
        
        # Resource names - use AWS-default naming
        role_name = f"Pod{pod_id}"
        ip_name = f"Pod{pod_id}"  # Use simplest possible naming
        log_group = f"/gpucloud/{customer_id}/{pod_id}"
        
        try:
            # 1. Create CloudWatch log group
            self._create_log_group(log_group, customer_id, pod_id)
            
            # 2. Create IAM role with permissions boundary
            role_arn = self._create_iam_role(role_name, customer_id, pod_id, log_group)
            
            # 3. Create inline policy for the role
            self._create_role_policy(role_name, log_group, customer_id)
            
            # 4. Create instance profile
            self._create_instance_profile(ip_name, role_name, customer_id, pod_id)
            
            # 5. Launch EC2 instance
            instance_id = self._launch_ec2_instance(
                ami_id, instance_type, subnet_id, sg_id, ip_name, 
                customer_id, pod_id, key_name, volume_size_gb
            )
            
            # 6. Wait for instance to be running
            self._wait_for_instance_running(instance_id)
            
            # 7. Get instance details
            instance_details = self._get_instance_details(instance_id)
            
            result = {
                "role_name": role_name,
                "role_arn": role_arn,
                "instance_profile": ip_name,
                "instance_id": instance_id,
                "log_group": log_group,
                "public_ip": instance_details.get("public_ip"),
                "private_ip": instance_details.get("private_ip"),
                "status": "running"
            }
            
            logger.info(f"Successfully created pod {pod_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create pod {pod_id}: {e}")
            # Cleanup on failure
            self._cleanup_failed_pod(role_name, ip_name, log_group)
            raise
    
    def _create_log_group(self, log_group: str, customer_id: str, pod_id: str):
        """Create CloudWatch log group for the pod"""
        try:
            self.logs.create_log_group(
                logGroupName=log_group,
                tags={
                    "customer-id": customer_id,
                    "pod-id": pod_id,
                    "product": "gpucloud"
                }
            )
            self.logs.put_retention_policy(
                logGroupName=log_group,
                retentionInDays=14
            )
            logger.info(f"Created log group: {log_group}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceAlreadyExistsException':
                logger.info(f"Log group already exists: {log_group}")
            else:
                raise
    
    def _create_iam_role(self, role_name: str, customer_id: str, pod_id: str, log_group: str) -> str:
        """Create IAM role with permissions boundary"""
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        
        try:
            response = self.iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                PermissionsBoundary=self.boundary_arn,
                Tags=[
                    {"Key": "customer-id", "Value": customer_id},
                    {"Key": "pod-id", "Value": pod_id},
                    {"Key": "product", "Value": "gpucloud"}
                ]
            )
            role_arn = response["Role"]["Arn"]
            logger.info(f"Created IAM role: {role_arn}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExistsException':
                response = self.iam.get_role(RoleName=role_name)
                role_arn = response["Role"]["Arn"]
                logger.info(f"Using existing IAM role: {role_arn}")
            else:
                raise
        
        return role_arn
    
    def _create_role_policy(self, role_name: str, log_group: str, customer_id: str):
        """Create inline policy for the pod role"""
        inline_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "SSMCore",
                    "Effect": "Allow",
                    "Action": [
                        "ssmmessages:CreateControlChannel",
                        "ssmmessages:CreateDataChannel",
                        "ssmmessages:OpenControlChannel",
                        "ssmmessages:OpenDataChannel",
                        "ec2messages:*",
                        "ssm:UpdateInstanceInformation"
                    ],
                    "Resource": "*"
                },
                {
                    "Sid": "LogsPod",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogStreams"
                    ],
                    "Resource": f"arn:aws:logs:{self.region}:{self.account_id}:log-group:{log_group}:*"
                }
            ]
        }
        
        # Add S3 permissions if S3 bucket is configured
        s3_bucket = getattr(settings, 'S3_BUCKET', None)
        if s3_bucket:
            inline_policy["Statement"].extend([
                {
                    "Sid": "S3ListBucket",
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket"],
                    "Resource": f"arn:aws:s3:::{s3_bucket}",
                    "Condition": {"StringLike": {"s3:prefix": [f"{customer_id}/*"]}}
                },
                {
                    "Sid": "S3PrefixRW",
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:List*"
                    ],
                    "Resource": f"arn:aws:s3:::{s3_bucket}/{customer_id}/*"
                }
            ])
        
        self.iam.put_role_policy(
            RoleName=role_name,
            PolicyName="gpucloud-pod-inline",
            PolicyDocument=json.dumps(inline_policy)
        )
        logger.info(f"Created inline policy for role: {role_name}")
    
    def _create_instance_profile(self, ip_name: str, role_name: str, customer_id: str, pod_id: str):
        """Create instance profile and attach role"""
        try:
            self.iam.create_instance_profile(
                InstanceProfileName=ip_name,
                Tags=[
                    {"Key": "customer-id", "Value": customer_id},
                    {"Key": "pod-id", "Value": pod_id},
                    {"Key": "product", "Value": "gpucloud"}
                ]
            )
            logger.info(f"Created instance profile: {ip_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExistsException':
                logger.info(f"Instance profile already exists: {ip_name}")
            else:
                logger.error(f"Error creating instance profile {ip_name}: {e}")
                raise

        # Ensure role is attached to profile
        try:
            profile = self.iam.get_instance_profile(InstanceProfileName=ip_name)["InstanceProfile"]
            if not any(r["RoleName"] == role_name for r in profile.get("Roles", [])):
                self.iam.add_role_to_instance_profile(
                    InstanceProfileName=ip_name,
                    RoleName=role_name
                )
                logger.info(f"Attached role {role_name} to instance profile {ip_name}")
        except Exception as e:
            logger.error(f"Failed to attach role to instance profile: {e}")
            raise

        # Wait for instance profile to propagate (up to 60 seconds)
        import time
        max_retries = 30
        wait_seconds = 2
        for attempt in range(max_retries):
            try:
                self.iam.get_instance_profile(InstanceProfileName=ip_name)
                logger.info(f"Instance profile {ip_name} is now available (attempt {attempt+1}, waited {attempt*wait_seconds}s)")
                break
            except ClientError as e:
                logger.warning(f"Waiting for instance profile {ip_name} to propagate (attempt {attempt+1}, waited {attempt*wait_seconds}s): {e}")
                time.sleep(wait_seconds)
        else:
            logger.error(f"Instance profile {ip_name} did not propagate after {max_retries*wait_seconds} seconds")
            raise RuntimeError(f"Instance profile {ip_name} not available after {max_retries*wait_seconds} seconds")
    
    def _launch_ec2_instance(self, ami_id: str, instance_type: str, subnet_id: str, sg_id: str,
                            ip_name: str, customer_id: str, pod_id: str, key_name: Optional[str],
                            volume_size_gb: int) -> str:
        """Launch EC2 instance with all necessary configurations"""
        
        # Cloud-init user data
        user_data = f"""#cloud-config
package_update: true
runcmd:
  - sysctl -w net.ipv4.tcp_keepalive_time=60
  - systemctl enable amazon-ssm-agent && systemctl start amazon-ssm-agent
  - echo "GPUCloud pod {pod_id} initialized successfully"
"""
        
        # Tags for all resources
        tags = [
            {"Key": "customer-id", "Value": customer_id},
            {"Key": "pod-id", "Value": pod_id},
            {"Key": "product", "Value": "gpucloud"},
            {"Key": "created-by", "Value": "gpucloud-pod-creator"}
        ]
        
        # Wait a moment for instance profile to propagate
        import time
        time.sleep(2)
        
        # Wait 60 seconds after attaching role to profile for AWS propagation
        import time
        logger.info("Waiting 60 seconds for IAM instance profile propagation...")
        time.sleep(60)

        # Launch instance using profile Name (recommended by AWS)
        response = self.ec2.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            MaxCount=1,
            MinCount=1,
            SubnetId=subnet_id,
            SecurityGroupIds=[sg_id],
            IamInstanceProfile={"Name": ip_name},
            KeyName=key_name if key_name else None,
            TagSpecifications=[
                {"ResourceType": "instance", "Tags": tags},
                {"ResourceType": "volume", "Tags": tags},
                {"ResourceType": "network-interface", "Tags": tags}
            ],
            MetadataOptions={
                "HttpTokens": "required",
                "HttpPutResponseHopLimit": 1
            },
            BlockDeviceMappings=[{
                "DeviceName": "/dev/xvda",
                "Ebs": {
                    "Encrypted": True,
                    "DeleteOnTermination": True,
                    "VolumeType": "gp3",
                    "VolumeSize": volume_size_gb
                }
            }],
            UserData=base64.b64encode(user_data.encode()).decode()
        )
        
        instance_id = response["Instances"][0]["InstanceId"]
        logger.info(f"Launched EC2 instance: {instance_id}")
        return instance_id
    
    def _wait_for_instance_running(self, instance_id: str):
        """Wait for instance to be running"""
        try:
            logger.info(f"Waiting for instance {instance_id} to be running...")
            waiter = self.ec2.get_waiter("instance_running")
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={'Delay': 10, 'MaxAttempts': 30}
            )
            logger.info(f"Instance {instance_id} is now running")
        except WaiterError as e:
            logger.error(f"Instance {instance_id} failed to reach running state: {e}")
        import time
        logger.info("Waiting 60 seconds for IAM instance profile propagation...")
        time.sleep(60)
        """Get instance details including IP addresses"""
        try:
            response = self.ec2.describe_instances(InstanceIds=[instance_id])
            if response['Reservations']:
                instance = response['Reservations'][0]['Instances'][0]
                return {
                    "public_ip": instance.get("PublicIpAddress"),
                    "private_ip": instance.get("PrivateIpAddress"),
                    "state": instance["State"]["Name"]
                }
        except Exception as e:
            logger.error(f"Failed to get instance details: {e}")
        
        return {}
    
    def _cleanup_failed_pod(self, role_name: str, ip_name: str, log_group: str):
        """Cleanup resources if pod creation fails"""
        logger.warning(f"Cleaning up failed pod resources...")
        
        try:
            # Remove role from instance profile
            try:
                self.iam.remove_role_from_instance_profile(
                    InstanceProfileName=ip_name,
                    RoleName=role_name
                )
            except:
                pass
            
            # Delete instance profile
            try:
                self.iam.delete_instance_profile(InstanceProfileName=ip_name)
            except:
                pass
            
            # Delete IAM role
            try:
                self.iam.delete_role(RoleName=role_name)
            except:
                pass
            
            # Note: Don't delete log group as it might contain useful error logs
            
        except Exception as e:
            logger.error(f"Failed to cleanup resources: {e}")
    
    def delete_pod(self, pod_id: str, customer_id: str) -> bool:
        """Delete a pod and all associated resources"""
        logger.info(f"Deleting pod {pod_id} for customer {customer_id}")
        
        role_name = f"gpucloud-pod-{pod_id}"
        ip_name = role_name
        log_group = f"/gpucloud/{customer_id}/{pod_id}"
        
        try:
            # Get instance ID first
            instances = self.ec2.describe_instances(
                Filters=[
                    {'Name': 'tag:pod-id', 'Values': [pod_id]},
                    {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}
                ]
            )
            
            instance_ids = []
            for reservation in instances['Reservations']:
                for instance in reservation['Instances']:
                    instance_ids.append(instance['InstanceId'])
            
            # Terminate instances
            if instance_ids:
                self.ec2.terminate_instances(InstanceIds=instance_ids)
                logger.info(f"Terminated instances: {instance_ids}")
                
                # Wait for termination
                waiter = self.ec2.get_waiter("instance_terminated")
                waiter.wait(InstanceIds=instance_ids)
            
            # Cleanup IAM resources
            self._cleanup_failed_pod(role_name, ip_name, log_group)
            
            # Delete log group
            try:
                self.logs.delete_log_group(logGroupName=log_group)
                logger.info(f"Deleted log group: {log_group}")
            except:
                pass
            
            logger.info(f"Successfully deleted pod {pod_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete pod {pod_id}: {e}")
            return False

