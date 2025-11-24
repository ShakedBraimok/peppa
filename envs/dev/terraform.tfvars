# Terraform variables

environment = "dev"
project_name = "senora"
aws_region = "us-east-1"
actions_path = "../bot/src/slack_bot/actions"
compute_type = "BUILD_GENERAL1_SMALL"
build_image = "aws/codebuild/standard:7.0"
build_timeout = 15
privileged_mode = false
log_retention_days = 30
enable_log_encryption = true
enable_monitoring = true
build_failure_threshold = 1
alarm_actions = null
enable_action_permissions = false
action_permissions_policy = "{"
tags = null
