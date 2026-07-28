import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pipecat.frames.frames import LLMContextFrame
from pipecat.pipeline.runner import PipelineRunner

from config import CEREBRAS_API_KEY, SARVAM_API_KEY, FRONTEND_ORIGINS
from pipeline import create_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Voice Agent server starting up...")
    yield
    logger.info("Voice Agent server shutting down.")


app = FastAPI(title="Ministros Voice Agent", lifespan=lifespan)

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
    missing = []
    if not CEREBRAS_API_KEY:
        missing.append("CEREBRAS_API_KEY")
    if not SARVAM_API_KEY:
        missing.append("SARVAM_API_KEY")
    if missing:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "missing": missing},
        )
    return {"status": "ready"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_id = str(uuid.uuid4())

    await websocket.accept()
    logger.info(
        "Client connected | session_id={} client={}",
        session_id,
        websocket.client,
    )

    language = websocket.query_params.get("lang", "en-IN")

    try:
        transport, task, context = await create_pipeline(
            websocket,
            language=language,
            session_id=session_id,
        )

        @transport.event_handler("on_client_connected")
        async def on_connected(t, ws):
            logger.info("Pipeline running | session_id={}", session_id)
            greeting = (
                "The user just connected. Greet them warmly — introduce yourself as "
                "Ministros in one short sentence and ask how you can help. "
                "Keep it natural and brief."
            )
            context.messages.append({"role": "system", "content": greeting})
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
        except Exception:
            pass


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


# Serve frontend — must be LAST (catches all remaining routes)
_client_dir = Path(__file__).resolve().parent.parent / "client"
app.mount("/", StaticFiles(directory=str(_client_dir), html=True), name="static")
