#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import sys

from pyppeteer import launch

dumpio = '--dumpio' in sys.argv


async def main():
    browser = await launch(args=['--no-sandbox'], dumpio=dumpio)
    page = await browser.newPage()
    await page.evaluate('console.log("DUMPIO_TEST")')
    await page.close()
    await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
