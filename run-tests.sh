#!/bin/bash

python3 -mvenv .venv-test
source .venv-test/bin/activate
pip install poetry
poetry install
# Download Chrome/Chromium for testing
poetry run pyppeteer-install
poetry run pytest


#  Note: test_launcher.py tests will fail when executed because they use the old Tornado API (.listen(), .stop()) but the server was re-implemented with aiohttp in 2020. This is a pre-existing issue that needs separate refactoring.

# @todo tox
