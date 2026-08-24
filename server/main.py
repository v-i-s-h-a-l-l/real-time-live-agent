import json
import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pipecat.frames.frames import LLMContextFrame
from pipecat.pipeline.runner import PipelineRunner

from auth.routes import router as auth_router
from auth.store import get_store
from config import (
    FRONTEND_ORIGINS,
    config_warnings,
    is_production,
    missing_required_keys,
    production_blockers,
)
from opening import opening_turn_messages
from ops_log import ops_event
from pipeline import create_pipeline
from protocol import CLIENT_AUTH, SERVER_AUTH_OK
from security import (
    WS_CLOSE_CAPACITY,
    WS_CLOSE_FORBIDDEN,
    WS_CLOSE_NOT_READY,
    WS_CLOSE_RATE_LIMITED,
    WS_CLOSE_UNAUTHORIZED,
    origin_allowed,
    parse_voice_ticket,
    session_limiter,
    token_required,
)

_AUTH_HANDSHAKE_SECS = 5.0

# Wait briefly for the browser to send session + learning context before greeting.
_SESSION_CONTEXT_WAIT_SECS = 1.5
_SESSION_CONTEXT_POLL_SECS = 0.05


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Voice Agent server starting up (Lumina tutor + selectable Cartesia voices)...")
    for warning in config_warnings():
        logger.warning(warning)
    yield
    logger.info("Voice Agent server shutting down.")


app = FastAPI(title="Lumina Voice Tutor", lifespan=lifespan)

_cors_wildcard = FRONTEND_ORIGINS == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=not _cors_wildcard,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, _exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "invalid"})


@app.exception_handler(Exception)
async def unhandled_error(_request: Request, exc: Exception):
    logger.error("unhandled_error err={}", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "server_error"})


async def _authenticate_socket(websocket: WebSocket, session_id: str) -> str | None:
    """First-message voice ticket. Never reads tokens from the URL.

    Returns user_id, or None when anonymous development connections are allowed.
    """
    if websocket.query_params.get("token"):
        ops_event(
            "ws_auth_failure",
            session_id=session_id,
            category="auth",
            reason="query_token_rejected",
        )
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return ""

    if not token_required():
        return None

    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=_AUTH_HANDSHAKE_SECS)
    except (TimeoutError, asyncio.TimeoutError, WebSocketDisconnect):
        ops_event(
            "ws_auth_failure",
            session_id=session_id,
            category="auth",
            reason="handshake_timeout",
        )
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return ""
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        ops_event(
            "ws_auth_failure",
            session_id=session_id,
            category="auth",
            reason="invalid_json",
        )
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return ""
    if not isinstance(message, dict) or message.get("type") != CLIENT_AUTH:
        ops_event(
            "ws_auth_failure",
            session_id=session_id,
            category="auth",
            reason="missing_auth_frame",
        )
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return ""
    token = message.get("token")
    if not isinstance(token, str):
        ops_event(
            "ws_auth_failure",
            session_id=session_id,
            category="auth",
            reason="invalid_token_type",
        )
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return ""
    parsed = parse_voice_ticket(token)
    if parsed is None:
        ops_event(
            "ws_auth_failure",
            session_id=session_id,
            category="auth",
            reason="invalid_ticket",
        )
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return ""
    consumed = get_store().consume_voice_jti(parsed["jti"], parsed["user_id"])
    if not consumed:
        ops_event(
            "ws_auth_failure",
            session_id=session_id,
            category="auth",
            reason="ticket_reuse",
        )
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return ""
    await websocket.send_text(json.dumps({"type": SERVER_AUTH_OK}))
    ops_event("ws_auth_ok", session_id=session_id, category="auth")
    return parsed["user_id"]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    missing = missing_required_keys()
    blockers = production_blockers()
    if missing or blockers:
        if is_production():
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready"},
            )
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "missing": missing,
                "blockers": blockers,
            },
        )
    payload: dict = {"status": "ready"}
    warnings = config_warnings()
    if warnings:
        payload["warnings"] = warnings
    return payload


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_id = str(uuid.uuid4())
    client_host = websocket.client.host if websocket.client else "unknown"
    opened_at = time.monotonic()

    if missing_required_keys() or production_blockers():
        ops_event(
            "voice_session_failure",
            session_id=session_id,
            category="config",
            reason="not_ready",
        )
        await websocket.close(code=WS_CLOSE_NOT_READY)
        return
    if not origin_allowed(websocket.headers.get("origin")):
        ops_event(
            "ws_auth_failure",
            session_id=session_id,
            category="origin",
            reason="origin_rejected",
        )
        await websocket.close(code=WS_CLOSE_FORBIDDEN)
        return

    try:
        await websocket.accept()
        ops_event(
            "ws_open",
            session_id=session_id,
            category="websocket",
            client_host=client_host,
        )
        user_id = await _authenticate_socket(websocket, session_id)
        if user_id == "":
            return
    except WebSocketDisconnect:
        ops_event(
            "ws_close",
            session_id=session_id,
            category="websocket",
            reason="disconnect_before_auth",
        )
        return

    limit_reason = session_limiter.acquire(session_id, client_host)
    if limit_reason == "rate_limited":
        ops_event(
            "voice_session_failure",
            session_id=session_id,
            category="capacity",
            reason="rate_limited",
        )
        await websocket.close(code=WS_CLOSE_RATE_LIMITED)
        return
    if limit_reason == "capacity":
        ops_event(
            "voice_session_failure",
            session_id=session_id,
            category="capacity",
            reason="capacity",
        )
        await websocket.close(code=WS_CLOSE_CAPACITY)
        return

    try:
        logger.info(
            "Client connected | session_id={} client={}",
            session_id,
            websocket.client,
        )

        # Auto language: Sarvam STT language="unknown" + LanguageTracker
        language = websocket.query_params.get("lang", "auto")
        voice_id = websocket.query_params.get("voice")
        logger.info(
            "WS params | session_id={} lang={} voice={}",
            session_id,
            language,
            voice_id,
        )

        transport, task, context, session_store = await create_pipeline(
            websocket,
            language=language,
            session_id=session_id,
            voice_id=voice_id,
        )

        @transport.event_handler("on_client_connected")
        async def on_connected(t, ws):
            logger.info("Pipeline running | session_id={}", session_id)
            ops_event(
                "voice_session_ready",
                session_id=session_id,
                category="voice",
                duration_ms=int((time.monotonic() - opened_at) * 1000),
            )
            # Allow the client to deliver session_context before the first LLM turn.
            waited = 0.0
            while waited < _SESSION_CONTEXT_WAIT_SECS:
                if session_store.applied and session_store.learning_context:
                    break
                await asyncio.sleep(_SESSION_CONTEXT_POLL_SECS)
                waited += _SESSION_CONTEXT_POLL_SECS

            for message in opening_turn_messages(session_store):
                context.add_message(message)
            await task.queue_frames([LLMContextFrame(context=context)])

        @transport.event_handler("on_client_disconnected")
        async def on_disconnected(t, ws):
            logger.info(
                "Client disconnected — stopping pipeline | session_id={}", session_id
            )
            ops_event(
                "ws_close",
                session_id=session_id,
                category="websocket",
                reason="client_disconnected",
                duration_ms=int((time.monotonic() - opened_at) * 1000),
            )
            await task.cancel()

        runner = PipelineRunner()
        await runner.run(task)

    except WebSocketDisconnect:
        ops_event(
            "ws_close",
            session_id=session_id,
            category="websocket",
            reason="clean_disconnect",
            duration_ms=int((time.monotonic() - opened_at) * 1000),
        )
        logger.info("WebSocket disconnected cleanly | session_id={}", session_id)
    except Exception as e:
        ops_event(
            "pipeline_exception",
            session_id=session_id,
            category="pipeline",
            error_type=type(e).__name__,
        )
        logger.error(
            "Pipeline error | session_id={} err={}",
            session_id,
            e,
            exc_info=not is_production(),
        )
        try:
            await websocket.close()
        except RuntimeError as close_err:
            # Already closed by the transport — worth a trace, not a crash.
            logger.debug(
                "Socket already closed | session_id={} err={}",
                session_id,
                close_err,
            )
    finally:
        session_limiter.release(session_id)


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=not is_production(),
        log_level="info",
    )


# Leftover engine debug UI. Never mount at "/" — Starlette's catch-all StaticFiles
# only allows GET/HEAD, so POST /auth/signup and /auth/signin become 405.
if not is_production():
    _client_dir = Path(__file__).resolve().parent.parent / "client"
    if _client_dir.is_dir():
        app.mount(
            "/debug-ui",
            StaticFiles(directory=str(_client_dir), html=True),
            name="static",
        )
