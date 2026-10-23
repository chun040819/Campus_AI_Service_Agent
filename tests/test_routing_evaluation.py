from scripts.evaluate_routing import routing_matches


def test_route_requires_all_stages_in_order_and_rejects_extra_tools() -> None:
    stages = [["search_help_articles"], ["calculate_remaining_requests"]]
    assert routing_matches(["search_help_articles", "search_help_articles", "calculate_remaining_requests"], stages)
    assert not routing_matches(["search_help_articles"], stages)
    assert not routing_matches(["calculate_remaining_requests", "search_help_articles"], stages)
    assert not routing_matches(["search_help_articles", "get_human_support", "calculate_remaining_requests"], stages)


def test_no_tool_route_and_alternative_tools() -> None:
    assert routing_matches([], [])
    assert not routing_matches(["search_help_articles"], [])
    assert routing_matches(["get_human_support"], [["search_help_articles", "get_human_support"]])
