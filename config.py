"""
Single place environment/config is read from. Everything else in this
project imports Config instead of reading os.environ directly, so
switching sandbox -> prod is a config change, not a code change (per
the abdm-m2-care-context-linking skill's environment guardrail).
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    env: str                 # "sandbox" or "prod"
    base_url: str
    hip_id: str
    client_id: str
    client_secret: str

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


_SANDBOX_BASE_URL = "https://api.dev.eka.care"   # placeholder -- confirm exact
_PROD_BASE_URL = "https://api.eka.care"              # placeholder -- confirm exact


def load_config() -> Config:
    env = os.environ.get("EKA_ENV", "sandbox").lower()
    if env not in ("sandbox", "prod"):
        raise ValueError(f"EKA_ENV must be 'sandbox' or 'prod', got: {env!r}")

    base_url = os.environ.get("EKA_BASE_URL") or (
        _PROD_BASE_URL if env == "prod" else _SANDBOX_BASE_URL
    )
    hip_id = os.environ.get("EKA_HIP_ID", "")
    client_id = os.environ.get("EKA_CLIENT_ID", "")
    client_secret = os.environ.get("EKA_CLIENT_SECRET", "")

    if not hip_id:
        raise ValueError("EKA_HIP_ID is not set -- put it in your environment, not in code.")

    return Config(env=env, base_url=base_url, hip_id=hip_id,
                  client_id=client_id, client_secret=client_secret)
