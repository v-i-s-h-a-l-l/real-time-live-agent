"""Handle explicit interrupt signals from the browser."""

from loguru import logger

from pipecat.frames.frames import Frame, InputTransportMessageFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from protocol import CLIENT_INTERRUPT, is_client_message


class ClientInterruptProcessor(FrameProcessor):
    """Broadcast pipeline interruption when the client sends {type: interrupt}."""

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, InputTransportMessageFrame):
            if is_client_message(frame.message, CLIENT_INTERRUPT):
                logger.info("[ClientInterrupt] interrupt signal from browser")
                await self.broadcast_interruption()
                return

        await self.push_frame(frame, direction)
