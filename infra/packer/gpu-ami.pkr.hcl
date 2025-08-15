packer {
  required_plugins {
    amazon-ami-management = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/amazon-ami-management"
    }
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "base_ami_id" {
  description = "Base AMI ID"
  type        = string
}

variable "instance_type" {
  description = "Instance type for building"
  type        = string
  default     = "t3.medium"
}

source "amazon-ami-management" "gpu_base" {
  region = var.aws_region
  source_ami = var.base_ami_id
  instance_type = var.instance_type
  
  ami_name        = "gpucloud-base-{{timestamp}}"
  ami_description = "GPUCloud Base AMI with CUDA and Docker"
  
  tags = {
    Name    = "gpucloud-base"
    Project = "gpucloud-mvp"
  }
}

build {
  sources = ["source.amazon-ami-management.gpu_base"]
  
  provisioner "shell" {
    inline = [
      "sudo yum update -y",
      "sudo yum install -y docker",
      "sudo systemctl start docker",
      "sudo systemctl enable docker",
      "sudo usermod -a -G docker ec2-user"
    ]
  }
}
