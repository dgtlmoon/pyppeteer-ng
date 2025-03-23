#!/usr/bin/env python3
"""
Connection stability test that focuses specifically on our fix.
This tests how the connection handles errors, disconnections, and
bad responses from the real WebSocket.
"""
import asyncio
import logging
import os
import subprocess
import sys
import time
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# WebSocket URL
WEBSOCKET_URL = "ws://127.0.0.1:3000"

async def test_connection_stability():
    """Test connection stability with real WebSocket."""
    from pyppeteer.connection import Connection
    from pyppeteer.websocket_transport import WebsocketTransport
    
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
            # Test 1: Send multiple rapid requests
            logger.info("TEST 1: Sending multiple rapid requests")
            futures = []
            
            # Send 10 requests in quick succession
            for i in range(10):
                method = random.choice([
                    'Page.navigate', 'Runtime.evaluate', 'Network.enable', 
                    'DOM.getDocument', 'CSS.enable', 'Target.attachToTarget'
                ])
                params = {'id': i, 'value': f'test{i}'}
                future = conn.send(method, params)
                futures.append(future)
                
            # Wait for all requests to complete (most will error)
            for i, future in enumerate(futures):
                try:
                    result = await asyncio.wait_for(future, timeout=1.0)
                    logger.info(f"Request {i} completed: {result}")
                except asyncio.TimeoutError:
                    logger.info(f"Request {i} timed out (expected)")
                except Exception as e:
                    logger.info(f"Request {i} failed with error: {e}")
            
            # Monitor CPU during high activity
            logger.info("Monitoring CPU during high activity")
            cpu_active = await monitor_cpu(pid, 3)
            logger.info(f"CPU during high activity: max={cpu_active['max']:.1f}%, " 
                         f"avg={cpu_active['avg']:.1f}%")
            
            # Test 2: Send requests with random errors
            logger.info("TEST 2: Triggering random errors")
            for i in range(5):
                # These methods don't exist, will cause protocol errors
                method = f"Invalid.method{i}"
                params = {'random': random.random()}
                
                try:
                    future = conn.send(method, params)
                    result = await asyncio.wait_for(future, timeout=1.0)
                    logger.info(f"Unexpected success: {result}")
                except Exception as e:
                    logger.info(f"Got expected error: {e}")
            
            # Test 3: Close connection abruptly and monitor CPU
            logger.info("TEST 3: Closing connection abruptly")
            await transport.close(1001, "Test complete")
            
            # Monitor CPU after connection close
            logger.info("Monitoring CPU after connection close")
            cpu_after = await monitor_cpu(pid, 5)
            logger.info(f"CPU after close: max={cpu_after['max']:.1f}%, " 
                         f"avg={cpu_after['avg']:.1f}%")
            
            # Test 4: Try to use closed connection
            logger.info("TEST 4: Using closed connection")
            try:
                future = conn.send('Test.method', {'param': 'value'})
                result = await asyncio.wait_for(future, timeout=1.0)
                logger.info(f"Unexpected success after close: {result}")
                return False
            except Exception as e:
                logger.info(f"Got expected error after close: {e}")
            
            # Success criteria: CPU after disconnection should be low
            success = cpu_after['max'] < 50.0 and cpu_after['avg'] < 30.0
            
            if success:
                logger.info("SUCCESS: Connection fix is working correctly!")
                return True
            else:
                logger.error("FAILURE: High CPU detected after disconnection!")
                return False
                
        finally:
            # Clean up
            logger.info("Disposing connection")
            try:
                await conn.dispose()
            except Exception as e:
                logger.info(f"Error during disposal (expected): {e}")
                
    except Exception as e:
        logger.error(f"Connection failed: {e}")
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
    """Run the stability test."""
    logger.info("Starting connection stability test...")
    
    success = await test_connection_stability()
    
    if success:
        logger.info("ALL TESTS PASSED! Connection fix is stable and working correctly.")
        return 0
    else:
        logger.error("TESTS FAILED! Connection fix may not be stable.")
        return 1

if __name__ == "__main__":
    # Set up and run the test
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        exit_code = loop.run_until_complete(main())
        sys.exit(exit_code)
    finally:
        loop.close()