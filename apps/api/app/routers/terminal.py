from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import boto3
import json
import asyncio
import subprocess
import os
import paramiko
from datetime import datetime, timedelta

from apps.api.app.db import get_session
from apps.api.app.models import Pod
from apps.api.app.deps import current_user
from apps.api.app.config import settings

# Request models
class SecurityGroupUpdateRequest(BaseModel):
    user_ip: str

router = APIRouter(prefix="/v1/pods", tags=["terminal"])
security = HTTPBearer()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}

    async def connect(self, websocket: WebSocket, pod_id: int):
        await websocket.accept()
        self.active_connections[pod_id] = websocket

    def disconnect(self, pod_id: int):
        if pod_id in self.active_connections:
            del self.active_connections[pod_id]

    async def send_message(self, pod_id: int, message: str):
        if pod_id in self.active_connections:
            await self.active_connections[pod_id].send_text(message)

manager = ConnectionManager()

@router.websocket("/{pod_id}/terminal")
async def websocket_terminal(
    websocket: WebSocket, 
    pod_id: int, 
    instance_id: str = Query(...),
    token: str = Query(None)
):
    """WebSocket endpoint for terminal access to EC2 instances"""
    
    # Validate token and get user
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    
    try:
        # Decode and validate JWT token
        # This is a simplified version - you should use proper JWT validation
        user_id = "3"  # For now, hardcoded - implement proper JWT validation
        
        # Get pod details
        db = next(get_session())
        pod = db.get(Pod, pod_id)
        
        if not pod:
            await websocket.close(code=4004, reason="Pod not found")
            return
            
        if pod.status != "running":
            await websocket.close(code=4005, reason="Pod not running")
            return
        
        await manager.connect(websocket, pod_id)
        
        try:
            # Send welcome message
            await websocket.send_text(json.dumps({
                "type": "system",
                "content": f"Connected to {pod.instance_type} instance"
            }))
            
            # Handle terminal commands
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message["type"] == "command":
                    command = message["content"]
                    
                    # Execute command on EC2 instance via SSH
                    result = await execute_ssh_command(
                        pod.public_ip, 
                        command, 
                        pod.instance_type
                    )
                    
                    # Send result back to client
                    await websocket.send_text(json.dumps({
                        "type": "output",
                        "content": result
                    }))
                    
        except WebSocketDisconnect:
            manager.disconnect(pod_id)
            
    except Exception as e:
        await websocket.close(code=4000, reason=f"Error: {str(e)}")

async def execute_ssh_command(public_ip: str, command: str, instance_type: str) -> str:
    """Execute SSH command on EC2 instance using paramiko"""
    try:
        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Get SSH key path from environment
        ssh_key_path = os.path.expanduser('~/.ssh/gpucloud-mvp-key')
        
        # Connect to instance
        ssh.connect(
            public_ip,
            username='ubuntu',
            key_filename=ssh_key_path,
            timeout=10
        )
        
        # Execute command
        stdin, stdout, stderr = ssh.exec_command(command)
        
        # Get output
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        # Close connection
        ssh.close()
        
        # Return result
        result = f"$ {command}\n"
        if output:
            result += output
        if error:
            result += f"Error: {error}\n"
            
        return result
        
    except Exception as e:
        return f"Error executing command: {str(e)}\n"

@router.post("/{pod_id}/security-group/update")
async def update_security_group(
    pod_id: int,
    request: SecurityGroupUpdateRequest,
    db: Session = Depends(get_session),
    current_user = Depends(current_user)
):
    """Update security group to allow SSH access from user's IP"""
    
    try:
        # Get pod details
        pod = db.get(Pod, pod_id)
        if not pod:
            raise HTTPException(status_code=404, detail="Pod not found")
        
        if not pod.instance_id:
            raise HTTPException(status_code=400, detail="Pod has no instance ID")
        
        # Initialize AWS client
        ec2_client = boto3.client(
            'ec2',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        # Get instance details to find security groups
        response = ec2_client.describe_instances(InstanceIds=[pod.instance_id])
        if not response['Reservations']:
            raise HTTPException(status_code=404, detail="Instance not found")
        
        instance = response['Reservations'][0]['Instances'][0]
        security_groups = instance['SecurityGroups']
        
        # Update each security group to allow SSH from user's IP
        for sg in security_groups:
            sg_id = sg['GroupId']
            
            # Check if rule already exists
            try:
                response = ec2_client.describe_security_groups(GroupIds=[sg_id])
                sg_rules = response['SecurityGroups'][0]['IpPermissions']
                
                # Check if SSH rule for this IP already exists
                ssh_rule_exists = False
                for rule in sg_rules:
                    if (rule.get('FromPort') == 22 and 
                        rule.get('ToPort') == 22 and 
                        rule.get('IpProtocol') == 'tcp'):
                        for ip_range in rule.get('IpRanges', []):
                            if ip_range['CidrIp'] == f"{request.user_ip}/32":
                                ssh_rule_exists = True
                                break
                
                if not ssh_rule_exists:
                    # Add SSH rule for user's IP
                    ec2_client.authorize_security_group_ingress(
                        GroupId=sg_id,
                        IpPermissions=[{
                            'IpProtocol': 'tcp',
                            'FromPort': 22,
                            'ToPort': 22,
                            'IpRanges': [{'CidrIp': f"{request.user_ip}/32"}]
                        }]
                    )
                    
                    # Schedule removal of this rule after 1 hour
                    asyncio.create_task(remove_security_group_rule_later(sg_id, request.user_ip, 3600))
                    
            except Exception as e:
                # Log error but continue with other security groups
                print(f"Error updating security group {sg_id}: {e}")
        
        return {
            "message": f"Security group updated to allow SSH from {request.user_ip}",
            "user_ip": request.user_ip,
            "expires_in": "1 hour"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update security group: {str(e)}")

async def remove_security_group_rule_later(sg_id: str, user_ip: str, delay_seconds: int):
    """Remove security group rule after specified delay"""
    await asyncio.sleep(delay_seconds)
    
    try:
        ec2_client = boto3.client(
            'ec2',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        ec2_client.revoke_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{'CidrIp': f"{user_ip}/32"}]
            }]
        )
        
        print(f"Removed SSH access for {user_ip} from security group {sg_id}")
        
    except Exception as e:
        print(f"Error removing security group rule: {e}")

@router.get("/{pod_id}/ssh-info")
async def get_ssh_info(
    pod_id: int,
    db: Session = Depends(get_session),
    current_user = Depends(current_user)
):
    """Get SSH connection information for a pod"""
    
    pod = db.query(Pod).filter(Pod.id == pod_id).first()
    if not pod:
        raise HTTPException(status_code=404, detail="Pod not found")
    
    if not pod.instance_id or not pod.public_ip:
        raise HTTPException(status_code=400, detail="Pod not ready for SSH access")
    
    return {
        "pod_id": pod_id,
        "instance_id": pod.instance_id,
        "public_ip": pod.public_ip,
        "instance_type": pod.instance_type,
        "ssh_command": f"ssh -i ~/.ssh/gpucloud-mvp-key ubuntu@{pod.public_ip}",
        "username": "ubuntu",
        "port": 22,
        "key_name": "gpucloud-mvp-key"
    }
