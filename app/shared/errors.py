"""Errores de dominio, independientes de HTTP. El router los traduce a un status."""


class DomainError(Exception):
    code = "domain_error"
    http_status = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        detail: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.detail = detail or {}

    def to_detail(self) -> dict:
        payload = {"code": self.code, "message": self.message}
        payload.update(self.detail)
        return payload
