import os
import time
import yaml
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
MODELS_CONFIG = BASE_DIR / "atlas_config" / "models.yaml"


def _load_models() -> dict:
    if MODELS_CONFIG.exists():
        return yaml.safe_load(MODELS_CONFIG.read_text(encoding="utf-8"))
    return {"default": os.getenv("ATLAS_DEFAULT_MODEL", "minimax/minimax-m2.5")}


def get_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )


def get_model_for_agent(agent_name: str) -> str:
    cfg = _load_models()
    return cfg.get("agents", {}).get(agent_name) or cfg.get("default", "minimax/minimax-m2.5")


def get_temperature_for_agent(agent_name: str) -> float:
    cfg = _load_models()
    temps = cfg.get("temperature", {})
    return float(temps.get(agent_name) or temps.get("default", 0.2))


def chat(messages: list, agent_name: str = "default", retries: int = 3) -> str:
    client = get_client()
    model = get_model_for_agent(agent_name)
    temperature = get_temperature_for_agent(agent_name)

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            wait = 2 ** attempt
            if attempt < retries - 1:
                time.sleep(wait)
            else:
                raise RuntimeError(f"LLM failed after {retries} attempts: {e}") from e
