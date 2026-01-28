#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import unittest

import pyppeteer
import pytest
from pyppeteer.helpers import get_positive_int
from pyppeteer.page import convertPrintParameterToInches


class TestVersion(unittest.TestCase):
    def test_version(self):
        version = pyppeteer.version
        assert isinstance(version, str)
        assert version.count('.') == 2

    def test_version_info(self):
        vinfo = pyppeteer.version_info
        assert len(vinfo) == 3
        for i in vinfo:
            assert isinstance(i, int)


class TestDefaultArgs(unittest.TestCase):
    def test_default_args(self):
        assert '--no-first-run' in pyppeteer.defaultArgs()
        assert '--headless' in pyppeteer.defaultArgs()
        assert '--headless' not in pyppeteer.defaultArgs({'headless': False})
        assert '--user-data-dir=foo' in pyppeteer.defaultArgs(userDataDir='foo')


class TestToInches(unittest.TestCase):
    def test_px(self):
        assert convertPrintParameterToInches('12px') == 12.0 / 96

    def test_inch(self):
        assert round(abs(convertPrintParameterToInches('12in') - 12.0), 7) == 0

    def test_cm(self):
        assert round(abs(convertPrintParameterToInches('12cm') - 12.0 * 37.8 / 96), 7) == 0

    def test_mm(self):
        assert round(abs(convertPrintParameterToInches('12mm') - 12.0 * 3.78 / 96), 7) == 0


class TestPositiveInt(unittest.TestCase):
    def test_badtype(self):
        with pytest.raises(TypeError):
            get_positive_int({'a': 'b'}, 'a')

    def test_negative_int(self):
        with pytest.raises(ValueError):
            get_positive_int({'a': -1}, 'a')
