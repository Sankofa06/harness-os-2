from harness.agents.mentions import parse_mentions


def test_single_mention() -> None:
    result = parse_mentions("@builder please implement this")
    assert result.handles == ["builder"]
    assert not result.everyone


def test_multiple_mentions_deduplicated_order_preserved() -> None:
    result = parse_mentions("@planner and @alternate, then @planner again")
    assert result.handles == ["planner", "alternate"]


def test_everyone_mention() -> None:
    result = parse_mentions("@everyone stand by")
    assert result.everyone
    assert result.handles == []


def test_team_mention_is_just_a_handle() -> None:
    result = parse_mentions("@dev-team go")
    assert result.handles == ["dev-team"]


def test_email_like_text_is_not_a_mention() -> None:
    result = parse_mentions("contact me at user@example.com")
    assert result.handles == []


def test_no_mentions() -> None:
    result = parse_mentions("just a plain message")
    assert result.handles == []
    assert not result.everyone
