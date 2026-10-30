"""Configure redacted transport failures on the official SDK application.

The SDK validates/decodes before Model.predict. Configure public exception hooks
there; never register inference routes or run an application-owned server.
"""
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def _invalid_transport(_request, _exception):
    # Do not inspect/stringify/log the exception: SDK/Pydantic exceptions can
    # contain the full input tensor or an untrusted binary header.
    return JSONResponse(status_code=400,content={'error':'invalid inference transport'})


def configure_transport_errors(app):
    # These specific hooks survive the SDK's later registration of its generic
    # Exception handler. SDK InvalidInput/ModelNotReady retain their more-specific
    # standard mappings, while decoder and schema failures are redacted here.
    for error in (RequestValidationError,ValueError,TypeError,KeyError,OverflowError):
        app.add_exception_handler(error,_invalid_transport)
