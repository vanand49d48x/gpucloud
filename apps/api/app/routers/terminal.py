from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import Optional, Dict
from pydantic import BaseModel
import boto3
import json
import asyncio
import os
import time
from datetime import datetime, timedelta
import logging

from apps.api.app.db import get_session
from apps.api.app.models import Pod
from apps.api.app.deps import current_user
from apps.api.app.config import settings

# Request models
class SecurityGroupUpdateRequest(BaseModel):
	user_ip: str

router = APIRouter(tags=["terminal"])
security = HTTPBearer()

# Configure logging
logger = logging.getLogger(__name__)

# WebSocket connection manager for SSM sessions
class SSMConnectionManager:
	def __init__(self):
		self.active_sessions: Dict[str, Dict] = {}  # session_id -> session_info
		self.user_sessions: Dict[int, str] = {}     # user_id -> session_id

	async def create_ssm_session(self, websocket: WebSocket, pod_id: int, user_id: int, instance_id: str) -> str:
		"""Create a new SSM session for the user"""
		try:
			logger.info(f"Creating SSM session for user {user_id} on instance {instance_id}")
			
			# Initialize AWS SSM client
			ssm_client = boto3.client(
				'ssm',
				region_name=settings.AWS_REGION,
				aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
				aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
			)
			
			logger.info(f"SSM client initialized for region {settings.AWS_REGION}")
			
			# Check if SSM agent is ready on the instance
			logger.info(f"Checking SSM agent status for instance {instance_id}")
			if not await self._check_ssm_agent_ready(ssm_client, instance_id):
				logger.error(f"SSM agent not ready on instance {instance_id}")
				raise Exception("SSM agent not ready on instance")
			
			logger.info(f"SSM agent is ready on instance {instance_id}")
			
			# Create SSM session
			logger.info(f"Creating interactive SSM session for instance {instance_id}")
			response = ssm_client.start_session(
				Target=instance_id,
				DocumentName='AWS-StartInteractiveCommand',
				Parameters={
					'command': ['/bin/bash']
				}
			)
			
			session_id = response['SessionId']
			stream_url = response['StreamUrl']
			token_value = response['TokenValue']
			
			logger.info(f"SSM session created: {session_id}")
			logger.info(f"Stream URL: {stream_url}")
			
			# Store session information
			self.active_sessions[session_id] = {
				'websocket': websocket,
				'pod_id': pod_id,
				'user_id': user_id,
				'instance_id': instance_id,
				'stream_url': stream_url,
				'token_value': token_value,
				'created_at': datetime.now(),
				'ssm_client': ssm_client
			}
			
			# Map user to session
			self.user_sessions[user_id] = session_id
			
			logger.info(f"Created SSM session {session_id} for user {user_id} on pod {pod_id}")
			return session_id
			
		except Exception as e:
			logger.error(f"Failed to create SSM session: {e}")
			raise HTTPException(status_code=500, detail=f"Failed to create SSM session: {str(e)}")

	async def _check_ssm_agent_ready(self, ssm_client, instance_id: str) -> bool:
		"""Check if SSM agent is ready on the instance"""
		try:
			logger.info(f"Checking SSM agent status for instance {instance_id}")
			
			response = ssm_client.describe_instance_information(
				Filters=[
					{
						'Key': 'InstanceIds',
						'Values': [instance_id]
					}
				]
			)
			
			logger.info(f"SSM describe_instance_information response: {response}")
			
			if response['InstanceInformationList']:
				instance_info = response['InstanceInformationList'][0]
				ping_status = instance_info.get('PingStatus', '')
				platform_type = instance_info.get('PlatformType', '')
				last_ping = instance_info.get('LastPingDateTime', '')
				
				logger.info(f"Instance {instance_id}: PingStatus={ping_status}, PlatformType={platform_type}, LastPing={last_ping}")
				
				if ping_status == 'Online':
					logger.info(f"SSM agent is online for instance {instance_id}")
					return True
				else:
					logger.warning(f"SSM agent not online for instance {instance_id}: PingStatus={ping_status}")
					return False
			else:
				logger.warning(f"No instance information found for {instance_id}")
				return False
			
		except Exception as e:
			logger.error(f"Error checking SSM agent status for {instance_id}: {e}")
			return False

	def get_session(self, session_id: str) -> Optional[Dict]:
		"""Get session information by session ID"""
		return self.active_sessions.get(session_id)

	def get_user_session(self, user_id: int) -> Optional[str]:
		"""Get session ID for a user"""
		return self.user_sessions.get(user_id)

	async def close_session(self, session_id: str):
		"""Close an SSM session"""
		try:
			if session_id in self.active_sessions:
				session_info = self.active_sessions[session_id]
				
				# Cancel any running commands
				running_commands = session_info.get('running_commands', {})
				if running_commands:
					logger.info(f"Cancelling {len(running_commands)} running commands for session {session_id}")
					for command, command_id in running_commands.items():
						try:
							ssm_client = session_info['ssm_client']
							instance_id = session_info['instance_id']
							ssm_client.cancel_command(CommandId=command_id)
						except Exception as e:
							logger.warning(f"Failed to cancel command {command_id}: {e}")
				
				# Terminate SSM session
				ssm_client = session_info['ssm_client']
				try:
					ssm_client.terminate_session(SessionId=session_id)
				except Exception as e:
					logger.warning(f"terminate_session failed for {session_id}: {e}")
				
				# Remove from tracking
				user_id = session_info['user_id']
				if user_id in self.user_sessions:
					del self.user_sessions[user_id]
				
				del self.active_sessions[session_id]
				
				logger.info(f"Closed SSM session {session_id}")
				
		except Exception as e:
			logger.error(f"Error closing SSM session {session_id}: {e}")

	async def send_to_session(self, session_id: str, message: str):
		"""Send a message to a specific SSM session"""
		try:
			if session_id in self.active_sessions:
				session_info = self.active_sessions[session_id]
				websocket = session_info['websocket']
				
				# Send message to WebSocket client
				await websocket.send_text(json.dumps({
					"type": "output",
					"content": message
				}))
				
		except Exception as e:
			logger.error(f"Error sending to session {session_id}: {e}")

	async def store_command_history(self, session_id: str, command: str):
		"""Store command in session history"""
		try:
			if session_id in self.active_sessions:
				if 'command_history' not in self.active_sessions[session_id]:
					self.active_sessions[session_id]['command_history'] = []
				
				self.active_sessions[session_id]['command_history'].append({
					'command': command,
					'timestamp': datetime.now().isoformat()
				})
				
				# Keep only last 100 commands
				if len(self.active_sessions[session_id]['command_history']) > 100:
					self.active_sessions[session_id]['command_history'] = \
						self.active_sessions[session_id]['command_history'][-100:]
						
		except Exception as e:
			logger.error(f"Error storing command history: {e}")

	def get_command_history(self, session_id: str) -> list:
		"""Get command history for a session"""
		try:
			if session_id in self.active_sessions:
				return self.active_sessions[session_id].get('command_history', [])
			return []
		except Exception as e:
			logger.error(f"Error getting command history: {e}")
			return []

	def get_session_stats(self, session_id: str) -> dict:
		"""Get session statistics"""
		try:
			if session_id in self.active_sessions:
				session_info = self.active_sessions[session_id]
				command_history = session_info.get('command_history', [])
				running_commands = session_info.get('running_commands', {})
				
				return {
					'commands_executed': len(command_history),
					'running_commands': len(running_commands),
					'session_duration': (datetime.now() - session_info['created_at']).total_seconds(),
					'created_at': session_info['created_at'].isoformat()
				}
			return {}
		except Exception as e:
			logger.error(f"Error getting session stats: {e}")
			return {}

	async def reconnect_session(self, websocket: WebSocket, session_id: str) -> bool:
		"""Reconnect a WebSocket to an existing session"""
		try:
			if session_id in self.active_sessions:
				# Update the WebSocket reference
				self.active_sessions[session_id]['websocket'] = websocket
				logger.info(f"Reconnected WebSocket to session {session_id}")
				return True
			return False
		except Exception as e:
			logger.error(f"Error reconnecting session {session_id}: {e}")
			return False

	def is_session_active(self, session_id: str) -> bool:
		"""Check if a session is still active"""
		return session_id in self.active_sessions

# Global connection manager
manager = SSMConnectionManager()

@router.websocket("/v1/pods/{pod_id}/terminal/{instance_id}")
async def websocket_terminal(
	websocket: WebSocket, 
	pod_id: int, 
	instance_id: str,
	token: str = Query(None)
):
	"""WebSocket endpoint for SSM-based terminal access to EC2 instances"""
	
	if not token:
		# Refuse without trying to close twice
		try:
			await websocket.accept()
		except Exception:
			pass
		try:
			await websocket.close(code=4001, reason="Missing token")
		except Exception:
			pass
		return
	
	try:
		# Accept the WebSocket connection
		await websocket.accept()
		
		# TODO: Implement proper JWT validation here
		# For now, we'll use a simplified approach
		user_id = 1  # This should come from JWT token validation
		
		# Get pod details and validate access
		db = next(get_session())
		pod = db.get(Pod, pod_id)
		
		if not pod:
			await websocket.close(code=4004, reason="Pod not found")
			return
			
		if pod.user_id != user_id:
			await websocket.close(code=4003, reason="Access denied")
			return
			
		if pod.status != "running":
			await websocket.close(code=4005, reason="Pod not running")
			return
		
		if pod.instance_id != instance_id:
			await websocket.close(code=4006, reason="Instance ID mismatch")
			return
		
		# Check if user already has an active session
		existing_session_id = manager.get_user_session(user_id)
		if existing_session_id:
			# Check if the existing session is still valid
			if manager.is_session_active(existing_session_id):
				# Try to reconnect to existing session
				if await manager.reconnect_session(websocket, existing_session_id):
					session_id = existing_session_id
					logger.info(f"Reconnected to existing session {session_id}")
				else:
					# Reconnection failed, close existing session and create new one
					await manager.close_session(existing_session_id)
					try:
						session_id = await manager.create_ssm_session(websocket, pod_id, user_id, instance_id)
					except Exception as e:
						logger.error(f"Failed to create SSM session after reconnection failure: {e}")
						await websocket.close(code=4007, reason=f"Failed to create SSM session: {str(e)}")
						return
			else:
				# Session is no longer active, create new one
				try:
					session_id = await manager.create_ssm_session(websocket, pod_id, user_id, instance_id)
				except Exception as e:
					logger.error(f"Failed to create SSM session: {e}")
					await websocket.close(code=4007, reason=f"Failed to create SSM session: {str(e)}")
					return
		else:
			# Create new SSM session
			try:
				session_id = await manager.create_ssm_session(websocket, pod_id, user_id, instance_id)
			except Exception as e:
				logger.error(f"Failed to create SSM session: {e}")
				await websocket.close(code=4007, reason=f"Failed to create SSM session: {str(e)}")
				return
		
		# Send welcome message
		await websocket.send_text(json.dumps({
			"type": "system",
			"content": f"Connected to {pod.instance_type} instance via SSM"
		}))
		
		try:
			# Handle WebSocket messages (commands from user)
			while True:
				data = await websocket.receive_text()
				message = json.loads(data)
				
				if message["type"] == "command":
					command = message["content"]
					
					# Validate command
					if not command or not command.strip():
						await websocket.send_text(json.dumps({
							"type": "error",
							"content": "Empty command received"
						}))
						continue
					
					# Handle special commands
					if command.strip() == "history":
						# Show command history
						history = manager.get_command_history(session_id)
						if history:
							result = "Command history:\n"
							for i, hist_item in enumerate(history[-20:], 1):  # Show last 20 commands
								result += f"{i:3d}  {hist_item['timestamp']}  {hist_item['command']}\n"
						else:
							result = "No command history available.\n"
						
						await websocket.send_text(json.dumps({
							"type": "output",
							"content": result
						}))
						continue
					
					elif command.strip().startswith("cancel "):
						# Cancel a running command
						target_command = command[7:].strip()
						result = await cancel_running_command(session_id, target_command)
						await websocket.send_text(json.dumps({
							"type": "output",
							"content": result
						}))
						continue
					
					elif command.strip() == "echo":
						# Simple echo test
						result = await execute_ssm_command(session_id, 'echo "Hello from SSM!"')
						await websocket.send_text(json.dumps({
							"type": "output",
							"content": result
						}))
						continue
					
					elif command.strip() == "simple":
						# Simple command test using the same approach as the test command
						result = await execute_simple_command(session_id, 'echo "Simple test"')
						await websocket.send_text(json.dumps({
							"type": "output",
							"content": result
						}))
						continue
					
					elif command.strip() == "help":
						# Show help
						help_text = """Available commands:
- help: Show this help message
- history: Show command history
- cancel <command>: Cancel a running command
- test: Test SSM connectivity
- echo: Test basic command execution
- simple: Test simple command execution
- Any other command will be executed on the remote instance

Note: Commands are executed via AWS SSM and may take a moment to complete."""
						
						await websocket.send_text(json.dumps({
							"type": "output",
							"content": help_text
						}))
						continue
					
					elif command.strip() == "test":
						# Test SSM connectivity
						result = await test_ssm_connectivity(session_id)
						await websocket.send_text(json.dumps({
							"type": "output",
							"content": result
						}))
						continue
					
					# Store command in history
					await manager.store_command_history(session_id, command)
					
					# Execute command via SSM
					result = await execute_ssm_command(session_id, command)
					
					# Send result back to client
					await websocket.send_text(json.dumps({
						"type": "output",
						"content": result
					}))
				
				elif message["type"] == "ping":
					# Handle ping/pong for connection health
					await websocket.send_text(json.dumps({
						"type": "pong",
						"content": "pong"
					}))
				
				elif message["type"] == "resize":
					# Handle terminal resize (if needed)
					await websocket.send_text(json.dumps({
						"type": "system",
						"content": "Terminal resize not yet implemented"
					}))
				
				else:
					# Unknown message type
					await websocket.send_text(json.dumps({
						"type": "error",
						"content": f"Unknown message type: {message.get('type', 'undefined')}"
					}))
				
		except WebSocketDisconnect:
			logger.info(f"WebSocket disconnected for session {session_id}")
			try:
				await manager.close_session(session_id)
			except Exception as close_err:
				logger.warning(f"Error during close_session on disconnect: {close_err}")
			return
			
	except Exception as e:
		logger.error(f"Error in websocket_terminal: {e}")
		# Guard against double-close
		try:
			await websocket.close(code=4000, reason=f"Error: {str(e)}")
		except Exception:
			pass

async def execute_ssm_command(session_id: str, command: str) -> str:
	"""Execute a command via SSM session"""
	try:
		logger.info(f"Executing command: '{command}' for session {session_id}")
		
		session_info = manager.get_session(session_id)
		if not session_info:
			logger.error(f"Session {session_id} not found")
			return "Error: Session not found"
		
		instance_id = session_info['instance_id']
		ssm_client = session_info['ssm_client']
		
		logger.info(f"Using instance {instance_id} and SSM client {ssm_client}")
		
		# For now, let's use a simpler approach with send_command
		# but with better error handling and validation
		
		# First, check if the instance is ready for SSM commands
		try:
			logger.info(f"Checking instance status for {instance_id}")
			# Check instance information
			instance_info = ssm_client.describe_instance_information(
				Filters=[
					{
						'Key': 'InstanceIds',
						'Values': [instance_id]
					}
				]
			)
			
			logger.info(f"Instance info response: {instance_info}")
			
			if not instance_info['InstanceInformationList']:
				logger.error(f"Instance {instance_id} not found in SSM")
				return f"$ {command}\nError: Instance {instance_id} not found in SSM\n"
			
			instance_status = instance_info['InstanceInformationList'][0]
			logger.info(f"Instance status: {instance_status}")
			
			if instance_status.get('PingStatus') != 'Online':
				logger.error(f"SSM agent not online on instance {instance_id}")
				return f"$ {command}\nError: SSM agent not online on instance\n"
				
		except Exception as e:
			logger.error(f"Error checking instance status: {e}")
			return f"$ {command}\nError: Could not verify instance status: {str(e)}\n"
		
		# Try to send the command
		try:
			logger.info(f"Sending command '{command}' to instance {instance_id}")
			
			response = ssm_client.send_command(
				InstanceIds=[instance_id],
				DocumentName='AWS-RunShellScript',
				Parameters={
					'commands': [command],
					'executionTimeout': ['300']  # 5 minute timeout for now
				}
			)
			
			command_id = response['Command']['CommandId']
			logger.info(f"Successfully sent command {command_id} to instance {instance_id}")
			
		except Exception as e:
			logger.error(f"Error sending command with AWS-RunShellScript: {e}")
			
			# Try fallback method with different document
			try:
				logger.info(f"Trying fallback method with AWS-RunPowerShellScript")
				response = ssm_client.send_command(
					InstanceIds=[instance_id],
					DocumentName='AWS-RunPowerShellScript',
					Parameters={
						'commands': [f'bash -c "{command}"'],
						'executionTimeout': ['300']
					}
				)
				
				command_id = response['Command']['CommandId']
				logger.info(f"Sent command {command_id} using fallback method")
				
			except Exception as fallback_e:
				logger.error(f"Fallback method also failed: {fallback_e}")
				return f"$ {command}\nError sending command: {str(e)}\nFallback also failed: {str(fallback_e)}\n"
		
		# Wait for command to complete and get output
		max_wait = 10  # Reduced wait time for better UX
		wait_time = 0
		
		logger.info(f"Waiting for command {command_id} to complete (max wait: {max_wait}s)")
		
		while wait_time < max_wait:
			try:
				logger.info(f"Checking command {command_id} status (attempt {wait_time + 1})")
				
				output_response = ssm_client.get_command_invocation(
					CommandId=command_id,
					InstanceId=instance_id,
					PluginName='aws:runShellScript'
				)
				
				status = output_response['Status']
				logger.info(f"Command {command_id} status: {status}")
				
				if status in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
					# Command completed
					if status == 'Success':
						output = output_response.get('StandardOutputContent', '')
						error_output = output_response.get('StandardErrorContent', '')
						
						logger.info(f"Command {command_id} succeeded. Output: '{output}', Error: '{error_output}'")
						
						result = f"$ {command}\n"
						if output:
							result += output
						if error_output:
							result += f"\nError output:\n{error_output}"
						
						return result
					elif status == 'TimedOut':
						logger.warning(f"Command {command_id} timed out")
						return f"$ {command}\nCommand timed out after 5 minutes\n"
					elif status == 'Cancelled':
						logger.warning(f"Command {command_id} was cancelled")
						return f"$ {command}\nCommand was cancelled\n"
					else:
						logger.warning(f"Command {command_id} failed with status: {status}")
						return f"$ {command}\nCommand failed with status: {status}\n"
				
				# Wait before checking again
				await asyncio.sleep(1)  # Use asyncio.sleep instead of time.sleep
				wait_time += 1
				
			except Exception as e:
				logger.error(f"Error getting command output for {command_id}: {e}")
				if "InvocationDoesNotExist" in str(e):
					logger.error(f"Command {command_id} invocation does not exist - this suggests a command execution issue")
					return f"$ {command}\nError: Command execution failed - SSM agent may not have proper permissions\n"
				break
		
		# If we reach here, command is still running or failed
		logger.warning(f"Command {command_id} execution incomplete after {max_wait}s")
		return f"$ {command}\nCommand execution incomplete (waited {max_wait}s)\n"
		
	except Exception as e:
		logger.error(f"Error executing SSM command '{command}': {e}")
		return f"Error executing command: {str(e)}\n"

async def execute_simple_command(session_id: str, command: str) -> str:
	"""Execute a simple command using the same approach as the test command"""
	try:
		logger.info(f"Executing simple command: '{command}' for session {session_id}")
		
		session_info = manager.get_session(session_id)
		if not session_info:
			return "Error: Session not found"
		
		instance_id = session_info['instance_id']
		ssm_client = session_info['ssm_client']
		
		# Use the exact same approach as the working test command
		response = ssm_client.send_command(
			InstanceIds=[instance_id],
			DocumentName='AWS-RunShellScript',
			Parameters={
				'commands': [command],
				'executionTimeout': ['60']
			}
		)
		
		command_id = response['Command']['CommandId']
		logger.info(f"Simple command {command_id} sent successfully")
		
		# Wait for completion (same as test command)
		await asyncio.sleep(2)
		
		try:
			output_response = ssm_client.get_command_invocation(
				CommandId=command_id,
				InstanceId=instance_id,
				PluginName='aws:runShellScript'
			)
			
			status = output_response['Status']
			logger.info(f"Simple command {command_id} status: {status}")
			
			if status == 'Success':
				output = output_response.get('StandardOutputContent', '')
				result = f"$ {command}\n{output}"
				return result
			else:
				return f"$ {command}\nCommand failed with status: {status}\n"
				
		except Exception as e:
			logger.error(f"Error getting simple command output: {e}")
			return f"$ {command}\nError getting command output: {str(e)}\n"
			
	except Exception as e:
		logger.error(f"Error executing simple command: {e}")
		return f"Error executing simple command: {str(e)}\n"

async def test_ssm_connectivity(session_id: str) -> str:
	"""Test SSM connectivity and permissions"""
	try:
		session_info = manager.get_session(session_id)
		if not session_info:
			return "Error: Session not found"
		
		instance_id = session_info['instance_id']
		ssm_client = session_info['ssm_client']
		
		result = "=== SSM Connectivity Test ===\n"
		
		# Test 1: Check instance information
		try:
			instance_info = ssm_client.describe_instance_information(
				Filters=[
					{
						'Key': 'InstanceIds',
						'Values': [instance_id]
					}
				]
			)
			
			if instance_info['InstanceInformationList']:
				instance_status = instance_info['InstanceInformationList'][0]
				result += f"✓ Instance found: {instance_id}\n"
				result += f"  Ping Status: {instance_status.get('PingStatus', 'Unknown')}\n"
				result += f"  Platform Type: {instance_status.get('PlatformType', 'Unknown')}\n"
				result += f"  Last Ping: {instance_status.get('LastPingDateTime', 'Unknown')}\n"
			else:
				result += f"✗ Instance {instance_id} not found in SSM\n"
				return result
				
		except Exception as e:
			result += f"✗ Error checking instance info: {str(e)}\n"
			return result
		
		# Test 2: Try to send a simple command
		try:
			response = ssm_client.send_command(
				InstanceIds=[instance_id],
				DocumentName='AWS-RunShellScript',
				Parameters={
					'commands': ['echo "SSM test successful"'],
					'executionTimeout': ['60']
				}
			)
			
			command_id = response['Command']['CommandId']
			result += f"✓ Test command sent: {command_id}\n"
			
			# Wait for completion
			await asyncio.sleep(2)
			
			try:
				output_response = ssm_client.get_command_invocation(
					CommandId=command_id,
					InstanceId=instance_id,
					PluginName='aws:runShellScript'
				)
				
				status = output_response['Status']
				result += f"  Command Status: {status}\n"
				
				if status == 'Success':
					output = output_response.get('StandardOutputContent', '')
					result += f"  Output: {output.strip()}\n"
				else:
					result += f"  Error: {output_response.get('StandardErrorContent', 'No error details')}\n"
					
			except Exception as e:
				result += f"  ✗ Error getting command output: {str(e)}\n"
				
		except Exception as e:
			result += f"✗ Error sending test command: {str(e)}\n"
		
		result += "=== End Test ===\n"
		return result
		
	except Exception as e:
		logger.error(f"Error in SSM connectivity test: {e}")
		return f"Error running connectivity test: {str(e)}\n"

async def cancel_running_command(session_id: str, command: str) -> str:
	"""Cancel a running command via SSM session"""
	try:
		session_info = manager.get_session(session_id)
		if not session_info:
			return "Error: Session not found"
		
		instance_id = session_info['instance_id']
		ssm_client = session_info['ssm_client']
		
		# Get the command ID for the target command
		running_commands = session_info.get('running_commands', {})
		command_id = running_commands.get(command)
		
		if not command_id:
			return f"Error: Command '{command}' not found in running commands."
		
		# Send cancel command via SSM
		response = ssm_client.send_command(
			InstanceIds=[instance_id],
			DocumentName='AWS-RunShellScript',
			Parameters={
				'commands': ['pkill -f "aws ssm send-command --command-id ' + command_id + ' --instance-id ' + instance_id + ' --plugin-name aws:runShellScript"'],
				'executionTimeout': ['300'] # 5 minute timeout for cancellation
			}
		)
		
		cancel_command_id = response['Command']['CommandId']
		
		# Wait for cancellation to complete
		max_wait = 30 # Maximum wait time in seconds
		wait_time = 0
		
		while wait_time < max_wait:
			cancel_output_response = ssm_client.get_command_invocation(
				CommandId=cancel_command_id,
				InstanceId=instance_id,
				PluginName='aws:runShellScript'
			)
			
			status = cancel_output_response['Status']
			
			if status in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
				if status == 'Success':
					return f"Command '{command}' cancelled successfully."
				elif status == 'TimedOut':
					return f"Command '{command}' cancellation timed out after {max_wait}s."
				elif status == 'Cancelled':
					return f"Command '{command}' was already cancelled."
				else:
					return f"Command '{command}' cancellation failed with status: {status}."
			
			time.sleep(1)
			wait_time += 1
		
		return f"Command '{command}' cancellation is still pending (waited {max_wait}s)."
		
	except Exception as e:
		logger.error(f"Error cancelling SSM command: {e}")
		return f"Error cancelling command: {str(e)}\n"

@router.post("/v1/pods/{pod_id}/security-group/update")
async def update_security_group(
	pod_id: int,
	request: SecurityGroupUpdateRequest,
	db: Session = Depends(get_session),
	current_user = Depends(current_user)
):
	"""Update security group to allow SSM access (if needed)"""
	
	try:
		# Get pod details
		pod = db.get(Pod, pod_id)
		if not pod:
			raise HTTPException(status_code=404, detail="Pod not found")
		
		if not pod.instance_id:
			raise HTTPException(status_code=400, detail="Pod has no instance ID")
		
		# For SSM-based terminals, we typically don't need to modify security groups
		# SSM uses AWS internal networking and IAM roles for security
		
		return {
			"message": "Security group update not required for SSM-based terminals",
			"pod_id": pod_id,
			"instance_id": pod.instance_id
		}
		
	except Exception as e:
		logger.error(f"Error updating security group: {e}")
		raise HTTPException(status_code=500, detail=f"Failed to update security group: {str(e)}")

@router.get("/v1/pods/{pod_id}/terminal/status")
async def get_terminal_status(
	pod_id: int,
	db: Session = Depends(get_session),
	current_user = Depends(current_user)
):
	"""Get terminal connection status for a pod"""
	
	try:
		# Get pod details
		pod = db.get(Pod, pod_id)
		if not pod:
			raise HTTPException(status_code=404, detail="Pod not found")
		
		# Check if user has active session
		user_id = current_user.id
		session_id = manager.get_user_session(user_id)
		
		return {
			"pod_id": pod_id,
			"instance_id": pod.instance_id,
			"status": pod.status,
			"terminal_connected": session_id is not None,
			"session_id": session_id,
			"session_stats": manager.get_session_stats(session_id) if session_id else {}
		}
		
	except Exception as e:
		logger.error(f"Error getting terminal status: {e}")
		raise HTTPException(status_code=500, detail=f"Failed to get terminal status: {str(e)}")
