from fastapi import HTTPException


class APIError(HTTPException):
    def __init__(self, status: int, detail: str, code: str, headers: dict | None = None):
        super().__init__(status, detail, headers)
        self.code = code
