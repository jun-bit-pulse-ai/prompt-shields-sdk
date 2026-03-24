from prompt_shields import ShieldsClient


def test_client_init():
    client = ShieldsClient(
        api_key="sk-test",
        ps_api_key="ps-test",
        business_unit="HR",
        use_case="screening",
        owner="jane@test.com",
        ps_collector_url="http://localhost:8000",
    )
    assert client._ps_api_key == "ps-test"
    assert client._metadata["business_unit"] == "HR"
    assert client._metadata["use_case"] == "screening"
    assert client._metadata["owner"] == "jane@test.com"


def test_client_has_chat_completions():
    client = ShieldsClient(
        api_key="sk-test",
        ps_api_key="ps-test",
        ps_collector_url="http://localhost:8000",
    )
    assert hasattr(client, "chat")
    assert hasattr(client.chat, "completions")
    assert hasattr(client.chat.completions, "create")


def test_client_metadata_filters_none():
    client = ShieldsClient(
        api_key="sk-test",
        ps_api_key="ps-test",
        business_unit="HR",
        ps_collector_url="http://localhost:8000",
    )
    assert "use_case" not in client._metadata
    assert "owner" not in client._metadata
    assert client._metadata == {"business_unit": "HR"}


def test_build_event_maps_field_names():
    """Verify use_case -> use_case_name and owner -> owner_email mapping."""
    from unittest.mock import MagicMock
    client = ShieldsClient(
        api_key="sk-test",
        ps_api_key="ps-test",
        use_case="screening",
        owner="jane@test.com",
        business_unit="HR",
        ps_collector_url="http://localhost:8000",
    )
    mock_response = MagicMock()
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20

    event = client._build_event(
        model="gpt-4o",
        messages=[{"role": "user", "content": "hello"}],
        response=mock_response,
        latency_ms=100,
    )
    assert event["use_case_name"] == "screening"
    assert event["owner_email"] == "jane@test.com"
    assert event["business_unit"] == "HR"
    assert "use_case" not in event
    assert "owner" not in event
