#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio

from pyppeteer import launch


async def main() -> None:
    browser = await launch(args=['--no-sandbox'])
    print(browser.wsEndpoint, flush=True)


if __name__ == '__main__':
    asyncio.run(main())
