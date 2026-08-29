"""Fonksiyon düzeyi kokular: derin iç içelik, aşırı parametre, yüksek CC."""


def deep_transform(data):
    """Kasıtlı derin iç içelik (max_nesting eşiğini aşar)."""
    result = []
    for group in data:
        if isinstance(group, list):
            for item in group:
                if isinstance(item, dict):
                    for key in sorted(item):
                        value = item[key]
                        if isinstance(value, (int, float)):
                            if value > 0:
                                result.append((key, value))
                            else:
                                result.append((key, 0))
    return result


def build_shipping_label(name, street, city, postcode, country, weight, express):
    """Kasıtlı aşırı parametre (7 > max_params.warn)."""
    speed = "EXPRESS" if express else "STANDARD"
    return f"{name}|{street}|{city} {postcode}|{country}|{weight:.1f}kg|{speed}"


def classify_order(total, item_count, tier, is_gift, country, coupon, weight):
    """Kasıtlı yüksek cyclomatic complexity."""
    if total <= 0:
        return "invalid"
    if item_count <= 0:
        return "invalid"
    if tier == "premium" and total > 1000:
        return "vip-large"
    if tier == "premium":
        return "vip"
    if is_gift and country != "TR":
        return "gift-international"
    if is_gift:
        return "gift-domestic"
    if coupon and total > 500:
        return "discounted-large"
    if coupon:
        return "discounted"
    if weight > 30:
        return "freight"
    if total > 1000:
        return "large"
    if item_count > 20:
        return "bulk"
    return "standard"
