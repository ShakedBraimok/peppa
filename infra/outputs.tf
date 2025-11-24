output "codebuild_projects" {
  description = "Map of action names to CodeBuild project names"
  value = {
    for action, project in aws_codebuild_project.action : action => project.name
  }
}

output "codebuild_role_arn" {
  description = "CodeBuild IAM role ARN"
  value       = aws_iam_role.codebuild_role.arn
}

output "log_groups" {
  description = "Map of action names to CloudWatch log groups"
  value = {
    for action, log_group in aws_cloudwatch_log_group.codebuild_logs : action => log_group.name
  }
}

output "discovered_actions" {
  description = "List of discovered action directories"
  value       = sort(keys(local.action_directories))
}

output "kms_key_id" {
  description = "KMS key ID for log encryption"
  value       = var.enable_log_encryption ? aws_kms_key.logs[0].id : null
}

output "deployment_summary" {
  description = "Deployment summary"
  value = {
    environment      = var.environment
    project_name     = var.project_name
    region           = var.aws_region
    actions_count    = length(local.action_directories)
    actions          = sort(keys(local.action_directories))
    log_encryption   = var.enable_log_encryption
    monitoring       = var.enable_monitoring
  }
}
