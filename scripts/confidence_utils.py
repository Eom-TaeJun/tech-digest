def confidence_gate(config: dict) -> dict:
    return config.get("summary", {}).get("confidence_gate", {})


def classify_confidence(result: dict, gate: dict) -> str:
    evidence = result.get("evidence", {})
    source = result.get("source", "")
    official = evidence.get("official_source_count", 0)
    community = evidence.get("community_source_count", 0)
    filtered = evidence.get("filtered_out_citation_count", 0)
    raw_citations = evidence.get("raw_citation_count", 0)

    high_min = gate.get("high_min_community_sources", 3)
    medium_min = gate.get("medium_min_community_sources", 1)
    source_rules = gate.get("source_rules", {})
    source_rule = source_rules.get(source)

    if source_rule == "official_only":
        return "HIGH" if official > 0 or evidence.get("has_official_sources") else "LOW"
    if source_rule == "community_only":
        if community >= high_min:
            return "HIGH"
        if community >= medium_min:
            return "MEDIUM"
        return "LOW"
    if official > 0 or evidence.get("has_official_sources"):
        return "HIGH"
    if community >= high_min and filtered == 0:
        return "HIGH"
    if community >= medium_min:
        return "MEDIUM"
    if raw_citations and filtered >= raw_citations and official == 0 and community == 0:
        return "LOW"
    return "LOW"
