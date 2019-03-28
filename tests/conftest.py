import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--requires_linters",
        action="store_true",
        default=False,
        help="Run tests that require the linter dockers available."
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--requires_linters"):
        # pull linters
        return
    skip = pytest.mark.skip(reason="need --requires_linters option to run")
    for item in items:
        if "requires_linters" in item.keywords:
            item.add_marker(skip)
