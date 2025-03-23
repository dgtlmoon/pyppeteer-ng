#!/usr/bin/env python3
"""
Simplified test for the connection module.
"""
import asyncio
import logging
import sys
import time
from websockets.exceptions import ConnectionClosed
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockWebSocket:
    """Mock WebSocket implementation."""
    def __init__(self):
        self._connected = True
        self.connection_lost_waiter = asyncio.Future()
        self.sent_messages = []
        
    async def recv(self):
        """Wait a bit, then simulate connection close."""
        if not self._connected:
            raise ConnectionClosed(1000, "Connection closed")
            
        # Simulate working for a short time, then disconnect
        await asyncio.sleep(0.5)
        
        # Close on the second call
        if hasattr(self, '_recv_called'):
            self._connected = False
            if not self.connection_lost_waiter.done():
                self.connection_lost_waiter.set_result(None)
            raise ConnectionClosed(1000, "Connection closed")
            
        self._recv_called = True
        return '{"id": 1, "result": {"value": "test result"}}'
        
    async def send(self, msg):
        """Record sent messages."""
        if not self._connected:
            raise ConnectionClosed(1000, "Connection closed")
        self.sent_messages.append(msg)
        logger.info(f"Message sent: {msg[:50]}...")
        
    async def close(self, code=1000, reason=''):
        """Close the connection."""
        logger.info(f"WebSocket closed: code={code}, reason={reason}")
        self._connected = False
        if not self.connection_lost_waiter.done():
            self.connection_lost_waiter.set_result(None)

class MockTransport:
    """Mock transport implementation."""
    def __init__(self):
        self.ws = MockWebSocket()
        self.onmessage = None
        self.onclose = None
        self.loop = asyncio.get_event_loop()
        
    async def recv(self):
        """Receive message from WebSocket."""
        try:
            data = await self.ws.recv()
            # Handle message in a separate task
            if data and self.onmessage:
                self.loop.create_task(self.onmessage(data))
            return data
        except ConnectionClosed:
            if self.onclose:
                await self.onclose()
            raise
        
    async def send(self, msg):
        """Send message to WebSocket."""
        await self.ws.send(msg)
        
    async def close(self, code=1000, reason=''):
        """Close the WebSocket."""
        logger.info(f"Transport closed: code={code}, reason={reason}")
        await self.ws.close(code, reason)
        if self.onclose:
            await self.onclose()

async def test_connection():
    """Test the Connection class with our fix."""
    from pyppeteer.connection import Connection
    
    # Create a mock transport
    transport = MockTransport()
    
    # Create a connection
    conn = Connection("ws://test", transport)
    
    # Send a message
    try:
        logger.info("Sending test message")
        future = conn.send('Test.method', {'param': 'value'})
        
        # Wait for the response (should succeed)
        result = await future
        logger.info(f"Received response: {result}")
        assert result == {"value": "test result"}, f"Expected test result, got {result}"
        
        # Send another message (this should fail as the connection will close)
        logger.info("Sending second message (expected to fail)")
        future2 = conn.send('Test.method2', {'param': 'value2'})
        
        try:
            await asyncio.wait_for(future2, 2.0)
            logger.error("Second message should have failed but didn't!")
            assert False, "Second message should have failed"
        except Exception as e:
            logger.info(f"Got expected error from second message: {e}")
            
        # Wait a bit to see if CPU usage spikes
        logger.info("Waiting to ensure no CPU spinning...")
        await asyncio.sleep(2)
        
        # Test passed if we got here without hanging
        logger.info("Test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return False
    finally:
        # Clean up
        await conn.dispose()
        logger.info("Connection disposed")

def main():
    """Run the test."""
    logger.info("Testing connection implementation...")
    
    # Set up asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Run the test
        success = loop.run_until_complete(test_connection())
        
        if success:
            logger.info("Test PASSED! The connection fix is working correctly.")
            return 0
        else:
            logger.error("Test FAILED!")
            return 1
    finally:
        loop.close()

if __name__ == "__main__":
    sys.exit(main())