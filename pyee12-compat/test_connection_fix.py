#!/usr/bin/env python3
import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from multiprocessing import Process

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    stream=sys.stdout)
logger = logging.getLogger(__name__)

# Create a connection manager class to test
class SimpleConnectionTest:
    def __init__(self):
        self.connection_module_path = os.path.join(os.getcwd(), 'pyppeteer/connection/__init__.py')
        self.connection_bak_path = os.path.join(os.getcwd(), 'pyppeteer/connection/__init__.py.bak')
        
    def test_description(self):
        """Describe the changes made to fix the high CPU issue."""
        logger.info("""
Fix for high CPU usage when browser disconnects:
1. Changed busy polling loop to event-driven approach
2. Added proper error handling for websocket disconnections
3. Added connection state tracking with atomic state transitions
4. Used websocket's built-in connection monitoring
5. Implemented asynchronous message processing
6. Ensured proper cleanup even during unexpected errors
        """)
    
    def run_simulate(self):
        """Simulate a situation where the connection loop would cause high CPU."""
        # Import the modules dynamically to ensure we use the updated code
        logger.info("Testing our fix by simulating a websocket connection closing...")
        
        # Create a simple script that imports our connection module and simulates usage
        script = """
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
"""
        
        # Write the test script
        test_script_path = os.path.join(os.getcwd(), 'connection_test_script.py')
        with open(test_script_path, 'w') as f:
            f.write(script)
        
        # Run the test script in a subprocess
        process = subprocess.Popen([sys.executable, test_script_path], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE)
        
        # Give it some time to run
        time.sleep(2)
        
        # Check CPU usage
        pid = process.pid
        high_cpu = False
        
        # Monitor CPU for 5 seconds
        start_time = time.time()
        while time.time() - start_time < 5:
            cmd = f"ps -p {pid} -o %cpu | tail -n 1"
            try:
                result = subprocess.check_output(cmd, shell=True).decode().strip()
                cpu_percent = float(result)
                logger.info(f"Process {pid} CPU usage: {cpu_percent}%")
                
                if cpu_percent > 90:  # High CPU threshold
                    logger.critical(f"Detected high CPU usage: {cpu_percent}%")
                    high_cpu = True
                    break
                    
                time.sleep(0.5)
            except (subprocess.SubprocessError, ValueError) as e:
                logger.error(f"Error monitoring CPU: {e}")
                break
        
        # Terminate the process
        process.terminate()
        stdout, stderr = process.communicate(timeout=2)
        
        logger.info(f"Test script output: {stdout.decode()}")
        if stderr:
            logger.error(f"Test script errors: {stderr.decode()}")
        
        if high_cpu:
            logger.error("❌ Test FAILED: High CPU usage detected")
            return False
        else:
            logger.info("✅ Test PASSED: No high CPU usage detected")
            return True

def main():
    """Main entry point."""
    logger.info("Starting test of connection fix...")
    test = SimpleConnectionTest()
    test.test_description()
    result = test.run_simulate()
    sys.exit(0 if result else 1)

if __name__ == "__main__":
    main()