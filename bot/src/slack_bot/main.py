"""
Slack Bot Lambda Handler

Production-ready Slack bot using Slack Bolt framework with comprehensive
error handling, monitoring, and security features.
"""
import json
import os
from typing import Dict, Any, Optional
import boto3
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

from blocks import action_data

# Initialize AWS Lambda Powertools
logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "slack-bot"))
tracer = Tracer(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "slack-bot"))
metrics = Metrics(namespace="SlackBot", service="slack-bot")

# Initialize AWS clients
secrets_client = boto3.client("secretsmanager")
codebuild_client = boto3.client("codebuild")

# Global variable for Slack app (initialized in get_slack_app)
_slack_app: Optional[App] = None


@tracer.capture_method
def get_slack_credentials() -> Dict[str, str]:
    """
    Retrieve Slack credentials from AWS Secrets Manager.

    Returns:
        Dict containing slack_signing_secret and slack_bot_token

    Raises:
        ClientError: If secret cannot be retrieved
    """
    secret_name = os.environ.get("SLACK_SECRET_TOKEN")

    if not secret_name:
        logger.error("SLACK_SECRET_TOKEN environment variable not set")
        raise ValueError("SLACK_SECRET_TOKEN environment variable is required")

    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_data = json.loads(response["SecretString"])

        required_keys = ["slack_signing_secret", "slack_bot_token"]
        missing_keys = [key for key in required_keys if key not in secret_data]

        if missing_keys:
            logger.error(f"Missing required keys in secret: {missing_keys}")
            raise ValueError(f"Secret missing keys: {missing_keys}")

        logger.info("Successfully retrieved Slack credentials")
        return secret_data

    except ClientError as e:
        logger.error(f"Failed to retrieve secret: {e}")
        metrics.add_metric(name="SecretRetrievalError", unit=MetricUnit.Count, value=1)
        raise


def get_slack_app() -> App:
    """
    Get or initialize the Slack Bolt app.

    Returns:
        Configured Slack App instance
    """
    global _slack_app

    if _slack_app is None:
        logger.info("Initializing Slack app")
        credentials = get_slack_credentials()

        _slack_app = App(
            token=credentials["slack_bot_token"],
            signing_secret=credentials["slack_signing_secret"],
            process_before_response=True,
        )

        # Register event handlers
        register_handlers(_slack_app)

    return _slack_app


def register_handlers(app: App) -> None:
    """Register all Slack event handlers."""

    @app.command("/senora")
    @tracer.capture_method
    def handle_slash_command(ack, body, client):
        """Handle /senora slash command."""
        ack()
        metrics.add_metric(name="SlashCommandReceived", unit=MetricUnit.Count, value=1)

        try:
            open_modal(client, body["trigger_id"])
            metrics.add_metric(name="ModalOpened", unit=MetricUnit.Count, value=1)
        except Exception as e:
            logger.error(f"Error opening modal: {e}", exc_info=True)
            metrics.add_metric(name="ModalOpenError", unit=MetricUnit.Count, value=1)
            # Send error message to user
            try:
                client.chat_postMessage(
                    channel=body["user_id"],
                    text="❌ Sorry, I encountered an error. Please try again later."
                )
            except Exception:
                pass  # Best effort

    @app.view("initial_modal")
    @tracer.capture_method
    def handle_initial_modal_submission(ack, body, client, view):
        """Handle initial modal submission (action selection)."""
        metrics.add_metric(name="InitialModalSubmitted", unit=MetricUnit.Count, value=1)

        try:
            selected_action = view["state"]["values"]["action_select_block"]["action_select"][
                "selected_option"
            ]["value"]

            logger.info(f"Action selected: {selected_action}")

            if selected_action not in action_data:
                logger.error(f"Invalid action selected: {selected_action}")
                ack(
                    response_action="errors",
                    errors={"action_select_block": "Invalid action selected"}
                )
                return

            # Acknowledge and update modal with action-specific form
            ack(
                response_action="update",
                view=create_action_modal(selected_action)
            )

            metrics.add_metric(name="ActionFormDisplayed", unit=MetricUnit.Count, value=1)

        except Exception as e:
            logger.error(f"Error handling initial modal: {e}", exc_info=True)
            metrics.add_metric(name="InitialModalError", unit=MetricUnit.Count, value=1)
            ack(
                response_action="errors",
                errors={"action_select_block": "An error occurred. Please try again."}
            )

    @app.view("updated_modal")
    @tracer.capture_method
    def handle_updated_modal_submission(ack, body, client, view):
        """Handle final modal submission and trigger CodeBuild."""
        ack()
        metrics.add_metric(name="FinalModalSubmitted", unit=MetricUnit.Count, value=1)

        try:
            # Extract action name and user inputs
            action_name = view["private_metadata"]
            user_id = body["user"]["id"]

            logger.info(f"Executing action: {action_name} for user: {user_id}")

            # Send immediate acknowledgment
            client.chat_postMessage(
                channel=user_id,
                text=f"✅ Your request for *{action_name}* has been received and is being processed..."
            )

            # Execute the action
            build_info = execute_action(action_name, body)

            # Send confirmation with build details
            client.chat_postMessage(
                channel=user_id,
                text=f"🚀 *{action_name}* is now running!\n"
                     f"Build ID: `{build_info['id']}`\n"
                     f"You'll be notified when it completes."
            )

            metrics.add_metric(name="ActionExecuted", unit=MetricUnit.Count, value=1)
            metrics.add_metadata(key="action_name", value=action_name)

        except Exception as e:
            logger.error(f"Error executing action: {e}", exc_info=True)
            metrics.add_metric(name="ActionExecutionError", unit=MetricUnit.Count, value=1)

            try:
                client.chat_postMessage(
                    channel=body["user"]["id"],
                    text=f"❌ Failed to execute action: {str(e)}\nPlease contact support if this continues."
                )
            except Exception:
                pass  # Best effort

    @app.event("app_mention")
    @tracer.capture_method
    def handle_app_mention(event, say):
        """Handle @bot mentions."""
        metrics.add_metric(name="AppMentioned", unit=MetricUnit.Count, value=1)
        say(
            text=f"Hi <@{event['user']}>! Use `/senora` to see available actions.",
            thread_ts=event.get("thread_ts", event["ts"])
        )

    @app.event("message")
    @tracer.capture_method
    def handle_direct_message(event, say):
        """Handle direct messages to the bot."""
        # Only respond to DMs (not channel messages)
        if event.get("channel_type") == "im":
            metrics.add_metric(name="DirectMessageReceived", unit=MetricUnit.Count, value=1)
            say("Hello! Use `/senora` to access self-service automation.")

    @app.event("app_home_opened")
    @tracer.capture_method
    def handle_app_home_opened(client, event):
        """Display custom home tab."""
        metrics.add_metric(name="HomeTabOpened", unit=MetricUnit.Count, value=1)

        try:
            client.views_publish(
                user_id=event["user"],
                view=create_home_view()
            )
        except Exception as e:
            logger.error(f"Error publishing home view: {e}", exc_info=True)


def open_modal(client, trigger_id: str) -> None:
    """
    Open the initial action selection modal.

    Args:
        client: Slack client
        trigger_id: Slack trigger ID from command invocation
    """
    modal_view = {
        "type": "modal",
        "callback_id": "initial_modal",
        "title": {"type": "plain_text", "text": "Senora Self-Service"},
        "submit": {"type": "plain_text", "text": "Next"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Select an action to perform:"
                }
            },
            {
                "type": "input",
                "block_id": "action_select_block",
                "element": {
                    "type": "static_select",
                    "action_id": "action_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Choose an action..."
                    },
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": action_name},
                            "value": action_name
                        }
                        for action_name in sorted(action_data.keys())
                    ]
                },
                "label": {"type": "plain_text", "text": "Action"}
            }
        ]
    }

    client.views_open(trigger_id=trigger_id, view=modal_view)


def create_action_modal(action_name: str) -> Dict[str, Any]:
    """
    Create the action-specific modal form.

    Args:
        action_name: Name of the selected action

    Returns:
        Modal view dictionary
    """
    action_modal = action_data[action_name].copy()
    action_modal["callback_id"] = "updated_modal"
    action_modal["private_metadata"] = action_name

    return action_modal


def create_home_view() -> Dict[str, Any]:
    """Create the bot's home tab view."""
    return {
        "type": "home",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🤖 Senora Self-Service Bot"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Welcome! This bot provides self-service automation for common tasks."
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Getting Started:*\n"
                           "• Use `/senora` to see available actions\n"
                           "• Select an action and fill out the form\n"
                           "• You'll be notified when your request completes"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Available Actions:* {len(action_data)}\n"
                           + "\n".join(f"• {name}" for name in sorted(action_data.keys()))
                }
            }
        ]
    }


@tracer.capture_method
def execute_action(action_name: str, request_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the selected action by starting a CodeBuild project.

    Args:
        action_name: Name of the action to execute
        request_body: Full Slack request body

    Returns:
        CodeBuild build information

    Raises:
        ClientError: If CodeBuild project cannot be started
    """
    project_name = f"{os.environ.get('BOT_NAME', 'senora')}-{action_name}"

    logger.info(f"Starting CodeBuild project: {project_name}")

    try:
        response = codebuild_client.start_build(
            projectName=project_name,
            environmentVariablesOverride=[
                {
                    "name": "REQUEST_BODY",
                    "value": json.dumps(request_body),
                    "type": "PLAINTEXT"
                },
                {
                    "name": "TRIGGER_ID",
                    "value": request_body.get("trigger_id", ""),
                    "type": "PLAINTEXT"
                },
                {
                    "name": "USER_ID",
                    "value": request_body["user"]["id"],
                    "type": "PLAINTEXT"
                },
                {
                    "name": "USER_NAME",
                    "value": request_body["user"]["name"],
                    "type": "PLAINTEXT"
                }
            ]
        )

        build_info = response["build"]
        logger.info(f"Build started successfully: {build_info['id']}")

        return build_info

    except ClientError as e:
        logger.error(f"Failed to start CodeBuild project: {e}", exc_info=True)
        metrics.add_metric(name="CodeBuildStartError", unit=MetricUnit.Count, value=1)
        raise


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for Slack bot.

    Args:
        event: Lambda event from API Gateway
        context: Lambda context

    Returns:
        Response for API Gateway
    """
    logger.info("Processing Slack event")

    try:
        app = get_slack_app()
        slack_handler = SlackRequestHandler(app=app)

        response = slack_handler.handle(event, context)

        logger.info("Successfully processed Slack event")
        metrics.add_metric(name="RequestProcessed", unit=MetricUnit.Count, value=1)

        return response

    except Exception as e:
        logger.error(f"Unhandled error in lambda_handler: {e}", exc_info=True)
        metrics.add_metric(name="UnhandledError", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"})
        }
