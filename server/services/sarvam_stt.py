"""Sarvam STT that survives a dropped provider websocket.

Pipecat's Sarvam client does not reconnect. After ~30–40s the underlying
`websockets` keepalive ping races with audio writes, the socket dies with
1011, and every later mic frame logs "Error sending audio to Sarvam" with
no transcripts and no tutor replies.

This wrapper:
1. Disables the protocol ping (Pipecat already sends idle silence).
2. Reconnects the Sarvam socket instead of flooding ErrorFrames.
"""

from __future__ import annotations

import asyncio

from loguru import logger
from pipecat.frames.frames import ErrorFrame
from pipecat.services.sarvam.stt import SarvamSTTService

from ops_log import ops_event


def disable_websockets_protocol_ping(socket_client) -> None:
    """Stop legacy `websockets` ping/pong so it cannot race audio writes."""
    ws = getattr(socket_client, "_websocket", None)
    if ws is None:
        return
    try:
        ws.ping_interval = None
    except Exception:
        return
    task = getattr(ws, "keepalive_ping_task", None)
    if task is not None and not task.done():
        task.cancel()


class ReconnectingSarvamSTTService(SarvamSTTService):
    async def _connect(self):
        await super()._connect()
        disable_websockets_protocol_ping(self._socket_client)

    async def _do_reconnect(self):
        await self._disconnect()
        await self._connect()

    async def _reconnect(self):
        ops_event("stt_reconnect_attempt", category="stt")
        await super()._reconnect()
        if self._socket_client is not None:
            ops_event("stt_reconnect_success", category="stt")

    async def run_stt(self, audio: bytes):
        if not self._socket_client:
            if not self._reconnecting:
                await self._request_reconnect()
            yield None
            return

        async for frame in super().run_stt(audio):
            if isinstance(frame, ErrorFrame):
                ops_event(
                    "stt_connection_failure",
                    category="stt",
                    error_type="send_failed",
                )
                logger.warning(
                    "Sarvam STT send failed; reconnecting | err={}",
                    getattr(frame, "error", "unknown"),
                )
                await self._request_reconnect()
                yield None
                return
            yield frame

    async def _receive_task_handler(self):
        if not self._socket_client:
            return
        try:
            await self._socket_client.start_listening()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            ops_event(
                "stt_connection_failure",
                category="stt",
                error_type=type(exc).__name__,
            )
            logger.warning(
                "Sarvam STT receive ended; reconnecting | err={}",
                type(exc).__name__,
            )
        if self._socket_client is not None:
            await self._request_reconnect()
