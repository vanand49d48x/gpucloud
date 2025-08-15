terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID"
  type        = string
}

variable "security_group_id" {
  description = "Security Group ID"
  type        = string
}

variable "instance_profile" {
  description = "IAM Instance Profile"
  type        = string
}

variable "ssh_key_name" {
  description = "SSH Key Pair Name"
  type        = string
}

# GPU Instance
resource "aws_instance" "gpu_instance" {
  ami                    = var.base_ami_id
  instance_type          = "g4dn.xlarge"  # NVIDIA T4 GPU
  key_name              = var.ssh_key_name
  vpc_security_group_ids = [var.security_group_id]
  subnet_id              = var.subnet_id
  iam_instance_profile   = var.instance_profile

  tags = {
    Name = "gpucloud-instance"
    Project = "gpucloud-mvp"
  }
}

output "instance_id" {
  value = aws_instance.gpu_instance.id
}

output "public_ip" {
  value = aws_instance.gpu_instance.public_ip
}
