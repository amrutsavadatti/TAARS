from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM ---
    llm_provider: Literal["openai", "anthropic"] = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    embedding_provider: Literal["openai", "huggingface"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- Vector DB ---
    vector_db: Literal["chroma"] = "chroma"
    chroma_persist_dir: str = "./data/chroma"

    # --- Valkey ---
    valkey_url: str = "redis://localhost:6379"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./data/conversations.db"

    # --- OTP Gate ---
    enable_otp_gate: bool = False
    otp_gate_mode: Literal["upfront", "after_n"] = "after_n"
    otp_gate_after_n_questions: int = 1  # ask on 1st question by default;
                                          # set to 2 or 3 to let visitor chat
                                          # freely before the identity gate
    email_provider: str = "resend"
    email_from: str = "noreply@yourdomain.com"
    otp_expiry_seconds: int = 300
    otp_max_retries: int = 3

    # --- Rate Limiting ---
    rate_limit_per_ip_per_day: int = 50
    rate_limit_per_email_per_day: int = 20

    # --- Session ---
    session_ttl_minutes: int = 30
    session_context_window: int = 5
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_expiry_hours: int = 24

    # --- Chat ---
    enable_hyde: bool = False
    retrieval_top_k: int = 5
    enable_reranking: bool = False     # cross-encoder reranking; disable for small
                                       # corpora — vector similarity alone works well
    rerank_top_n: int = 3
    similarity_threshold: float = 0.62  # cosine similarity lower bound [0, 1]
                                         # career queries score ~0.65-0.72
                                         # off-topic queries score ~0.50-0.58
    enable_response_cache: bool = True
    profile_partial_threshold: float = Field(default=0.10, ge=0.0, le=1.0)
    profile_supported_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    session_end_timeout_minutes: int = 10

    # --- Ingestion ---
    max_upload_size_mb: int = 10
    allowed_file_types: str = "pdf,png,jpg,jpeg,txt,md,docx"

    # --- Owner ---
    owner_name: str = "Amrut"
    owner_contact_email: str = "ryan@yourdomain.com"
    owner_notification_channel: Literal["email", "slack"] = "email"
    owner_slack_webhook: str = ""
    cal_com_booking_url: str = ""

    # --- Widget ---
    suggested_questions: str = ""
    widget_greeting: str = "Hi! Ask me anything about my experience, skills, and projects."
    widget_theme_primary: str = "#2563eb"

    # --- Analytics ---
    umami_script_url: str = ""
    umami_website_id: str = ""

    # --- Agents ---
    enable_follow_up_email: bool = True
    follow_up_delay_minutes: int = 90
    follow_up_min_questions: int = 3
    follow_up_intent_threshold: float = 0.7
    enable_owner_notifications: bool = True
    enable_content_gap_detection: bool = True
    weekly_digest_day: str = "monday"
    weekly_digest_hour: int = 9
    owner_approval_required: bool = False

    @property
    def allowed_file_types_list(self) -> list[str]:
        return [t.strip() for t in self.allowed_file_types.split(",")]

    @property
    def suggested_questions_list(self) -> list[str]:
        if not self.suggested_questions:
            return []
        return [q.strip() for q in self.suggested_questions.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
