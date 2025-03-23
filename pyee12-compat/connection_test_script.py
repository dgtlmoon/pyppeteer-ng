
import asyncio
import time
import sys
from pyppeteer.connection import Connection
from pyppeteer.websocket_transport import WebsocketTransport
from websockets.exceptions import ConnectionClosed

class MockTransport:
    def __init__(self):
        self.ws = None
        self.onmessage = None
        self.onclose = None
        self._connected = True
        
    async def recv(self):
        # Simulate connection working briefly then failing
        await asyncio.sleep(1)
        # Now simulate connection closing abruptly
        self._connected = False
        raise ConnectionClosed(None, None)
        
    async def send(self, msg):
        if not self._connected:
            raise ConnectionClosed(None, None)
        print(f"Message sent: {msg[:30]}...")
        
    async def close(self, code=1000, reason=''):
        print(f"Transport closed: {code} {reason}")

async def main():
    # Create a mock transport
    transport = MockTransport()
    
    # Create a connection using our implementation
    conn = Connection("ws://localhost:9222", transport)
    
    # Trigger some activity
    try:
        # This should not spin CPU after connection closes
        await asyncio.sleep(5)
        print("Connection test completed without issues")
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        await conn.dispose()
        print("Connection disposed")

# Run the test
asyncio.run(main())
