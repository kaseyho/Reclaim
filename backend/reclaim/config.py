from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./reclaim.db")
    app_url: str = os.getenv("APP_URL", "http://localhost:5173").rstrip("/")
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    payment_mode: str = os.getenv("PAYMENT_MODE", "demo")
    paypal_client_id: str = os.getenv("PAYPAL_CLIENT_ID", "")
    paypal_client_secret: str = os.getenv("PAYPAL_CLIENT_SECRET", "")
    paypal_webhook_id: str = os.getenv("PAYPAL_WEBHOOK_ID", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini-2025-04-14")
    auth_mode: str = os.getenv("AUTH_MODE", "workspace")
    supabase_url: str = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_publishable_key: str = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    jwt_audience: str = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    session_ttl_hours: int = int(os.getenv("SESSION_TTL_HOURS", "72"))
    checkout_minutes: int = int(os.getenv("CHECKOUT_MINUTES", "15"))
    auto_worker: bool = os.getenv("AUTO_WORKER", "true").lower() == "true"

    def __post_init__(self):
        if self.payment_mode not in {"demo", "sandbox"}:
            raise ValueError("Only demo and PayPal sandbox payments are supported.")
        if self.auth_mode not in {"workspace", "supabase"}:
            raise ValueError("AUTH_MODE must be workspace or supabase.")
        if self.auth_mode == "supabase" and not self.supabase_url:
            raise ValueError("Supabase authentication needs SUPABASE_URL.")
        if self.supabase_publishable_key.startswith("sb_secret_"):
            raise ValueError("SUPABASE_PUBLISHABLE_KEY must be a public client key, not a secret key.")
        if self.supabase_publishable_key.count(".")==2:
            import jwt
            try:
                if jwt.decode(self.supabase_publishable_key,options={"verify_signature":False}).get("role")=="service_role":
                    raise ValueError("Do not expose a Supabase service-role key as a public client key.")
            except jwt.PyJWTError:
                pass

    @property
    def paypal_ready(self):
        return bool(self.paypal_client_id and self.paypal_client_secret)
