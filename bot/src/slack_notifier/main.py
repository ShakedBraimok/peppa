"""
Slack Notifier Lambda Function

Sends notifications to Slack users after action completion.
"""
import json
import os
from typing import Dict, Any
import boto3
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "slack-notifier"))
tracer = Tracer(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "slack-notifier"))
metrics = Metrics(namespace="SlackBot", service="slack-notifier")

secrets_client = boto3.client("secretsmanager")
_slack_client = None


@tracer.capture_method
def get_slack_client() -> WebClient:
    """Get or initialize Slack WebClient."""
    global _slack_client

    if _slack_client is None:
        secret_name = os.environ.get("SLACK_SECRET_TOKEN")

        try:
            response = secrets_client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response["SecretString"])
            bot_token = secret_data["slack_bot_token"]

            _slack_client = WebClient(token=bot_token)
            logger.info("Slack client initialized")

        except ClientError as e:
            logger.error(f"Failed to get Slack credentials: {e}")
            raise

    return _slack_client


@tracer.capture_method
def send_direct_message(user_id: str, message: str) -> Dict[str, Any]:
    """
    Send a direct message to a Slack user.

    Args:
        user_id: Slack user ID
        message: Message text (supports markdown)

    Returns:
        Slack API response
    """
    client = get_slack_client()

    try:
        response = client.chat_postMessage(
            channel=user_id,
            text=message,
            mrkdwn=True
        )

        logger.info(f"Message sent to user {user_id}")
        metrics.add_metric(name="DirectMessageSent", unit=MetricUnit.Count, value=1)

        return response.data

    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
        metrics.add_metric(name="SlackApiError", unit=MetricUnit.Count, value=1)
        raise


@tracer.capture_method
def send_thread_reply(channel: str, thread_ts: str, message: str) -> Dict[str, Any]:
    """
    Send a reply in a thread.

    Args:
        channel: Slack channel ID
        thread_ts: Thread timestamp
        message: Message text (supports markdown)

    Returns:
        Slack API response
    """
    client = get_slack_client()

    try:
        response = client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=message,
            mrkdwn=True
        )

        logger.info(f"Thread reply sent to channel {channel}")
        metrics.add_metric(name="ThreadReplySent", unit=MetricUnit.Count, value=1)

        return response.data

    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
        metrics.add_metric(name="SlackApiError", unit=MetricUnit.Count, value=1)
        raise


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for Slack notifications.

    Expected event format:
    {
        "notification_type": "direct-message" | "in-thread",
        "user_id": "U123456",
        "message": "Your message here",
        "channel": "C123456" (for in-thread),
        "thread_ts": "1234567890.123456" (for in-thread)
    }

    Args:
        event: Notification request
        context: Lambda context

    Returns:
        Response with status
    """
    logger.info(f"Processing notification: {json.dumps(event)}")

    try:
        notification_type = event.get("notification_type", "direct-message")
        message = event.get("message", "")

        if not message:
            logger.error("No message provided")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Message is required"})
            }

        if notification_type == "direct-message":
            user_id = event.get("user_id")
            if not user_id:
                logger.error("No user_id provided for direct message")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "user_id is required for direct messages"})
                }

            response = send_direct_message(user_id, message)

        elif notification_type == "in-thread":
            channel = event.get("channel")
            thread_ts = event.get("thread_ts")

            if not channel or not thread_ts:
                logger.error("Missing channel or thread_ts for thread reply")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "channel and thread_ts required for thread replies"})
                }

            response = send_thread_reply(channel, thread_ts, message)

        else:
            logger.error(f"Invalid notification type: {notification_type}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid notification_type: {notification_type}"})
            }

        logger.info("Notification sent successfully")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Notification sent",
                "response": response
            })
        }

    except Exception as e:
        logger.error(f"Error sending notification: {e}", exc_info=True)
        metrics.add_metric(name="NotificationError", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
