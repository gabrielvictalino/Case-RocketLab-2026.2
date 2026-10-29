from pydantic import BaseModel, Field, SecretStr


class Login(BaseModel):
    login: str = Field(min_length=1, max_length=100)
    senha: SecretStr = Field(min_length=1, max_length=1024)


class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int
