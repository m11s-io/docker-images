from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=True, extra="ignore", populate_by_name=True)

    model_id: str = Field(default="mistralai/Timestral-209M", min_length=1, alias="MODEL_ID")
    model_revision: str = Field(min_length=40, max_length=40, alias="MODEL_REVISION")
    model_device: Literal["cpu", "cuda"] = Field(default="cpu", alias="MODEL_DEVICE")
    hf_home: str = Field(default="/models/huggingface", alias="HF_HOME")
    hf_token: SecretStr | None = Field(default=None, alias="HF_TOKEN")
    torch_num_threads: int = Field(default=2, ge=1, alias="TORCH_NUM_THREADS")

    max_request_bytes: int = Field(default=8 * 1024 * 1024, ge=1, alias="MAX_REQUEST_BYTES")
    max_batch_size: int = Field(default=8, ge=1, alias="MAX_BATCH_SIZE")
    max_rows_per_series: int = Field(default=32, ge=1, alias="MAX_ROWS_PER_SERIES")
    max_context_steps: int = Field(default=32_768, ge=1, alias="MAX_CONTEXT_STEPS")
    max_prediction_length: int = Field(default=1_024, ge=1, alias="MAX_PREDICTION_LENGTH")
    max_output_elements: int = Field(default=1_000_000, ge=1, alias="MAX_OUTPUT_ELEMENTS")

    @field_validator("model_id", "model_revision", "hf_home")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("model_revision")
    @classmethod
    def revision_is_commit(cls, value: str) -> str:
        if any(char not in "0123456789abcdefABCDEF" for char in value):
            raise ValueError("must be an immutable 40-character commit hash")
        return value.lower()
