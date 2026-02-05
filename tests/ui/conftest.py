import os
import tempfile
from typing import Generator

import pytest
from playwright.sync_api import Browser, Page, sync_playwright


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def browser() -> Generator[Browser, None, None]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser: Browser, request: pytest.FixtureRequest) -> Generator[Page, None, None]:
    video_option = request.config.getoption("--video", default=None)
    if video_option == "on":
        context = browser.new_context(
            record_video_dir="test-results/",
            record_video_size={"width": 1280, "height": 720}
        )
        page = context.new_page()
    else:
        page = browser.new_page()
    page.set_default_timeout(15000)
    yield page
    page.close()
    if video_option == "on":
        context.close()


def pytest_addoption(parser: pytest.Parser):
    parser.addoption("--video", action="store", default=None, help="Record video: on/off")
