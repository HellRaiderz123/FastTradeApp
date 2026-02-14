import json
from pathlib import Path
from typing import Any, Dict
import joblib

from app.core.ml.config import StockMLConfig


def ensure_model_dir(config: StockMLConfig) -> None:
    config.model_dir.mkdir(parents=True, exist_ok=True)


def save_model(model: Any, metadata: Dict[str, Any], config: StockMLConfig) -> Path:
    ensure_model_dir(config)
    model_path = config.model_path
    joblib.dump(model, model_path)

    meta_path = model_path.with_suffix(".json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return model_path


def load_model(config: StockMLConfig):
    model_path = config.model_path
    if not model_path.exists():
        return None
    return joblib.load(model_path)


def load_metadata(config: StockMLConfig) -> Dict[str, Any]:
    meta_path = config.model_path.with_suffix(".json")
    if not meta_path.exists():
        return {}
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)
