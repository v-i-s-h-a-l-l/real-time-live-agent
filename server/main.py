import uuid
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pipecat.frames.frames import LLMContextFrame
from pipecat.pipeline.runner import PipelineRunner

from config import config_warnings, missing_required_keys, FRONTEND_ORIGINS
from opening import opening_system_message
from pipeline import create_pipeline

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
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    missing = missing_required_keys()
    if missing:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "missing": missing},
        )
    payload: dict = {"status": "ready"}
    warnings = config_warnings()
    if warnings:
        payload["warnings"] = warnings
    return payload


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_id = str(uuid.uuid4())

    await websocket.accept()
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

    try:
        transport, task, context, session_store = await create_pipeline(
            websocket,
            language=language,
            session_id=session_id,
            voice_id=voice_id,
        )

        @transport.event_handler("on_client_connected")
        async def on_connected(t, ws):
            logger.info("Pipeline running | session_id={}", session_id)
            # Allow the client to deliver session_context before the first LLM turn.
            waited = 0.0
            while waited < _SESSION_CONTEXT_WAIT_SECS:
                if session_store.applied and session_store.learning_context:
                    break
                await asyncio.sleep(_SESSION_CONTEXT_POLL_SECS)
                waited += _SESSION_CONTEXT_POLL_SECS

            context.add_message(
                {"role": "system", "content": opening_system_message(session_store)}
            )
            await task.queue_frames([LLMContextFrame(context=context)])

        @transport.event_handler("on_client_disconnected")
        async def on_disconnected(t, ws):
            logger.info(
                "Client disconnected — stopping pipeline | session_id={}", session_id
            )
            await task.cancel()

        runner = PipelineRunner()
        await runner.run(task)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected cleanly | session_id={}", session_id)
    except Exception as e:
        logger.error(
            "Pipeline error | session_id={} err={}",
            session_id,
            e,
            exc_info=True,
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


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info",
    )


# Leftover static page for engine-only debugging. The product UI is
# tutor-frontend/ on :3000. This mount is last so it does not shadow /ws.
_client_dir = Path(__file__).resolve().parent.parent / "client"
app.mount("/", StaticFiles(directory=str(_client_dir), html=True), name="static")
