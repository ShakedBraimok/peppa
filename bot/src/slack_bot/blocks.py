"""
Dynamic Action Menu Builder

Scans the actions directory and builds Slack UI components
from action definitions.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any
from aws_lambda_powertools import Logger

logger = Logger(child=True)

# Store action data globally
action_data: Dict[str, Any] = {}


def load_actions() -> Dict[str, Any]:
    """
    Load all action definitions from the actions directory.

    Returns:
        Dictionary mapping action names to their modal definitions
    """
    actions = {}
    actions_dir = Path(__file__).parent / "actions"

    if not actions_dir.exists():
        logger.warning(f"Actions directory not found: {actions_dir}")
        return actions

    # Scan for action directories
    for action_path in actions_dir.iterdir():
        if not action_path.is_dir() or action_path.name.startswith((".", "_")):
            continue

        modal_file = action_path / "modal.json"

        if not modal_file.exists():
            logger.warning(f"No modal.json found for action: {action_path.name}")
            continue

        try:
            with open(modal_file, "r") as f:
                modal_data = json.load(f)

            actions[action_path.name] = modal_data
            logger.info(f"Loaded action: {action_path.name}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {modal_file}: {e}")
        except Exception as e:
            logger.error(f"Error loading action {action_path.name}: {e}")

    logger.info(f"Loaded {len(actions)} actions")
    return actions


# Load actions on module import
action_data = load_actions()
