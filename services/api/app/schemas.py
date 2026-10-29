"""HTTP request/response validation."""
from pydantic import BaseModel, Field, field_validator


class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: str):
        email = email.strip().lower()
        if email.count("@") != 1 or "." not in email.split("@")[-1] or " " in email:
            raise ValueError("Укажите корректный адрес электронной почты")
        return email


class Signup(Credentials):
    invite_code: str | None = Field(default=None, max_length=128)
    display_name: str = Field(min_length=2, max_length=80)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, name: str):
        clean = name.strip()
        if len(clean) < 2:
            raise ValueError("Имя слишком короткое")
        return clean


class NoteCreate(BaseModel):
    title: str = Field(default="Без названия", max_length=160)
    content: str = Field(default="", max_length=50000)


class NoteUpdate(BaseModel):
    title: str = Field(max_length=160)
    content: str = Field(max_length=50000)


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=2, max_length=80)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Имя слишком короткое")
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=10, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)
