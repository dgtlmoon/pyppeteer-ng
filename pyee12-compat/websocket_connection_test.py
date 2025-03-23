#!/usr/bin/env python3
"""
Test for the connection code using a real WebSocket connection.
This test focuses on how our code handles WebSocket disconnection.
"""
import asyncio
import logging
import sys
import time
import os
import signal
import websockets
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# WebSocket URL to connect to
WEBSOCKET_URL = "ws://127.0.0.1:3000"

class ConnectionTest:
    """Test for the connection module using real WebSockets."""
    
    def __init__(self):
        """Initialize the test."""
        self.server = None
        self.client = None
        self.server_task = None
    
    async def setup_echo_server(self):
        """Set up a simple echo WebSocket server for testing."""
        # Create an echo handler for WebSocket connections
        async def echo_handler(websocket, path):
            logger.info(f"Server: Client connected from {websocket.remote_address}")
            try:
                async for message in websocket:
                    logger.info(f"Server: Received message: {message[:50]}...")
                    # Parse the message and respond with an echo
                    try:
                        data = json.loads(message)
                        response = {
                            "id": data.get("id", 0),
                            "result": {
                                "echo": data.get("params", {}),
                                "timestamp": datetime.now().isoformat()
                            }
                        }
                        await websocket.send(json.dumps(response))
                    except json.JSONDecodeError:
                        # Just echo non-JSON messages
                        await websocket.send(message)
            except websockets.ConnectionClosed:
                logger.info("Server: Client disconnected")
        
        # Start the server
        port = 3456  # Use a different port than the provided one
        self.server = await websockets.serve(echo_handler, "localhost", port)
        logger.info(f"Echo server started on ws://localhost:{port}")
        return f"ws://localhost:{port}"
    
    async def test_with_real_connection(self):
        """Test the connection with a real WebSocket."""
        from pyppeteer.connection import Connection
        from pyppeteer.websocket_transport import WebsocketTransport
        
        # Either use the provided URL or start our own echo server
        use_own_server = False
        websocket_url = WEBSOCKET_URL
        
        if use_own_server:
            websocket_url = await self.setup_echo_server()
        
        # Connect to the WebSocket
        logger.info(f"Connecting to WebSocket at {websocket_url}...")
        try:
            transport = await WebsocketTransport.create(websocket_url)
            logger.info("Successfully connected to WebSocket!")
            
            # Create connection
            conn = Connection(websocket_url, transport)
            
            # Send a test message
            logger.info("Sending test message...")
            future = conn.send('Test.echo', {'message': 'Hello, WebSocket!'})
            
            try:
                # Wait for the response
                result = await asyncio.wait_for(future, timeout=3.0)
                logger.info(f"Received response: {result}")
                
                # Now deliberately close the connection
                logger.info("Simulating connection closure...")
                await transport.close(1000, "Test closing connection")
                
                # Try to send another message after closing
                logger.info("Sending message after connection closed...")
                try:
                    future2 = conn.send('Test.echo', {'message': 'This should fail'})
                    result2 = await asyncio.wait_for(future2, timeout=1.0)
                    logger.error(f"Unexpected success after connection closed: {result2}")
                    return False
                except Exception as e:
                    logger.info(f"Got expected error after connection closed: {e}")
                
                # Monitor CPU usage after disconnection
                logger.info("Monitoring CPU usage after disconnection...")
                pid = os.getpid()
                start_time = time.time()
                high_cpu_detected = False
                
                while time.time() - start_time < 5:  # Monitor for 5 seconds
                    # Check CPU usage
                    try:
                        cmd = f"ps -p {pid} -o %cpu | tail -n 1"
                        result = subprocess.check_output(cmd, shell=True).decode().strip()
                        cpu = float(result)
                        logger.info(f"CPU usage: {cpu}%")
                        
                        if cpu > 80:  # Consider high CPU
                            logger.error(f"High CPU detected: {cpu}%")
                            high_cpu_detected = True
                            break
                    except Exception as e:
                        logger.error(f"Error checking CPU: {e}")
                    
                    await asyncio.sleep(0.5)
                
                if high_cpu_detected:
                    logger.error("Test FAILED: High CPU detected after connection closed")
                    return False
                else:
                    logger.info("Test PASSED: No high CPU detected after connection closed")
                    return True
                    
            except Exception as e:
                logger.error(f"Error during test: {e}")
                return False
            finally:
                # Clean up
                try:
                    await conn.dispose()
                except Exception:
                    pass  # Expected to fail if already closed
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            return False
    
    async def cleanup(self):
        """Clean up any resources."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Echo server stopped")

async def main():
    """Run the connection tests."""
    logger.info("Testing connection with real WebSocket...")
    
    test = ConnectionTest()
    try:
        success = await test.test_with_real_connection()
        
        if success:
            logger.info("All tests PASSED! Connection fix is working correctly.")
            return 0
        else:
            logger.error("Tests FAILED!")
            return 1
    finally:
        await test.cleanup()

if __name__ == "__main__":
    # Import subprocess here to avoid circular imports
    import subprocess
    
    # Run the tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        exit_code = loop.run_until_complete(main())
        sys.exit(exit_code)
    finally:
        loop.close()