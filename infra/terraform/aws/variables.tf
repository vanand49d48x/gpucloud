variable "base_ami_id" {
  description = "Base AMI ID for GPU instances"
  type        = string
  default     = ""
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
