#!/usr/bin/env python3
"""
Basic WebSocket connection test that focuses on disconnection handling.
"""
import asyncio
import logging
import sys
import time
import os
import subprocess
import signal
import websockets
import json

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# WebSocket URL
WEBSOCKET_URL = "ws://127.0.0.1:3000"

class TestConnection:
    """Test WebSocket connection directly."""
    
    async def run_test(self):
        """Test WebSocket connection handling."""
        # Import our connection code
        from pyppeteer.websocket_transport import WebsocketTransport
        
        logger.info(f"Connecting to {WEBSOCKET_URL}...")
        try:
            # Connect to WebSocket
            transport = await WebsocketTransport.create(WEBSOCKET_URL)
            logger.info("Connected successfully!")
            
            # Get the raw WebSocket object
            ws = transport.ws
            
            # Monitor CPU for a bit while connected
            logger.info("Monitoring CPU while connected...")
            pid = os.getpid()
            await self._monitor_cpu(pid, 2)
            
            # Now close the connection deliberately
            logger.info("Closing connection...")
            await transport.close(1000, "Test complete")
            
            # Monitor CPU after disconnection
            logger.info("Monitoring CPU after disconnection...")
            high_cpu = await self._monitor_cpu(pid, 5)
            
            if high_cpu:
                logger.error("High CPU detected after disconnection!")
                return False
            else:
                logger.info("No high CPU detected after disconnection")
                return True
                
        except Exception as e:
            logger.error(f"Test failed: {e}")
            return False
    
    async def _monitor_cpu(self, pid, duration=5):
        """Monitor CPU usage of this process."""
        start_time = time.time()
        readings = []
        high_cpu_detected = False
        
        while time.time() - start_time < duration:
            # Get CPU usage
            try:
                cmd = f"ps -p {pid} -o %cpu | tail -n 1"
                result = subprocess.check_output(cmd, shell=True).decode().strip()
                cpu = float(result)
                readings.append(cpu)
                logger.info(f"CPU usage: {cpu}%")
                
                if cpu > 80:  # High CPU threshold
                    logger.warning(f"High CPU detected: {cpu}%")
                    high_cpu_detected = True
            except Exception as e:
                logger.error(f"Error checking CPU: {e}")
            
            # Check every 0.5 seconds
            await asyncio.sleep(0.5)
        
        # Calculate average
        if readings:
            avg_cpu = sum(readings) / len(readings)
            logger.info(f"Average CPU over {duration} seconds: {avg_cpu:.1f}%")
        
        return high_cpu_detected

async def main():
    """Run the WebSocket test."""
    logger.info("Starting basic WebSocket connection test...")
    
    test = TestConnection()
    success = await test.run_test()
    
    if success:
        logger.info("Test PASSED! No high CPU detected after disconnection.")
        return 0
    else:
        logger.error("Test FAILED! High CPU detected.")
        return 1

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        exit_code = loop.run_until_complete(main())
        sys.exit(exit_code)
    finally:
        loop.close()