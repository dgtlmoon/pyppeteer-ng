import asyncio
import logging
from typing import Any, AsyncIterable, Callable, Iterable, Optional, Union

from websockets import Data, WebSocketClientProtocol, connect

logger = logging.getLogger(__name__)


class WebsocketTransport:
    def __init__(self, ws: WebSocketClientProtocol, loop: asyncio.AbstractEventLoop = None):
        self.onmessage: Optional[Callable[[str], Any]] = None
        self.onclose: Optional[Callable[[], Any]] = None
        self.ws = ws
        self.loop = loop or asyncio.get_event_loop()
        self._closed = False
        
        # Track socket state
        self._socket_open = True
        
        # Setup socket state monitoring
        self.ws.connection_lost_waiter.add_done_callback(self._handle_connection_lost)

    @classmethod
    async def create(cls, uri: str, loop: asyncio.AbstractEventLoop = None) -> 'WebsocketTransport':
        connection = await connect(
            uri=uri,
            # chrome doesn't respond to pings
            # todo: remove note after websockets release
            # waiting on websockets to release new version where ping_interval is typed correctly
            ping_interval=None,  # type: ignore
            max_size=256 * 1024 * 1024,  # 256Mb
            loop=loop,
            close_timeout=5,
            # todo check if speed is affected
            # note: seems to work w/ compression
            compression=None,
        )
        return cls(connection, loop)

    def _handle_connection_lost(self, future):
        """Called when the underlying websocket connection is lost."""
        self._socket_open = False
        if not self._closed and self.onclose:
            # Schedule onclose callback
            if self.loop and self.loop.is_running():
                self.loop.create_task(self._trigger_onclose())
    
    async def _trigger_onclose(self):
        """Trigger onclose callback safely."""
        try:
            if self.onclose:
                await self.onclose()
        except Exception as e:
            logger.error(f"Error in onclose callback: {e}")
        finally:
            self._closed = True

    async def send(self, message: Union[Data, Iterable[Data], AsyncIterable[Data]]) -> None:
        """Send a message over the websocket."""
        if not self._socket_open:
            raise ConnectionError("Cannot send: connection is closed")
        
        try:
            await self.ws.send(message)
        except Exception as e:
            # Mark socket as closed on any error
            self._socket_open = False
            raise

    async def close(self, code: int = 1000, reason: str = '') -> None:
        """Close the websocket connection."""
        if self._closed:
            return
            
        self._closed = True
        logger.debug(f'Disposing connection: code={code} reason={reason}')
        
        try:
            # Only try to close if socket appears to be open
            if self._socket_open:
                await self.ws.close(code=code, reason=reason)
        except Exception as e:
            logger.warning(f"Error closing websocket: {e}")
        finally:
            self._socket_open = False
            
            # Trigger onclose callback if it exists
            if self.onclose:
                try:
                    await self.onclose()
                except Exception as e:
                    logger.error(f"Error in onclose callback: {e}")

    async def recv(self) -> Data:
        """Receive data from the websocket.
        
        This is a blocking call that waits for data or a connection close.
        """
        if not self._socket_open:
            raise ConnectionError("Cannot receive: connection is closed")
            
        try:
            data = await self.ws.recv()
            
            # Handle message through callback if it exists
            if data and self.onmessage:
                # Use create_task to avoid blocking the receive loop
                self.loop.create_task(self._handle_message(data))
                
            return data
        except Exception as e:
            # Mark socket as closed on any error
            self._socket_open = False
            raise
    
    async def _handle_message(self, data):
        """Process message through the onmessage callback safely."""
        try:
            if self.onmessage:
                await self.onmessage(data)
        except Exception as e:
            logger.error(f"Error in onmessage callback: {e}")
