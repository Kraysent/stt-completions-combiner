from fastapi import responses


def openai_error(*, message: str, error_type: str, code: str, status_code: int) -> responses.JSONResponse:
    return responses.JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": error_type,
                "code": code,
            }
        },
    )
