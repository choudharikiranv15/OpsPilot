from pathlib import Path
from typing import Optional, Dict, Any
import json


def load_config(project_root: str) -> Optional[Dict[str, Any]]:
    """
    Load configuration from the project root directory.

    Args:
        project_root: The root directory of the project

    Returns:
        Configuration dictionary if found, None otherwise
    """
    config_path = Path(project_root) / ".opspilot.json"

    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)

    return None
