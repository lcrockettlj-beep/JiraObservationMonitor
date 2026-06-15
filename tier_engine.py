
def calculate_tier_status(used: int, tier: int) -> str:
    if not tier:
        return "unknown"
    usage = (used / tier) * 100
    if usage >= 90:
        return "critical"
    if usage >= 70:
        return "warning"
    return "stable"


def generate_tier_metrics(used: int, tier: int):
    usage_percent = round((used / tier) * 100, 2) if tier else 0
    remaining = max(tier - used, 0) if tier else 0
    return {
        "licensed_users": used,
        "tier_limit": tier,
        "usage_percent": usage_percent,
        "capacity_remaining": remaining,
        "tier_status": calculate_tier_status(used, tier),
    }
