async def test_get_settings_returns_defaults(client):
    response = await client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "copilot"
    assert body["radius_miles"] == 10
    assert body["llm_provider"] == "anthropic"
