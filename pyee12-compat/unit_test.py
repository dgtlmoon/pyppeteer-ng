#!/usr/bin/env python3
"""
Unit tests for the connection module.
"""
import asyncio
import logging
import unittest
import time
import websockets
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unit_test")

# Import the patched connection code
from pyppeteer.connection import Connection
from pyppeteer.websocket_transport import WebsocketTransport
from websockets.exceptions import ConnectionClosed

class MockWebSocketProtocol:
    """Mock WebSocket implementation for testing."""
    def __init__(self):
        self.connection_lost_waiter = asyncio.Future()
        self._closed = False
        self.sent_messages = []
        self.close_code = None
        self.close_reason = None
        
    async def recv(self):
        """Simulate receiving a message."""
        if self._closed:
            raise ConnectionClosed(None, None)
        
        # First return a message, then simulate connection close on next call
        self._closed = True
        self.connection_lost_waiter.set_result(None)
        return '{"id": 1, "result": {"value": "test"}}'
    
    async def send(self, message):
        """Record sent messages."""
        if self._closed:
            raise ConnectionClosed(None, None)
        self.sent_messages.append(message)
        
    async def close(self, code=1000, reason=""):
        """Record close parameters."""
        self._closed = True
        self.close_code = code
        self.close_reason = reason
        if not self.connection_lost_waiter.done():
            self.connection_lost_waiter.set_result(None)

class TestConnection(unittest.TestCase):
    """Test the Connection class."""
    
    async def test_send_receive(self):
        """Test sending and receiving messages."""
        # Create a mock WebSocket
        mock_ws = MockWebSocketProtocol()
        
        # Create a transport with the mock
        transport = WebsocketTransport(mock_ws)
        
        # Create a connection
        connection = Connection("ws://test", transport)
        
        # Send a message
        future = connection.send("Test.method", {"param": "value"})
        
        # Wait for the response
        try:
            result = await asyncio.wait_for(future, timeout=1.0)
            self.assertEqual(result, {"value": "test"})
            
            # Verify the message was sent correctly
            self.assertEqual(len(mock_ws.sent_messages), 1)
            self.assertIn("Test.method", mock_ws.sent_messages[0])
            self.assertIn("param", mock_ws.sent_messages[0])
            self.assertIn("value", mock_ws.sent_messages[0])
            
        except Exception as e:
            self.fail(f"Sending message failed: {e}")
        
        # Close the connection
        await connection.dispose()
        
        # Verify the websocket was closed
        self.assertIsNotNone(mock_ws.close_code)
        self.assertTrue(mock_ws._closed)
    
    async def test_connection_close(self):
        """Test behavior when connection closes unexpectedly."""
        # Create a mock WebSocket that will close immediately
        mock_ws = MockWebSocketProtocol()
        mock_ws._closed = True  # Pre-mark as closed
        
        # Create a transport with the mock
        transport = WebsocketTransport(mock_ws)
        
        # Create a connection
        connection = Connection("ws://test", transport)
        
        # Send a message that should fail
        future = connection.send("Test.method", {"param": "value"})
        
        # Wait a bit for the connection to handle the closed websocket
        await asyncio.sleep(0.5)
        
        # Verify the future was rejected correctly
        with self.assertRaises(Exception):
            await future
            
        # Clean up
        await connection.dispose()
        
        # Verify the connection is marked as closed
        self.assertTrue(connection._closed)
    
    async def test_cpu_usage(self):
        """Test CPU usage when connection closes."""
        # Create a mock WebSocket
        mock_ws = MockWebSocketProtocol()
        
        # Create a transport with the mock
        transport = WebsocketTransport(mock_ws)
        
        # Create a connection
        connection = Connection("ws://test", transport)
        
        # Send a message
        future = connection.send("Test.method", {"param": "value"})
        
        # Close the connection abruptly
        mock_ws._closed = True
        mock_ws.connection_lost_waiter.set_result(None)
        
        # Wait a bit for any high CPU loops to manifest
        start_time = time.time()
        await asyncio.sleep(1.0)
        
        # Clean up
        try:
            await connection.dispose()
        except Exception:
            pass  # Expected
        
        # If we got here without freezing or high CPU, the test passed
        end_time = time.time()
        logger.info(f"Test completed in {end_time - start_time:.2f} seconds")
        # We'll assert the test didn't take too long (which would suggest CPU spinning)
        self.assertLess(end_time - start_time, 2.0)

def run_tests():
    """Run the unit tests."""
    logger.info("Running connection unit tests...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Create and run the test cases
    test_cases = [
        TestConnection("test_send_receive"),
        TestConnection("test_connection_close"),
        TestConnection("test_cpu_usage")
    ]
    
    suite = unittest.TestSuite()
    for test in test_cases:
        suite.addTest(test)
    
    # Create a test runner that adapts the async tests
    class AsyncTestRunner(unittest.TextTestRunner):
        def run(self, test):
            """Run async test cases."""
            # Override the run method to run async test methods
            for test_case in test:
                test_method = getattr(test_case, test_case._testMethodName)
                loop.run_until_complete(test_method())
            return super().run(test)
    
    # Run the tests
    runner = AsyncTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Clean up
    loop.close()
    
    # Return success status
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)