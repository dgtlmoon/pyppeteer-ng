#!/usr/bin/env python3
"""
CPU usage verification script.
Measures CPU usage when a connection disconnects unexpectedly.
"""
import asyncio
import logging
import os
import subprocess
import sys
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockWebSocket:
    """Mock WebSocket implementation."""
    def __init__(self):
        self._connected = True
        self.connection_lost_waiter = asyncio.Future()
        
    async def recv(self):
        """Wait a bit, then simulate connection close."""
        await asyncio.sleep(0.5)
        self._close()
        raise Exception("Connection closed")
        
    async def send(self, msg):
        print(f"SEND: {msg[:30]}...")
        
    async def close(self, code=1000, reason=None):
        print(f"CLOSE: code={code}, reason={reason}")
        self._close()
        
    def _close(self):
        """Close the connection and mark the connection_lost_waiter as done."""
        self._connected = False
        if not self.connection_lost_waiter.done():
            self.connection_lost_waiter.set_result(None)

class MockTransport:
    """Mock transport that simulates websockets module."""
    def __init__(self):
        self.ws = MockWebSocket()
        self.onmessage = None
        self.onclose = None
        
    async def recv(self):
        return await self.ws.recv()
        
    async def send(self, msg):
        await self.ws.send(msg)
        
    async def close(self, code=1000, reason=None):
        await self.ws.close(code, reason)
        if self.onclose:
            await self.onclose()

async def run_with_cpu_monitoring():
    """Run test and monitor CPU usage."""
    from pyppeteer.connection import Connection
    
    # Create mock transport and connection
    logger.info("Creating connection...")
    transport = MockTransport()
    conn = Connection("ws://test", transport)
    
    # Get current process ID for CPU monitoring
    pid = os.getpid()
    cpu_readings = []
    
    # Set up CPU monitoring task
    async def monitor_cpu():
        while True:
            try:
                # Get CPU usage
                cmd = f"ps -p {pid} -o %cpu | tail -n 1"
                result = subprocess.check_output(cmd, shell=True).decode().strip()
                cpu = float(result)
                cpu_readings.append(cpu)
                logger.info(f"CPU usage: {cpu}%")
                
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"Error monitoring CPU: {e}")
                break
    
    # Start CPU monitoring
    monitor_task = asyncio.create_task(monitor_cpu())
    
    try:
        # Send a message
        logger.info("Sending test message")
        fut = conn.send('Test.method', {'param': 'value'})
        
        # Wait a moment for the connection to be lost
        await asyncio.sleep(1)
        
        # Now that connection is closed, wait to see if CPU spikes
        logger.info("Connection should be closed now, monitoring CPU...")
        await asyncio.sleep(3)
        
    finally:
        # Stop monitoring and clean up
        monitor_task.cancel()
        try:
            await conn.dispose()
        except Exception:
            pass  # Expected to fail
        
    # Analyze CPU readings
    if cpu_readings:
        max_cpu = max(cpu_readings)
        avg_cpu = sum(cpu_readings) / len(cpu_readings)
        logger.info(f"CPU statistics: Max={max_cpu:.1f}%, Avg={avg_cpu:.1f}%")
        
        if max_cpu > 80:
            logger.error("HIGH CPU DETECTED! Fix is not working!")
        else:
            logger.info("CPU usage is normal, fix is working.")

async def main():
    logger.info("Testing CPU usage with connection fix...")
    await run_with_cpu_monitoring()
    logger.info("Test completed")

if __name__ == "__main__":
    asyncio.run(main())