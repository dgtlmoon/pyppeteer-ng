#!/usr/bin/env python3
"""
Final connection test that focuses on our specific fix.
This test verifies that CPU doesn't spike when connections close or fail.
"""
import asyncio
import logging
import os
import subprocess
import sys
import time
import websockets

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# WebSocket URL
WEBSOCKET_URL = "ws://127.0.0.1:3000"

class ConnectionFixTest:
    """Test class for connection fix verification."""
    
    async def test_real_connection(self):
        """Test with a real WebSocket connection."""
        from pyppeteer.connection import Connection
        from pyppeteer.websocket_transport import WebsocketTransport
        
        logger.info(f"Connecting to real WebSocket at {WEBSOCKET_URL}...")
        try:
            # Connect to the real WebSocket
            transport = await WebsocketTransport.create(WEBSOCKET_URL)
            logger.info("Successfully connected!")
            
            # Create connection
            conn = Connection(WEBSOCKET_URL, transport)
            logger.info("Connection established")
            
            # Send a message (will likely fail but that's fine)
            logger.info("Sending test message...")
            future = conn.send('Test.method', {'param': 'value'})
            
            try:
                await asyncio.wait_for(future, timeout=1.0)
            except asyncio.TimeoutError:
                logger.info("Message timed out (expected)")
            except Exception as e:
                logger.info(f"Message failed with error: {e}")
            
            # Close the connection
            logger.info("Closing connection...")
            await conn.dispose()
            logger.info("Connection closed successfully")
            
            # Verify CPU doesn't spike after closing
            logger.info("Monitoring CPU after connection close...")
            high_cpu = await self._monitor_cpu()
            
            if high_cpu:
                logger.error("High CPU detected after close!")
                return False
            else:
                logger.info("No high CPU detected after close")
                return True
                
        except Exception as e:
            logger.error(f"Test failed: {e}")
            return False
    
    async def test_connection_error(self):
        """Test connection behavior with connection errors."""
        from pyppeteer.connection import Connection
        from pyppeteer.websocket_transport import WebsocketTransport
        
        logger.info("Testing connection with errors...")
        
        # Create a mock WebSocket that fails immediately
        class FailingTransport:
            def __init__(self):
                self.ws = None
                self.onmessage = None
                self.onclose = None
            
            async def recv(self):
                raise websockets.ConnectionClosed(None, None)
                
            async def send(self, msg):
                raise websockets.ConnectionClosed(None, None)
                
            async def close(self, code=1000, reason=''):
                if self.onclose:
                    await self.onclose()
        
        # Create connection with failing transport
        transport = FailingTransport()
        conn = Connection("ws://dummy", transport)
        
        try:
            # Try to send a message (will fail)
            logger.info("Sending message to failing connection...")
            future = conn.send('Test.method', {'param': 'value'})
            
            try:
                await asyncio.wait_for(future, timeout=1.0)
                logger.error("Unexpected success with failing connection!")
                return False
            except Exception as e:
                logger.info(f"Got expected error: {e}")
            
            # Verify CPU doesn't spike after error
            logger.info("Monitoring CPU after connection error...")
            high_cpu = await self._monitor_cpu()
            
            if high_cpu:
                logger.error("High CPU detected after error!")
                return False
            else:
                logger.info("No high CPU detected after error")
                return True
                
        finally:
            # Clean up
            await conn.dispose()
    
    async def _monitor_cpu(self, duration=5, threshold=80):
        """Monitor CPU usage and return True if high CPU is detected."""
        pid = os.getpid()
        start_time = time.time()
        readings = []
        
        while time.time() - start_time < duration:
            try:
                cmd = f"ps -p {pid} -o %cpu | tail -n 1"
                result = subprocess.check_output(cmd, shell=True).decode().strip()
                cpu = float(result)
                readings.append(cpu)
                logger.info(f"CPU usage: {cpu}%")
                
                if cpu > threshold:
                    logger.error(f"High CPU detected: {cpu}%")
                    return True
                
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error checking CPU: {e}")
        
        # Calculate average
        if readings:
            avg_cpu = sum(readings) / len(readings)
            logger.info(f"Average CPU: {avg_cpu:.1f}%")
        
        return False

async def run_tests():
    """Run all tests."""
    logger.info("Running final connection fix tests...")
    
    test = ConnectionFixTest()
    success = True
    
    # Test with real connection
    logger.info("\n=== TEST 1: Real Connection Test ===")
    if not await test.test_real_connection():
        success = False
    
    # Test with connection errors
    logger.info("\n=== TEST 2: Connection Error Test ===")
    if not await test.test_connection_error():
        success = False
    
    return success

def main():
    """Main entry point."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        success = loop.run_until_complete(run_tests())
        
        if success:
            logger.info("\n✅ ALL TESTS PASSED! Connection fix is working correctly.")
            return 0
        else:
            logger.error("\n❌ SOME TESTS FAILED! Connection fix may have issues.")
            return 1
    finally:
        loop.close()

if __name__ == "__main__":
    sys.exit(main())