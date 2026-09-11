variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type for RF Suite compute (e.g. c6i.2xlarge, c5.2xlarge, t3.xlarge)"
  type        = string
  default     = "c6i.2xlarge"
}

variable "volume_size_gb" {
  description = "EBS GP3 root volume size in GB"
  type        = number
  default     = 60
}

variable "auto_stop_idle_minutes" {
  description = "Minutes of idle CPU before EC2 automatically stops to save costs"
  type        = number
  default     = 30
}
