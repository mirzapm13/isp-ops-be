import os
import yaml
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(__file__)

def _resolve_env(value):
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_value = os.getenv(value[2:-1])
        if env_value is None:
            raise RuntimeError(f"Missing env var: {value}")
        return env_value
    return value


with open(os.path.join(BASE_DIR, "routers.yaml")) as f:
    raw = yaml.safe_load(f)

ROUTERS = [
    {k: _resolve_env(v) for k, v in r.items()}
    for r in raw
]

_cors_origins_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
CORS_ORIGINS = [
    origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()
]

