from fastapi import HTTPException


class APIError(HTTPException):
    def __init__(self, status: int, detail: str, code: str):
        super().__init__(status, detail)
        self.code = code
