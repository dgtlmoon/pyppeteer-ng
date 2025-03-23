#!/usr/bin/env python3
"""
Run tests directly against a real Chrome browser.
This script patches the connection to use ws://127.0.0.1:3000.
"""
import asyncio
import logging
import os
import sys
import unittest
from unittest.mock import patch
import pytest

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# WebSocket URL
WEBSOCKET_URL = "ws://127.0.0.1:3000"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Override browser connection
async def custom_connect(*args, **kwargs):
    """Connect to real browser at ws://127.0.0.1:3000."""
    from pyppeteer.connection import Connection
    from pyppeteer.websocket_transport import WebsocketTransport
    from pyppeteer.browser import Browser
    
    logger.info(f"Connecting to browser at {WEBSOCKET_URL}")
    transport = await WebsocketTransport.create(WEBSOCKET_URL)
    connection = Connection(WEBSOCKET_URL, transport)
    
    # Create browser with this connection
    browser = Browser(connection, [], True, lambda: None)
    return browser

# Run a specific test directly
async def run_test(test_name):
    """Run a specific test directly against the custom browser."""
    from pyppeteer import launch
    
    # Connect to browser
    browser = await custom_connect()
    
    try:
        # Create an isolated page
        page = await browser.newPage()
        
        logger.info(f"Running test: {test_name}")
        
        # Define common test utilities
        def request_continuer(request):
            asyncio.ensure_future(request.continue_())
        
        # Basic test for request interception
        if test_name == "test_basic_usage":
            # Set up request interception
            await page.setRequestInterception(True)
            
            # Track intercepted requests
            intercepted_requests = []
            
            @page.on('request')
            async def request_handler(request):
                intercepted_requests.append(request)
                await request.continue_()
            
            # Navigate to a page
            await page.goto('https://example.com')
            
            # Verify requests were intercepted
            logger.info(f"Intercepted {len(intercepted_requests)} requests")
            assert len(intercepted_requests) > 0, "No requests were intercepted"
            
            # Check first request properties
            first_request = intercepted_requests[0]
            assert first_request.url == 'https://example.com/'
            assert first_request.method == 'GET'
            assert first_request.resourceType == 'document'
            
            logger.info("Test test_basic_usage PASSED")
            return True
            
        elif test_name == "test_stop_interception":
            # First enable interception
            await page.setRequestInterception(True)
            
            # Track intercepted requests
            intercepted1 = []
            
            @page.on('request')
            async def handler1(request):
                intercepted1.append(request)
                await request.continue_()
            
            # Navigate to a page
            await page.goto('https://example.com')
            
            # Verify interception worked
            count1 = len(intercepted1)
            assert count1 > 0, "Interception didn't work"
            
            # Now disable interception
            await page.setRequestInterception(False)
            
            # Reset counters
            intercepted1.clear()
            
            # Navigate again
            await page.goto('https://example.com')
            
            # Verify no more interception
            assert len(intercepted1) == 0, "Interception still happening after disabling"
            
            logger.info("Test test_stop_interception PASSED")
            return True
            
        elif test_name == "test_abortability":
            # Set up request interception
            await page.setRequestInterception(True)
            
            # Abort all image requests
            @page.on('request')
            async def request_handler(request):
                if request.resourceType == 'image':
                    await request.abort()
                else:
                    await request.continue_()
            
            # Navigate to a page with images
            response = await page.goto('https://example.com')
            
            # Verify navigation worked
            assert response.ok
            
            # Look for error events on images
            has_errors = await page.evaluate('''() => {
                const errors = [];
                window.addEventListener('error', e => errors.push(e.message), {capture: true});
                // Try to load an image
                const img = document.createElement('img');
                img.src = 'https://example.com/nonexistent.jpg';
                document.body.appendChild(img);
                
                // Wait a bit for error to happen
                return new Promise(resolve => setTimeout(() => resolve(errors.length > 0), 1000));
            }''')
            
            assert has_errors, "No error events detected for aborted images"
            
            logger.info("Test test_abortability PASSED")
            return True
            
        # Add more test implementations as needed
        else:
            logger.warning(f"Test {test_name} not implemented")
            return False
            
    except Exception as e:
        logger.error(f"Test {test_name} FAILED: {e}")
        return False
    finally:
        # Clean up
        if 'page' in locals():
            await page.close()
        await browser.close()

async def run_all_tests():
    """Run all implemented tests."""
    # List of tests to run
    tests = [
        "test_basic_usage",
        "test_stop_interception",
        "test_abortability",
        # Add more tests as they're implemented
    ]
    
    # Run each test
    results = {}
    for test_name in tests:
        logger.info(f"\n=== Running {test_name} ===")
        result = await run_test(test_name)
        results[test_name] = result
    
    # Report results
    logger.info("\n=== Test Results ===")
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        logger.info("\n✅ ALL TESTS PASSED!")
    else:
        logger.error("\n❌ SOME TESTS FAILED!")
    
    return all_passed

def main():
    """Main entry point."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        success = loop.run_until_complete(run_all_tests())
        return 0 if success else 1
    finally:
        loop.close()

if __name__ == "__main__":
    sys.exit(main())