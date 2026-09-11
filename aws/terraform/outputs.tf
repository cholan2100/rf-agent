output "instance_id" {
  description = "EC2 Instance ID of RF Suite Host"
  value       = aws_instance.rf_suite_host.id
}

output "workspace_bucket" {
  description = "S3 Bucket for Workspace Artifacts Synchronization"
  value       = aws_s3_bucket.rf_workspace_bucket.id
}

output "aws_region" {
  description = "AWS Region"
  value       = var.aws_region
}

output "ssm_connect_command" {
  description = "SSM Connect Command"
  value       = "aws ssm start-session --target ${aws_instance.rf_suite_host.id} --region ${var.aws_region}"
}

output "ssm_gui_tunnel_command" {
  description = "SSM noVNC Port Forwarding Tunnel Command"
  value       = "aws ssm start-session --target ${aws_instance.rf_suite_host.id} --region ${var.aws_region} --document-name AWS-StartPortForwardingSession --parameters '{\"portNumber\":[\"6080\"],\"localPortNumber\":[\"6080\"]}'"
}

output "env_config" {
  description = "Copy this to your .env file"
  value       = <<-EOT
    RF_BACKEND=aws
    AWS_REGION=${var.aws_region}
    AWS_INSTANCE_ID=${aws_instance.rf_suite_host.id}
    AWS_S3_BUCKET=${aws_s3_bucket.rf_workspace_bucket.id}
    RF_REMOTE_METHOD=ssm
  EOT
}
