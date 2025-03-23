#!/usr/bin/env python3
"""
Comprehensive connection test that exercises various aspects of the connection code.
This focuses specifically on testing the connection handling with our fix.
"""
import asyncio
import logging
import os
import subprocess
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# WebSocket URL
WEBSOCKET_URL = "ws://127.0.0.1:3000"

class ConnectionTestSuite(unittest.TestCase):
    """Test suite for connection-related functionality."""
    
    async def setUp(self):
        """Set up the test environment."""
        from pyppeteer.websocket_transport import WebsocketTransport
        from pyppeteer.connection import Connection
        
        # Connect to the real WebSocket
        logger.info(f"Connecting to WebSocket: {WEBSOCKET_URL}")
        self.transport = await WebsocketTransport.create(WEBSOCKET_URL)
        self.connection = Connection(WEBSOCKET_URL, self.transport)
        logger.info("Connection established")
    
    async def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'connection'):
            try:
                await self.connection.dispose()
                logger.info("Connection disposed")
            except Exception as e:
                logger.warning(f"Error during connection disposal: {e}")
    
    async def test_1_basic_connection(self):
        """Test basic connection functionality."""
        # The connection should be established during setUp
        self.assertIsNotNone(self.connection)
        self.assertTrue(self.connection._connected)
        
        # Try sending a message (might fail, but shouldn't crash)
        logger.info("Sending test message")
        future = self.connection.send('Echo', {'message': 'hello'})
        
        try:
            result = await asyncio.wait_for(future, timeout=2.0)
            logger.info(f"Got response: {result}")
        except Exception as e:
            logger.info(f"Got expected error (or timeout): {e}")
        
        # Connection should still be active
        self.assertTrue(self.connection._connected)
        logger.info("Basic connection test passed")
    
    async def test_2_connection_close(self):
        """Test connection closure handling."""
        # First check connection is active
        self.assertTrue(self.connection._connected)
        
        # Close the connection
        logger.info("Closing connection")
        await self.connection.dispose()
        
        # Verify connection state
        self.assertFalse(self.connection._connected)
        self.assertTrue(self.connection._closed)
        
        # Try sending a message after closing (should fail)
        logger.info("Sending message after connection closed")
        with self.assertRaises(Exception):
            future = self.connection.send('Echo', {'message': 'hello'})
            await asyncio.wait_for(future, timeout=1.0)
        
        logger.info("Connection close test passed")
    
    async def test_3_connection_error_handling(self):
        """Test connection error handling."""
        # Create a future to monitor CPU usage
        cpu_monitor_future = asyncio.ensure_future(self._monitor_cpu())
        
        try:
            # Close the transport abruptly to simulate a connection error
            logger.info("Simulating connection error")
            await self.transport.close(1001, "Connection error test")
            
            # Wait a bit for connection to process the closure
            await asyncio.sleep(0.5)
            
            # Verify connection state
            self.assertFalse(self.connection._connected)
            
            # Try sending a message after error (should fail)
            logger.info("Sending message after connection error")
            with self.assertRaises(Exception):
                future = self.connection.send('Echo', {'message': 'hello'})
                await asyncio.wait_for(future, timeout=1.0)
            
            # Wait for a bit to see if any CPU issues occur
            logger.info("Waiting to see if CPU spikes...")
            await asyncio.sleep(3)
            
            # Check CPU usage
            high_cpu = await cpu_monitor_future
            self.assertFalse(high_cpu, "High CPU detected after connection error")
            
            logger.info("Connection error handling test passed")
        finally:
            # Cancel CPU monitoring
            if not cpu_monitor_future.done():
                cpu_monitor_future.cancel()
    
    async def _monitor_cpu(self, threshold=80, duration=5):
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
            except Exception as e:
                logger.error(f"Error checking CPU: {e}")
            
            await asyncio.sleep(0.5)
        
        # Calculate average
        if readings:
            avg_cpu = sum(readings) / len(readings)
            logger.info(f"Average CPU: {avg_cpu:.1f}%")
        
        return False

async def run_tests():
    """Run all tests in the suite."""
    logger.info("Running comprehensive connection tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    test_cases = [
        ConnectionTestSuite('test_1_basic_connection'),
        ConnectionTestSuite('test_2_connection_close'),
        ConnectionTestSuite('test_3_connection_error_handling')
    ]
    
    for test in test_cases:
        suite.addTest(test)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Override the run method to handle async tests
    original_run = runner.run
    
    async def run_async_tests(test_suite):
        for test_case in test_suite:
            await test_case.setUp()
            try:
                test_method = getattr(test_case, test_case._testMethodName)
                await test_method()
                test_case._outcome.success = True
            except Exception as e:
                logger.error(f"Test failed: {e}")
                test_case._outcome.success = False
            finally:
                await test_case.tearDown()
        
        # Return True if all tests passed
        return all(getattr(test_case, '_outcome', None) and 
                  getattr(test_case._outcome, 'success', False) 
                  for test_case in test_suite)
    
    # Run the tests
    success = await run_async_tests(suite)
    
    return success

def main():
    """Main entry point."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        success = loop.run_until_complete(run_tests())
        
        if success:
            logger.info("All tests PASSED!")
            return 0
        else:
            logger.error("Some tests FAILED!")
            return 1
    finally:
        loop.close()

if __name__ == "__main__":
    sys.exit(main())