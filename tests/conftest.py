"""Shared test configuration.

``pytester`` is pytest's official fixture for testing plugins: it writes a throwaway
test tree into ``tmp_path`` and runs a nested pytest session against it, so the plugin
is exercised for real — no mocks.
"""

pytest_plugins = ["pytester"]
