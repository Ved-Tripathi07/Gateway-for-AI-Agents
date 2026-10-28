
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "config.yml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    """Read config.yml from the project root."""

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


CONFIG = load_config()

PROVIDER_API_KEYS: dict[str, str] = CONFIG["providers"]
TIERS: dict[str, list[str]] = CONFIG["tiers"]
ROUTER: dict = CONFIG["router"]
CLASSIFICATION: dict = CONFIG["classification"]
FALLBACK: dict = CONFIG["fallback"]
REQUEST_DEFAULTS: dict = CONFIG["defaults"]
OBSERVABILITY: dict = CONFIG["observability"]
COST: dict = CONFIG["cost"]
