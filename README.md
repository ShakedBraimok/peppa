# peppa

Build a Slack self-service bot in minutes. This template gives you a plug-and-play Slack bot with modals, actions, async CodeBuild tasks, and smart notifications - fully wired with Terraform + SAM and ready for production.

# Quick Start Guide

Deploy a custom Slack bot with plugin architecture powered by AWS Lambda and CodeBuild - run DevOps tasks directly from Slack. This guide walks through Slack app creation, AWS deployment, and adding custom actions.

## Prerequisites Checklist

Before you start, ensure you have:

- [ ] AWS CLI installed and configured (`aws --version`)
- [ ] AWS SAM CLI installed (`sam --version`)
- [ ] Terraform >= 1.0 installed (`terraform version`)
- [ ] Python 3.11+ installed (`python3 --version`)
- [ ] AWS credentials configured (`aws sts get-caller-identity`)
- [ ] Slack workspace admin access (to create apps)
- [ ] Appropriate AWS permissions (Lambda, CodeBuild, API Gateway, Secrets Manager, IAM)

## Architecture Overview

This Slack bot system consists of:

1. **Slack Bot Lambda:**
   - Handles slash commands and interactions
   - Dynamic menu generation from available actions
   - Triggers CodeBuild jobs

2. **Notifier Lambda:**
   - Sends job completion notifications to Slack
   - Reports success/failure with build logs

3. **CodeBuild Projects:**
   - One project per action
   - Executes commands defined in buildspec.yaml
   - Isolated execution environments

4. **Plugin Architecture:**
   - Each action = 2 files (modal.json + buildspec.yaml)
   - Auto-discovered and added to bot menu
   - Easy to extend with new capabilities

## Step 1: Create Slack App

### Create Slack App

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. App Name: `DevOps Bot` (or your choice)
4. Select your workspace → Click **"Create App"**

### Configure Bot Token Scopes

1. Navigate to **"OAuth & Permissions"**
2. Scroll to **"Scopes"** → **"Bot Token Scopes"**
3. Add these scopes:
   - `chat:write` - Send messages
   - `commands` - Handle slash commands
   - `users:read` - Get user info
   - `channels:read` - List channels

### Create Slash Command (Temporary URL)

1. Navigate to **"Slash Commands"**
2. Click **"Create New Command"**
3. Configure:
   - **Command:** `/devops` (or your choice)
   - **Request URL:** `https://example.com` (temporary, we'll update after deployment)
   - **Short Description:** `DevOps automation commands`
   - **Usage Hint:** `[action]`
4. Click **"Save"**

### Enable Interactivity (Temporary URL)

1. Navigate to **"Interactivity & Shortcuts"**
2. Toggle **"Interactivity"** to **On**
3. **Request URL:** `https://example.com` (temporary, we'll update after deployment)
4. Click **"Save Changes"**

### Install App to Workspace

1. Navigate to **"Install App"**
2. Click **"Install to Workspace"**
3. Review permissions → Click **"Allow"**
4. **Copy Bot User OAuth Token** (starts with `xoxb-`)
   - Example: `REDACTED_TOKEN`
5. **Save this token** - you'll need it soon!

### Get Signing Secret

1. Navigate to **"Basic Information"**
2. Scroll to **"App Credentials"**
3. **Copy Signing Secret**
4. **Save this secret** - you'll need it soon!

## Step 2: Deploy Bot Lambda

```bash
# Deploy SAM application
make deploy-bot ENV=dev

# This will:
# - Package Lambda functions
# - Upload to S3
# - Deploy CloudFormation stack
# - Create API Gateway
# - Output API endpoint URL
```

**Save the API Gateway URL from outputs:**
```
Outputs:
SlackBotApiUrl = https://xxxxx.execute-api.us-east-1.amazonaws.com/Prod/slack/events
```

## Step 3: Update Slack App URLs

Now that you have the API Gateway URL, update Slack:

1. **Update Slash Command:**
   - Go to Slack app → **"Slash Commands"**
   - Edit `/devops` command
   - **Request URL:** `https://xxxxx.execute-api.us-east-1.amazonaws.com/Prod/slack/events`
   - **Save**

2. **Update Interactivity:**
   - Go to **"Interactivity & Shortcuts"**
   - **Request URL:** `https://xxxxx.execute-api.us-east-1.amazonaws.com/Prod/slack/events`
   - **Save Changes**

## Step 4: Configure Slack Credentials

Store your Slack tokens in AWS Secrets Manager:

```bash
# Set your tokens as environment variables
export SLACK_BOT_TOKEN="xoxb-your-token-here"
export SLACK_SIGNING_SECRET="your-signing-secret-here"

# Store in Secrets Manager
aws secretsmanager create-secret \
  --name /senora/dev/slack-secret-token \
  --description "Slack bot credentials" \
  --secret-string "{\"slack_bot_token\":\"$SLACK_BOT_TOKEN\",\"slack_signing_secret\":\"$SLACK_SIGNING_SECRET\"}" \
  --region us-east-1

# Verify
aws secretsmanager get-secret-value \
  --secret-id /senora/dev/slack-secret-token \
  --region us-east-1
```

**Alternative: Using AWS Console**
1. Go to AWS Secrets Manager
2. Create new secret → **"Other type of secret"**
3. Key/value pairs:
   - `slack_bot_token`: `xoxb-...`
   - `slack_signing_secret`: `...`
4. Secret name: `/senora/dev/slack-secret-token`

## Step 5: Test Bot in Slack

```bash
# In Slack, type:
/devops

# You should see a modal with the example action!
```

**If it works, you'll see:**
- A modal dialog with "Example Action"
- Input field for "Environment"
- Submit button

**If it doesn't work:**
```bash
# Check Lambda logs
make logs-bot ENV=dev

# Common issues:
# - Request URL mismatch (verify URLs in Slack app settings)
# - Secrets not found (verify secret name and region)
# - API Gateway errors (check API Gateway logs)
```

## Step 6: Deploy CodeBuild Runners

```bash
# Configure environment
cd envs/dev
# Edit terraform.tfvars if needed (optional for now)

# Deploy CodeBuild infrastructure
make deploy-runners ENV=dev

# This creates:
# - CodeBuild project for "example" action
# - IAM roles for CodeBuild
# - CloudWatch log groups
# - SNS topics for notifications
```

## Step 7: Test End-to-End

```bash
# In Slack, type:
/devops

# 1. Select "Example Action"
# 2. Choose environment: "dev"
# 3. Click Submit

# You should immediately see: "Job started! Build ID: xxx"
# After 30-60 seconds: "Job completed successfully!"
```

**Check build logs:**
```bash
make logs-notifier ENV=dev

# Or view in AWS Console:
# CodeBuild → Build projects → example-dev → Build history
```

## Step 8: Add Your Own Actions

The bot uses a plugin architecture - each action is just 2 files!

### Create New Action

```bash
# Use the built-in helper
make add-action NAME=deploy-api ENV=dev

# This creates:
# REDACTED_TOKEN
#   ├── modal.json
#   └── buildspec.yaml
```

### Customize Modal UI

Edit `REDACTED_TOKEN.json`:

```json
{
  "type": "modal",
  "callback_id": "deploy-api",
  "title": {"type": "plain_text", "text": "Deploy API"},
  "submit": {"type": "plain_text", "text": "Deploy"},
  "blocks": [
    {
      "type": "input",
      "block_id": "environment",
      "label": {"type": "plain_text", "text": "Environment"},
      "element": {
        "type": "static_select",
        "action_id": "environment_select",
        "placeholder": {"type": "plain_text", "text": "Select environment"},
        "options": [
          {"text": {"type": "plain_text", "text": "Dev"}, "value": "dev"},
          {"text": {"type": "plain_text", "text": "Staging"}, "value": "staging"},
          {"text": {"type": "plain_text", "text": "Production"}, "value": "prod"}
        ]
      }
    },
    {
      "type": "input",
      "block_id": "version",
      "label": {"type": "plain_text", "text": "Version"},
      "element": {
        "type": "plain_text_input",
        "action_id": "version_input",
        "placeholder": {"type": "plain_text", "text": "e.g., v1.2.3"}
      }
    }
  ]
}
```

### Customize Build Commands

Edit `REDACTED_TOKEN.yaml`:

```yaml
version: 0.2

phases:
  install:
    commands:
      - echo "Installing dependencies..."
      - pip install awscli boto3

  pre_build:
    commands:
      - echo "Pre-deployment checks..."
      - aws sts get-caller-identity

  build:
    commands:
      - echo "Deploying API to $ENVIRONMENT"
      - echo "Version: $VERSION"

      # Your deployment commands here:
      - cd api
      - make deploy ENV=$ENVIRONMENT VERSION=$VERSION

      # Or use AWS CLI:
      # - aws lambda update-function-code --function-name my-api-$ENVIRONMENT --zip-file fileb://api.zip

      # Or Terraform:
      # - terraform init
      # - terraform apply -var="version=$VERSION" -auto-approve

  post_build:
    commands:
      - echo "Deployment completed!"
      - echo "API URL: $(terraform output -raw api_url)"

artifacts:
  files:
    - '**/*'
```

### Deploy New Action

```bash
# Redeploy bot to recognize new action
make deploy-bot ENV=dev

# Deploy CodeBuild project for new action
make deploy-runners ENV=dev

# Test in Slack
/devops
# You should now see "Deploy API" in the menu!
```

## Common Action Examples

### 1. Terraform Apply

**modal.json:**
```json
{
  "callback_id": "terraform-apply",
  "title": {"type": "plain_text", "text": "Terraform Apply"},
  "blocks": [
    {
      "type": "input",
      "block_id": "environment",
      "label": {"type": "plain_text", "text": "Environment"},
      "element": {
        "type": "static_select",
        "action_id": "env_select",
        "options": [
          {"text": {"type": "plain_text", "text": "Dev"}, "value": "dev"},
          {"text": {"type": "plain_text", "text": "Prod"}, "value": "prod"}
        ]
      }
    }
  ]
}
```

**buildspec.yaml:**
```yaml
version: 0.2
phases:
  build:
    commands:
      - cd terraform
      - terraform init
      - terraform apply -var-file=envs/$ENVIRONMENT.tfvars -auto-approve
```

### 2. Database Migration

**buildspec.yaml:**
```yaml
version: 0.2
phases:
  build:
    commands:
      - echo "Running migrations on $ENVIRONMENT"
      - npm install
      - npm run migrate:$ENVIRONMENT
```

### 3. Restart ECS Service

**buildspec.yaml:**
```yaml
version: 0.2
phases:
  build:
    commands:
      - |
        aws ecs update-service \
          --cluster my-cluster-$ENVIRONMENT \
          --service my-service \
          --force-new-deployment
      - echo "Service restarted successfully"
```

## Advanced Configuration

### Add IAM Permissions for Actions

Edit `envs/dev/terraform.tfvars`:

```hcl
# Additional IAM policies for CodeBuild
codebuild_additional_policies = [
  "arn:aws:iam::aws:policy/AmazonECS_FullAccess",
  "arn:aws:iam::aws:policy/AmazonRDSFullAccess"
]

# Or create custom policy:
codebuild_custom_policy = jsonencode({
  Version = "2012-10-17"
  Statement = [
    {
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject"
      ]
      Resource = "arn:aws:s3:::my-bucket/*"
    }
  ]
})
```

### Restrict to Specific Users/Channels

Edit `bot/src/slack_bot/main.py`:

```python
ALLOWED_USERS = ["U12345678", "U87654321"]  # Slack user IDs
ALLOWED_CHANNELS = ["C12345678"]  # Slack channel IDs

@app.command("/devops")
def handle_command(ack, command):
    if command["user_id"] not in ALLOWED_USERS:
        ack("Sorry, you don't have permission to use this bot.")
        return
    # ... rest of handler
```

### Add Approval Workflow

For production actions, add approval step:

```python
# In modal.json, add a confirmation checkbox
{
  "type": "input",
  "block_id": "confirmation",
  "label": {"type": "plain_text", "text": "Confirmation"},
  "element": {
    "type": "checkboxes",
    "action_id": "confirm",
    "options": [
      {
        "text": {"type": "plain_text", "text": "I understand this will affect production"},
        "value": "confirmed"
      }
    ]
  }
}
```

## Monitoring and Debugging

```bash
# View bot logs
make logs-bot ENV=dev

# View notifier logs
make logs-notifier ENV=dev

# List all actions
make list-actions

# Check CodeBuild project status
aws codebuild batch-get-projects --names example-dev

# View recent builds
aws codebuild list-builds-for-project --project-name example-dev

# Get build details
aws codebuild batch-get-builds --ids <BUILD_ID>
```

## Troubleshooting

### Bot Not Responding in Slack?

1. **Check API Gateway URL matches Slack settings**
2. **Verify secrets in Secrets Manager:**
   ```bash
   aws secretsmanager get-secret-value --secret-id /senora/dev/slack-secret-token
   ```
3. **Check Lambda logs:**
   ```bash
   make logs-bot ENV=dev
   ```

### Action Not Appearing in Menu?

1. **Verify action directory exists:**
   ```bash
   ls -la bot/src/slack_bot/actions/
   ```
2. **Redeploy bot:**
   ```bash
   make deploy-bot ENV=dev
   ```

### Build Fails Immediately?

1. **Check IAM permissions for CodeBuild**
2. **Verify buildspec.yaml syntax:**
   ```bash
   # Install yamllint
   pip install yamllint
   yamllint bot/src/slack_bot/actions/*/buildspec.yaml
   ```
3. **Check build logs:**
   ```bash
   aws logs tail /aws/codebuild/example-dev --follow
   ```

## Clean Up

```bash
# Destroy all resources
make destroy ENV=dev

# Delete Slack app
# Go to https://api.slack.com/apps
# Select your app → Settings → Delete App
```

## Cost Estimates

**Light usage (few commands per day):**
- Lambda: $0-5/month
- CodeBuild: $0-10/month (first 100 build minutes free)
- API Gateway: $0-5/month
- Secrets Manager: $0.40/month per secret
- **Total: ~$1-20/month**

**Moderate usage (50+ commands per day):**
- Lambda: $5-10/month
- CodeBuild: $20-50/month
- API Gateway: $5-10/month
- Other services: $2-5/month
- **Total: ~$32-75/month**

## Security Best Practices

1. **Limit bot to specific channels:**
   ```python
   ALLOWED_CHANNELS = ["C12345678"]
   ```

2. **Require approval for production actions:**
   - Add confirmation checkboxes
   - Implement two-person rule

3. **Use IAM least privilege:**
   - Grant only necessary permissions per action
   - Use separate roles for different actions

4. **Audit logging:**
   - CloudWatch Logs capture all commands
   - Enable CloudTrail for API calls

5. **Rotate secrets regularly:**
   - Slack tokens
   - AWS access keys

## Support

- Run `make help` to see all available commands and get help with common tasks
- Open a support ticket at [https://senora.dev/NewTicket](https://senora.dev/NewTicket)


## Environment Variables

This project uses environment-specific variable files in the `envs/` directory.

### dev
Variables are stored in `envs/dev/terraform.tfvars`



## GitHub Actions CI/CD

This project includes automated Terraform validation via GitHub Actions.

### Required GitHub Secrets

Configure these in Settings > Secrets > Actions:

- `AWS_ACCESS_KEY_ID`: Your AWS Access Key ID
- `AWS_SECRET_ACCESS_KEY`: Your AWS Secret Access Key
- `TF_STATE_BUCKET`: S3 bucket name for Terraform state
- `TF_STATE_KEY`: Path to state file in S3 bucket

💡 **Tip**: Check your `backend.tf` file for the bucket and key values.


---
*Generated by [Senora](https://senora.dev)*
