from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator


class Signup(BaseModel):
    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter a name with at least two characters")
        return value

    email: EmailStr
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value):
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Use at least one letter and one number")
        return value


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailRequest(BaseModel):
    email: EmailStr


class TokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class Reset(TokenRequest):
    password: str = Field(min_length=10, max_length=128)
    _strong = field_validator("password")(Signup.strong_password.__func__)


class ChangePassword(BaseModel):
    current_password: str = Field(max_length=128)
    password: str = Field(min_length=10, max_length=128)
    _strong = field_validator("password")(Signup.strong_password.__func__)


class WorkspaceInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class MemberInput(BaseModel):
    email: EmailStr
    role: Literal["admin", "member", "viewer"] = "member"


class RunInput(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    provider: Literal["offline", "groq", "openai", "local"] = "offline"
    top_k: int = Field(default=5, ge=1, le=10)
    save_note: bool = False


class EvalCase(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    expected_answer: str = Field(default="", max_length=4000)
    expected_document_ids: list[str] = Field(default_factory=list, max_length=10)
    expect_blocked: bool = False
    expect_refusal: bool = False


class DatasetInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    cases: list[EvalCase] = Field(min_length=1, max_length=30)


class EvalInput(BaseModel):
    dataset_id: str
    provider: Literal["offline", "groq", "openai", "local"] = "offline"
    judge: bool = False
    pass_threshold: float = Field(default=0.6, ge=0, le=1)


class PredictInput(BaseModel):
    rows: list[dict] = Field(min_length=1, max_length=100)


class QuantMeasurement(BaseModel):
    mode: Literal["fp16", "int8", "nf4"]
    load_seconds: float = Field(ge=0)
    peak_memory_mb: float = Field(ge=0)
    inference_seconds: float = Field(gt=0)
    generated_tokens: int = Field(ge=0)
    tokens_per_second: float = Field(ge=0)
    output: str = Field(max_length=10000)


class QuantReport(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    device: str = Field(min_length=1, max_length=200)
    prompt: str = Field(max_length=2000)
    measurements: list[QuantMeasurement] = Field(min_length=1, max_length=3)
    library_versions: dict[str, str] = Field(default_factory=dict, max_length=10)
