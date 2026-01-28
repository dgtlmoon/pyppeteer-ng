#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test async context manager support for Browser."""

import unittest
from syncer import sync
from pyppeteer import launch


class TestBrowserContextManager(unittest.TestCase):
    """Test Browser async context manager protocol."""

    @sync
    async def test_context_manager_closes_browser(self):
        """Test that browser is properly closed when exiting context manager."""
        browser = await launch(args=['--no-sandbox'])
        
        # Use browser as async context manager
        async with browser as b:
            self.assertIs(b, browser)
            page = await browser.newPage()
            await page.goto('about:blank')
            self.assertTrue(browser.isConnected)
        
        # Browser should be closed after exiting context
        self.assertFalse(browser.isConnected)

    @sync
    async def test_context_manager_handles_exceptions(self):
        """Test that browser is closed even when exception occurs."""
        browser = await launch(args=['--no-sandbox'])
        
        try:
            async with browser:
                # Raise an exception
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected
        
        # Browser should still be closed
        self.assertFalse(browser.isConnected)
