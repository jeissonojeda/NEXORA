class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.headers = headers
        super().__init__(message)
