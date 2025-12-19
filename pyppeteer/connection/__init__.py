import asyncio
import json
import logging
import sys
from typing import Any, Awaitable, Dict

import websockets
from pyee.asyncio import AsyncIOEventEmitter

from pyppeteer.errors import NetworkError
from pyppeteer.events import Events
from pyppeteer.websocket_transport import WebsocketTransport

if sys.version_info < (3, 8):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_connection = logging.getLogger(__name__ + '.Connection')


class TargetInfo(TypedDict, total=False):
    type: str


class MessageParams(TypedDict, total=False):
    targetInfo: TargetInfo
    sessionId: str


class MessageError(TypedDict, total=False):
    message: str
    data: Any


class Message(TypedDict, total=False):
    method: str
    id: int
    params: MessageParams
    error: MessageError
    result: Any


class Connection(AsyncIOEventEmitter):
    """Connection management class."""

    def __init__(
        self, url: str, transport: WebsocketTransport, delay: float = 0, loop: asyncio.AbstractEventLoop = None,
    ) -> None:
        """Make connection.

        :arg str url: WebSocket url to connect devtool.
        :arg int delay: delay to wait before processing received messages.
        """
        super().__init__()
        self._url = url
        self._lastId = 0
        self._callbacks: Dict[int, asyncio.Future] = {}
        self._delay = delay / 1000

        self._transport = transport

        self.loop = loop or asyncio.get_event_loop()
        self._sessions: Dict[str, CDPSession] = {}
        self._connected = False
        self._closed = False
        self.loop.create_task(self._recv_loop())

    @staticmethod
    def fromSession(session: 'CDPSession') -> 'Connection':
        return session._connection

    def session(self, sessionId) -> 'CDPSession':
        return self._sessions.get(sessionId)

    @property
    def url(self) -> str:
        """Get connected WebSocket url."""
        return self._url

    async def _recv_loop(self) -> None:
        """Process incoming WebSocket messages in an event-driven way."""
        # Flag to track if we initiated a clean shutdown
        clean_shutdown = False
        
        try:
            self._connected = True
            self.connection = self._transport
            
            # Set up callbacks
            self.connection.onmessage = self._process_message
            self.connection.onclose = self._onClose
            
            # Process messages directly from the WebSocket until connection is closed
            # We let the websocket's own event mechanism drive message processing
            # instead of polling in a tight loop
            while self._connected:
                try:
                    # This is a blocking call that waits for the next message
                    # Only returns when a message is received or connection closes
                    message = await self.connection.ws.recv()
                    
                    # Process message if we got actual data and are still connected
                    if message and self._connected:
                        await self._onMessage(message)
                        
                except (websockets.ConnectionClosed, ConnectionResetError) as excpt:
                    logger.warning(f'Transport connection closed: {excpt}')
                    self._connected = False
                    break
                except AttributeError as excpt:
                    # Handle case where ws attribute might be None after disposal
                    if "'NoneType' object has no attribute 'recv'" in str(excpt):
                        logger.warning("Connection already closed (websocket is None)")
                        self._connected = False
                        break
                    else:
                        # Re-raise other attribute errors
                        raise
        
        except asyncio.CancelledError:
            # Handle task cancellation gracefully
            logger.debug("Connection receive loop cancelled")
            clean_shutdown = True
            self._connected = False
            raise
            
        except Exception as excpt:
            # Handle unexpected errors
            logger.error(f"Error in connection receive loop: {excpt}")
            if self._connected and not self._closed:
                self._connected = False
                await self.dispose(reason=str(excpt))
            # Don't re-raise the exception to avoid unhandled exceptions
            # in background tasks - just exit the loop by returning
            return
            
        finally:
            # Only run disposal if we didn't already start it and it wasn't
            # a clean shutdown via cancellation
            if not clean_shutdown and self._connected and not self._closed:
                self._connected = False
                await self.dispose(reason="Connection closed")

    async def _async_send(self, msg: Message) -> None:
        # Set a reasonable timeout for waiting for connection
        max_retries = 50  # 0.5 seconds max wait
        retries = 0
        
        while not self._connected and retries < max_retries:
            await asyncio.sleep(0.01)  # Use a short but non-zero sleep
            retries += 1
            
        # If not connected after maximum wait, fail rather than continuing
        if not self._connected:
            logger.error('Failed to send message: connection not established')
            callback = self._callbacks.get(msg['id'], None)
            if callback and not callback.done():
                callback.set_exception(ConnectionError('Connection not established'))
            return
            
        try:
            remove_none_items_inplace(msg)
            msg_to_send = json.dumps(msg)
            await self.connection.send(msg_to_send)
            logger_connection.debug('SEND ▶ %s', msg_to_send)
        except (websockets.ConnectionClosed, ConnectionResetError) as e:
            logger.error(f'Connection unexpectedly closed during send: {e}')
            # Mark as disconnected immediately to stop other operations
            self._connected = False
            callback = self._callbacks.get(msg['id'], None)
            if callback and not callback.done():
                callback.set_exception(ConnectionError(f'Connection closed during send: {e}'))
            # Only dispose if not already disposing
            if not self._closed:
                await self.dispose(reason=f"Connection closed during send: {e}")

    def send(self, method: str, params: dict = None) -> Awaitable:
        """Send message via the connection."""
        # Detect connection availability from the second transmission
        if self._lastId and not self._connected:
            raise ConnectionError('Connection is closed')
        id_ = self._rawSend({'method': method, 'params': params or {}})
        callback = self.loop.create_future()
        callback.error: Exception = NetworkError()  # type: ignore
        callback.method: str = method  # type: ignore
        self._callbacks[id_] = callback
        return callback

    def _rawSend(self, message: Message) -> int:
        self._lastId += 1
        id_ = self._lastId
        message['id'] = id_
        self.loop.create_task(self._async_send(message))
        return id_

    async def _process_message(self, msg: str) -> None:
        """Callback for handling messages from the websocket transport.
        This method is called by the transport when a message is received."""
        # Create a task to process the message asynchronously to avoid blocking the transport
        self.loop.create_task(self._onMessage(msg))
        
    async def _onMessage(self, msg: str) -> None:
        """Process a received message and dispatch it to the appropriate handler."""
        try:
            # Check connection state before processing
            if not self._connected or self._closed:
                logger_connection.debug(f'Ignoring message received after connection closed: {msg[:100]}...')
                return
                
            loaded_msg: Message = json.loads(msg)
            if self._delay:
                await asyncio.sleep(self._delay)
            logger_connection.debug('◀ RECV %s', loaded_msg)
    
            # Handle Target attach/detach methods
            if loaded_msg.get('method') == 'Target.attachedToTarget':
                sessionId = loaded_msg['params']['sessionId']
                self._sessions[sessionId] = CDPSession(
                    connection=self,
                    targetType=loaded_msg['params']['targetInfo']['type'],
                    sessionId=sessionId,
                    loop=self.loop,
                )
            elif loaded_msg.get('method') == 'Target.detachedFromTarget':
                session = self._sessions.get(loaded_msg['params']['sessionId'])
                if session:
                    session._onClosed()
                    del self._sessions[loaded_msg['params']['sessionId']]
    
            if loaded_msg.get('sessionId'):
                session = self._sessions.get(loaded_msg['sessionId'])
                if session:
                    session._onMessage(loaded_msg)
            elif loaded_msg.get('id'):
                # Callbacks could be all rejected if someone has called `.dispose()`
                callback = self._callbacks.get(loaded_msg['id'])
                if callback:
                    if loaded_msg.get('error'):
                        callback.set_exception(createProtocolError(callback.error, callback.method, loaded_msg))
                    else:
                        callback.set_result(loaded_msg.get('result'))
                    del self._callbacks[loaded_msg['id']]
            else:
                self.emit(loaded_msg['method'], loaded_msg['params'])
        except Exception as e:
            # Never crash the message handler
            logger.error(f"Error processing message: {e}")
            # If we hit a JSON parsing error or other issue,
            # it might indicate a corrupted connection
            if not self._closed:
                # Schedule connection disposal on a new task to avoid blocking current flow
                self.loop.create_task(self.dispose(reason=f"Error processing message: {e}"))

    async def _onClose(self) -> None:
        # Use atomic state change to prevent race conditions
        if self._closed:
            return
            
        # Mark as closed immediately to prevent duplicate cleanups
        self._closed = True
        self._connected = False
        
        # Clear event handlers first to prevent callbacks during cleanup
        if hasattr(self, '_transport') and self._transport:
            self._transport.onmessage = None
            self._transport.onclose = None

        # Handle any pending callbacks
        callbacks_to_complete = list(self._callbacks.values())
        self._callbacks.clear()
        for cb in callbacks_to_complete:
            if not cb.done():
                try:
                    cb.set_exception(
                        rewriteError(
                            cb.error,  # type: ignore
                            f'Protocol error {cb.method}: Target closed.',  # type: ignore
                        )
                    )
                except Exception:
                    # Ignore any issues with callback resolution
                    pass

        # Close all sessions
        sessions_to_close = list(self._sessions.values())
        self._sessions.clear()
        for session in sessions_to_close:
            try:
                session._onClosed()
            except Exception as e:
                logger.warning(f"Error closing session: {e}")

        # Close the connection
        if hasattr(self, 'connection') and self.connection:
            try:
                await self.connection.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
                
        # Emit disconnection event
        try:
            self.emit(Events.Connection.Disconnected)
        except Exception as e:
            logger.warning(f"Error emitting disconnect event: {e}")

    async def dispose(self, code: int = 1000, reason: str = None) -> None:
        """Close all connection."""
        # Use atomic state changes to prevent race conditions
        if self._closed:
            # Already disposed, don't duplicate cleanup
            return
            
        # Mark as disconnected first
        self._connected = False
        
        try:
            # Close sessions and callbacks
            await self._onClose()
        except Exception as e:
            # Prevent any exception from stopping full cleanup
            logger.error(f"Error during connection cleanup: {e}")
            
        try:
            # Ensure transport is closed
            if hasattr(self, '_transport'):
                await self._transport.close(code=code, reason=str(reason))
        except Exception as e:
            # Log but don't propagate to allow clean shutdown
            logger.error(f"Error closing transport: {e}")

    async def createSession(self, targetInfo: Dict) -> 'CDPSession':
        """Create new session."""
        resp = await self.send('Target.attachToTarget', {'targetId': targetInfo['targetId'], 'flatten': True})
        sessionId = resp.get('sessionId')
        return self._sessions[sessionId]


def createProtocolError(error: Exception, method: str, obj: Dict) -> Exception:
    message = f'Protocol error ({method}): {obj["error"]["message"]}'
    if 'data' in obj['error']:
        message += f' {obj["error"]["data"]}'
    return rewriteError(error, message)


def rewriteError(error: Exception, message: str) -> Exception:
    error.args = (message,)
    return error


def remove_none_items_inplace(o: Dict[str, Any]) -> None:
    """
    Removes items that have a value of None. There are instances in puppeteer where a object (dict) is sent which has
    undefined values, which are then omitted from the resulting json. This function emulates such behaviour, removing
    all k:v pairs where v = None
    :param o:
    :return Dict[str, Any]: dict without any None values
    """
    none_keys = []
    for key, value in o.items():
        if isinstance(value, dict):
            remove_none_items_inplace(value)
        if value is None:
            none_keys.append(key)
    for key in none_keys:
        del o[key]


from pyppeteer.connection.cdpsession import CDPSession  # isort:skip
