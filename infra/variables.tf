variable "environment" {
  description = "Environment name (e.g., dev, staging, prod, qa, etc.)"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "senora"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "actions_path" {
  description = "Path to actions directory"
  type        = string
  default     = "../bot/src/slack_bot/actions"
}

# CodeBuild Configuration
variable "compute_type" {
  description = "CodeBuild compute type"
  type        = string
  default     = "BUILD_GENERAL1_SMALL"
}

variable "build_image" {
  description = "CodeBuild Docker image"
  type        = string
  default     = "aws/codebuild/standard:7.0"
}

variable "build_timeout" {
  description = "Build timeout in minutes"
  type        = number
  default     = 15
}

variable "privileged_mode" {
  description = "Enable privileged mode for Docker builds"
  type        = bool
  default     = false
}

# Logging
variable "log_retention_days" {
  description = "CloudWatch Logs retention period (days)"
  type        = number
  default     = 30
}

variable "enable_log_encryption" {
  description = "Enable KMS encryption for logs"
  type        = bool
  default     = true
}

# Monitoring
variable "enable_monitoring" {
  description = "Enable CloudWatch alarms"
  type        = bool
  default     = true
}

variable "build_failure_threshold" {
  description = "Threshold for build failure alarms"
  type        = number
  default     = 1
}

variable "alarm_actions" {
  description = "SNS topic ARNs for alarm notifications"
  type        = list(string)
  default     = []
}

# IAM Permissions
variable "enable_action_permissions" {
  description = "Enable additional IAM permissions for actions"
  type        = bool
  default     = false
}

variable "action_permissions_policy" {
  description = "Additional IAM policy for action permissions"
  type        = string
  default     = "{}"
}

# Tags
variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}
