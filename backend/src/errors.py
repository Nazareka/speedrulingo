import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger(__name__)
INTERNAL_SERVER_ERROR_STATUS = 500


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        LOGGER.warning(
            "AppError on %s %s: %s",
            request.method,
            request.url.path,
            exc.message,
        )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(HTTPException)
    def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code >= INTERNAL_SERVER_ERROR_STATUS:
            LOGGER.error(
                "HTTPException on %s %s: status=%s detail=%s",
                request.method,
                request.url.path,
                exc.status_code,
                exc.detail,
            )
        else:
            LOGGER.info(
                "HTTPException on %s %s: status=%s detail=%s",
                request.method,
                request.url.path,
                exc.status_code,
                exc.detail,
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        LOGGER.exception(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return JSONResponse(status_code=INTERNAL_SERVER_ERROR_STATUS, content={"detail": "Internal Server Error"})
