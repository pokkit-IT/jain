"""In-process fake for a third-party external plugin.

Used by the install/call/uninstall integration test. Not a real service —
tests mock httpx to route calls here.
"""

FAKE_MANIFEST = {
    "name": "fake_weather",
    "version": "0.1.0",
    "type": "external",
    "description": "Returns a fixed weather string for tests",
    "skills": [
        {
            "name": "weather",
            "description": "Get weather.",
            "tools": ["get_weather"],
        }
    ],
    "api": {"base_url": "https://fake-weather.test"},
}
