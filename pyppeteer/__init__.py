#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import os
from pathlib import Path
from typing import Any, List, Sequence, Union

from appdirs import AppDirs

__author__ = 'Hiroyuki Takagi, Bernardas Ališauskas, Matt Marcus'
__email__ = 'pyppeteer@protonmail.com'
__version__ = '2.0.0rc4'
__chromium_revision__ = '722234'
__base_puppeteer_version__ = 'v2.1.1'
__pyppeteer_home__ = os.environ.get('PYPPETEER_HOME', AppDirs('pyppeteer').user_data_dir)  # type: str


from pyppeteer.browser import Browser  # isort:skip
from pyppeteer.browser_fetcher import BrowserFetcher, Platform  # isort:skip
from pyppeteer.device_descriptors import devices  # isort:skip
from pyppeteer.launcher import ChromeLauncher, FirefoxLauncher, launcher  # isort:skip
from pyppeteer.models import BrowserOptions, ChromeArgOptions, Devices, LaunchOptions, Protocol  # isort:skip
from pyppeteer.websocket_transport import WebsocketTransport  # isort:skip

# Setup root logger
_logger = logging.getLogger(__name__)
# Don't set a default level - let it inherit WARNING from root logger
# Users can set the level explicitly via the logLevel parameter in launch()/connect()


class Pyppeteer:
    def __init__(self, projectRoot: str = None, preferredRevision: str = None):
        self._projectRoot = projectRoot
        self._preferredRevision = preferredRevision
        self._lazyLauncher = None
        self.productName = None

    @property
    def executablePath(self) -> Union[str, Path]:
        return self._launcher.executable_path

    @property
    def product(self) -> str:
        return self._launcher.product

    @property
    def devices(self) -> Devices:
        return devices

    async def launch(self, **kwargs: Union[LaunchOptions, ChromeArgOptions, BrowserOptions]) -> Browser:
        if not self.productName and kwargs:
            self.productName = kwargs.get('product')
        return await self._launcher.launch(**kwargs)

    async def connect(
        self,
        browserWSEndpoint: str = None,
        browserURL: str = None,
        transport: WebsocketTransport = None,
        ignoreHTTPSErrors: bool = False,
        slowMo: float = 0,
        defaultViewport: Protocol.Page.Viewport = None,
        logLevel: int = None,
    ) -> Browser:
        return await self._launcher.connect(
            browserWSEndpoint=browserWSEndpoint,
            browserURL=browserURL,
            ignoreHTTPSErrors=ignoreHTTPSErrors,
            transport=transport,
            slowMo=slowMo,
            defaultViewport=defaultViewport,
            logLevel=logLevel,
        )

    @property
    def _launcher(self) -> Union[FirefoxLauncher, ChromeLauncher]:
        if not self._lazyLauncher:
            self._lazyLauncher = launcher(
                projectRoot=self._projectRoot, preferredRevision=self._preferredRevision, product=self.productName
            )
        return self._lazyLauncher

    async def defaultArgs(
        self,
        args: Sequence[str] = None,
        devtools: bool = False,
        headless: bool = None,
        userDataDir: str = None,
        **_: Any,
    ) -> List[str]:
        return self._launcher.default_args(args=args, devtools=devtools, headless=headless, userDataDir=userDataDir)

    def createBrowserFetcher(self, platform: Platform = None, host: str = None,) -> BrowserFetcher:
        return BrowserFetcher(projectRoot=self._projectRoot, platform=platform, host=host)


# shortcut methods
async def launch(
    projectRoot: Union[Path, str] = None,
    preferredRevision: str = None,
    **kwargs: Union[LaunchOptions, ChromeArgOptions, BrowserOptions],
) -> Browser:
    return await Pyppeteer(projectRoot, preferredRevision).launch(**kwargs)


async def connect(
    projectRoot: Union[Path, str] = None,
    preferredRevision: str = None,
    browserWSEndpoint: str = None,
    browserURL: str = None,
    transport: WebsocketTransport = None,
    ignoreHTTPSErrors: bool = False,
    slowMo: float = 0,
    defaultViewport: Protocol.Page.Viewport = None,
    logLevel: int = None,
) -> Browser:
    return await Pyppeteer(projectRoot, preferredRevision).connect(
        browserWSEndpoint=browserWSEndpoint,
        browserURL=browserURL,
        transport=transport,
        ignoreHTTPSErrors=ignoreHTTPSErrors,
        slowMo=slowMo,
        defaultViewport=defaultViewport,
        logLevel=logLevel,
    )


version = __version__
# Parse version_info, handling suffixes like rc4
import re
_version_parts = [re.match(r'^\d+', part).group() if re.match(r'^\d+', part) else '0'
                 for part in __version__.split('.')[:3]]
version_info = tuple(int(x) for x in _version_parts)
DEBUG = False  # Debug flag for backwards compatibility


def defaultArgs(options=None, **kwargs):
    """Get default Chrome arguments."""
    # Handle both dict and keyword arguments for backwards compatibility
    if options and isinstance(options, dict):
        kwargs.update(options)
    return Pyppeteer()._launcher.default_args(**kwargs)


def executablePath():
    """Get Chrome executable path."""
    return Pyppeteer().executablePath


__all__ = [
    '__chromium_revision__',
    '__pyppeteer_home__',
    'version',
    'version_info',
    'DEBUG',
    'defaultArgs',
    'executablePath',
    'devices',
    'launch',
    'connect',
    'Pyppeteer',
]