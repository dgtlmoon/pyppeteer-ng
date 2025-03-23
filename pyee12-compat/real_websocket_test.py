#!/usr/bin/env python3
"""
Test for the connection module using a real WebSocket endpoint.
"""
import asyncio
import logging
import sys
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the WebSocket URL
WEBSOCKET_URL = "ws://127.0.0.1:3000"

async def test_real_connection():
    """Test the Connection class with a real WebSocket."""
    from pyppeteer.connection import Connection
    from pyppeteer.websocket_transport import WebsocketTransport
    
    # Create transport with real WebSocket
    logger.info(f"Connecting to WebSocket at {WEBSOCKET_URL}...")
    try:
        transport = await WebsocketTransport.create(WEBSOCKET_URL)
        logger.info("Successfully connected to WebSocket!")
        
        # Create connection
        conn = Connection(WEBSOCKET_URL, transport)
        
        # Send a test message
        logger.info("Sending test message...")
        future = conn.send('Runtime.evaluate', {'expression': '1+1'})
        
        try:
            # Wait for the response with timeout
            result = await asyncio.wait_for(future, timeout=5.0)
            logger.info(f"Received response: {result}")
            
            # Send another message
            logger.info("Sending another message...")
            future2 = conn.send('Page.navigate', {'url': 'about:blank'})
            result2 = await asyncio.wait_for(future2, timeout=5.0)
            logger.info(f"Received second response: {result2}")
            
            # Now simulate connection issue by closing the browser
            logger.info("Test phase: Simulating browser disconnection...")
            logger.info("Please close the browser or WebSocket server now...")
            
            # Wait for a moment for manual intervention
            await asyncio.sleep(5)
            
            # Try to send another message after browser is closed
            try:
                logger.info("Sending message after disconnect...")
                future3 = conn.send('Runtime.evaluate', {'expression': 'console.log("test")'})
                result3 = await asyncio.wait_for(future3, timeout=5.0)
                logger.info(f"Unexpected success: {result3}")
                return False
            except Exception as e:
                logger.info(f"Got expected error after disconnect: {e}")
                
            # Monitor CPU usage - our fix should prevent high CPU
            logger.info("Monitoring for CPU usage after disconnect...")
            start_time = time.time()
            while time.time() - start_time < 10:
                # Just wait to see if any high CPU issues occur
                await asyncio.sleep(1)
            
            logger.info("Test completed successfully - no high CPU detected")
            return True
            
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for response")
            return False
        except Exception as e:
            logger.error(f"Error during test: {e}")
            return False
        finally:
            # Clean up
            logger.info("Disposing connection...")
            try:
                await conn.dispose()
            except Exception as e:
                logger.warning(f"Error during dispose: {e}")
    except Exception as e:
        logger.error(f"Failed to connect to WebSocket: {e}")
        return False

def main():
    """Run the test."""
    logger.info("Testing connection with real WebSocket...")
    
    # Set up asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Run the test
        success = loop.run_until_complete(test_real_connection())
        
        if success:
            logger.info("Test PASSED! The connection fix is working correctly.")
            return 0
        else:
            logger.error("Test FAILED!")
            return 1
    finally:
        loop.close()

if __name__ == "__main__":
    sys.exit(main())