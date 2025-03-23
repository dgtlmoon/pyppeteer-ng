#!/usr/bin/env python3
"""
Simple connection test that focuses on our fix for high CPU usage.
This directly tests the WebSocket transport and Connection classes.
"""
import asyncio
import logging
import os
import subprocess
import sys
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# WebSocket URL
WEBSOCKET_URL = "ws://127.0.0.1:3000"

async def test_connection_and_cpu():
    """Test connection with real WebSocket and monitor CPU after disconnection."""
    from pyppeteer.websocket_transport import WebsocketTransport
    from pyppeteer.connection import Connection
    
    # Connect to the real WebSocket
    logger.info(f"Connecting to WebSocket: {WEBSOCKET_URL}")
    try:
        transport = await WebsocketTransport.create(WEBSOCKET_URL)
        logger.info("Successfully connected to WebSocket!")
        
        # Create connection
        conn = Connection(WEBSOCKET_URL, transport)
        
        # Get process ID for CPU monitoring
        pid = os.getpid()
        
        try:
            # Send a test message (may fail but shouldn't cause high CPU)
            logger.info("Sending test message")
            future = conn.send('Test.method', {'param': 'value'})
            
            try:
                # Wait for response with timeout
                result = await asyncio.wait_for(future, timeout=1.0)
                logger.info(f"Received response: {result}")
            except asyncio.TimeoutError:
                logger.info("Timeout waiting for response (expected)")
            except Exception as e:
                logger.info(f"Error from message: {e}")
                
            # Test 1: Normal Connection
            logger.info("TEST 1: CPU usage during normal connection")
            cpu_normal = await monitor_cpu(pid, 3)
            logger.info(f"CPU during normal connection: max={cpu_normal['max']:.1f}%, " 
                         f"avg={cpu_normal['avg']:.1f}%")
                
            # Test 2: Simulate abrupt disconnection
            logger.info("TEST 2: Simulating abrupt disconnection")
            try:
                await transport.ws.close(1001, "Test disconnection")
                logger.info("WebSocket closed successfully")
            except Exception as e:
                logger.info(f"Error closing WebSocket (expected): {e}")
                
            # Wait a moment for disconnection to be processed
            await asyncio.sleep(0.5)
                
            # Try to send another message after disconnection
            logger.info("Sending message after disconnection")
            try:
                future2 = conn.send('Test.another', {'param': 'value2'})
                result2 = await asyncio.wait_for(future2, timeout=1.0)
                logger.info(f"Unexpected success after disconnection: {result2}")
                return False
            except Exception as e:
                logger.info(f"Got expected error after disconnection: {e}")
                
            # Test 3: Monitor CPU after disconnection
            logger.info("TEST 3: CPU usage after disconnection")
            cpu_after = await monitor_cpu(pid, 5)
            logger.info(f"CPU after disconnection: max={cpu_after['max']:.1f}%, " 
                         f"avg={cpu_after['avg']:.1f}%")
                
            # Success criteria: CPU after disconnection should not be high
            success = cpu_after['max'] < 80.0 and cpu_after['avg'] < 40.0
            
            if success:
                logger.info("SUCCESS: CPU usage after disconnection is normal!")
                return True
            else:
                logger.error("FAILURE: High CPU detected after disconnection!")
                return False
                
        finally:
            # Clean up
            try:
                logger.info("Disposing connection")
                await conn.dispose()
            except Exception as e:
                logger.info(f"Error during disposal (expected): {e}")
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False

async def monitor_cpu(pid, duration=5):
    """Monitor CPU usage and return statistics."""
    start_time = time.time()
    readings = []
    
    while time.time() - start_time < duration:
        try:
            # Get CPU usage
            cmd = f"ps -p {pid} -o %cpu | tail -n 1"
            result = subprocess.check_output(cmd, shell=True).decode().strip()
            cpu = float(result)
            readings.append(cpu)
            logger.info(f"CPU usage: {cpu}%")
            
            # Check every 0.5 seconds
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error checking CPU: {e}")
    
    # Calculate statistics
    if not readings:
        return {'max': 0, 'min': 0, 'avg': 0}
        
    return {
        'max': max(readings),
        'min': min(readings),
        'avg': sum(readings) / len(readings)
    }

async def main():
    """Run all tests."""
    logger.info("Starting connection tests with real WebSocket...")
    
    # Run the test and get result
    success = await test_connection_and_cpu()
    
    if success:
        logger.info("ALL TESTS PASSED! The connection fix is working correctly.")
        return 0
    else:
        logger.error("TESTS FAILED! Connection fix may not be working correctly.")
        return 1

if __name__ == "__main__":
    # Run the tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        exit_code = loop.run_until_complete(main())
        sys.exit(exit_code)
    finally:
        loop.close()