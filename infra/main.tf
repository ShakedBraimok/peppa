terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Backend configuration provided via backend config file
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project_name
      ManagedBy   = "Terraform"
    }
  }
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Discover action directories
  action_directories = fileset("${var.actions_path}", "*")

  common_tags = {
    Environment = var.environment
    Project     = var.project_name
    Terraform   = "true"
  }
}

# Data source to get notifier function name from SAM stack
data "aws_cloudformation_export" "notifier_function_name" {
  name = "${var.project_name}-${var.environment}-notifier-name"
}

# IAM Role for CodeBuild
resource "aws_iam_role" "codebuild_role" {
  name = "${local.name_prefix}-codebuild-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "codebuild.amazonaws.com"
      }
    }]
  })

  tags = local.common_tags
}

# IAM Policy for CodeBuild
resource "aws_iam_role_policy" "codebuild_policy" {
  name = "${local.name_prefix}-codebuild-policy"
  role = aws_iam_role.codebuild_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/codebuild/${local.name_prefix}-*"
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${var.project_name}-${var.environment}-notifier"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "SlackBot"
          }
        }
      }
    ]
  })
}

# Additional policy for action-specific permissions
resource "aws_iam_role_policy" "action_permissions" {
  count = var.enable_action_permissions ? 1 : 0

  name = "${local.name_prefix}-action-permissions"
  role = aws_iam_role.codebuild_role.id

  policy = var.action_permissions_policy
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# CodeBuild projects for each action
resource "aws_codebuild_project" "action" {
  for_each = local.action_directories

  name          = "${local.name_prefix}-${each.key}"
  description   = "CodeBuild project for ${each.key} action"
  build_timeout = var.build_timeout
  service_role  = aws_iam_role.codebuild_role.arn

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = var.compute_type
    image                       = var.build_image
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = var.privileged_mode

    environment_variable {
      name  = "ENVIRONMENT"
      value = var.environment
    }

    environment_variable {
      name  = "ACTION_NAME"
      value = each.key
    }

    environment_variable {
      name  = "NOTIFIER_FUNCTION_NAME"
      value = data.aws_cloudformation_export.notifier_function_name.value
    }

    environment_variable {
      name  = "AWS_ACCOUNT_ID"
      value = data.aws_caller_identity.current.account_id
    }
  }

  logs_config {
    cloudwatch_logs {
      group_name  = "/aws/codebuild/${local.name_prefix}-${each.key}"
      status      = "ENABLED"
      stream_name = "build-log"
    }
  }

  source {
    type      = "NO_SOURCE"
    buildspec = file("${var.actions_path}/${each.key}/buildspec.yaml")
  }

  tags = merge(
    local.common_tags,
    {
      Action = each.key
    }
  )
}

# CloudWatch Log Groups for CodeBuild
resource "aws_cloudwatch_log_group" "codebuild_logs" {
  for_each = local.action_directories

  name              = "/aws/codebuild/${local.name_prefix}-${each.key}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.enable_log_encryption ? aws_kms_key.logs[0].arn : null

  tags = merge(
    local.common_tags,
    {
      Action = each.key
    }
  )
}

# KMS Key for log encryption
resource "aws_kms_key" "logs" {
  count = var.enable_log_encryption ? 1 : 0

  description             = "KMS key for CodeBuild logs encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-logs-key"
    }
  )
}

resource "aws_kms_alias" "logs" {
  count = var.enable_log_encryption ? 1 : 0

  name          = "alias/${local.name_prefix}-logs"
  target_key_id = aws_kms_key.logs[0].key_id
}

# CloudWatch Alarms for build failures
resource "aws_cloudwatch_metric_alarm" "build_failures" {
  for_each = var.enable_monitoring ? local.action_directories : []

  alarm_name          = "${local.name_prefix}-${each.key}-build-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FailedBuilds"
  namespace           = "AWS/CodeBuild"
  period              = 300
  statistic           = "Sum"
  threshold           = var.build_failure_threshold
  alarm_description   = "CodeBuild failures for ${each.key} action"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ProjectName = aws_codebuild_project.action[each.key].name
  }

  alarm_actions = var.alarm_actions

  tags = local.common_tags
}
