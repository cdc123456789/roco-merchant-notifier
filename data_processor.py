from time_utils import get_beijing_time, format_timestamp, get_round_info

def process_data_for_template(data):
    """将原始 API 数据转换为渲染模板所需的字典"""
    if not data:
        return {}

    now_ms = int(get_beijing_time().timestamp() * 1000)
    round_info = get_round_info()

    activities = data.get("merchantActivities") or data.get("merchant_activities") or []
    activity = activities[0] if activities else {}

    buckets = [
        ("道具", activity.get("get_props") or []),
        ("额外道具", activity.get("get_extra_props") or []),
        ("精灵", activity.get("get_pets") or []),
    ]

    random_goods = data.get("random_goods") if isinstance(data.get("random_goods"), list) else []
    goods_meta_by_name = {
        str(item.get("goods_name", "") or item.get("name", "")).strip(): item
        for item in random_goods
        if isinstance(item, dict) and str(item.get("goods_name", "") or item.get("name", "")).strip()
    }

    all_products = []
    active_products = []

    for category, items in buckets:
        for item in items:
            if not isinstance(item, dict):
                continue

            goods_meta = goods_meta_by_name.get(str(item.get("name", "")).strip(), {})

            s_time = item.get("start_time")
            e_time = item.get("end_time")

            if s_time is None:
                s_time = activity.get("start_time")
            if e_time is None:
                e_time = activity.get("end_time")

            start_ms = int(s_time) if s_time else None
            end_ms = int(e_time) if e_time else None

            is_active = True
            if start_ms is not None and end_ms is not None:
                is_active = start_ms <= now_ms < end_ms

            status_label = "当前轮次"
            if start_ms is not None and now_ms < start_ms:
                status_label = "未开始"
            elif end_ms is not None and now_ms >= end_ms:
                status_label = "已结束"

            start_str = format_timestamp(start_ms)
            end_str = format_timestamp(end_ms)
            if start_str[:5] == end_str[:5] and start_str != "--:--":
                time_label = f"{start_str} - {end_str[6:]}" if len(end_str) > 6 else f"{start_str} - {end_str}"
            else:
                time_label = f"{start_str} - {end_str}"

            product = {
                "name": item.get("name", "未知商品"),
                "image": item.get("icon_url", ""),
                "time_label": time_label,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "is_active": is_active,
                "status_label": status_label,
                "price": item.get("price") if item.get("price") not in (None, "") else goods_meta.get("price"),
                "buy_limit_num": item.get("buy_limit_num") if item.get("buy_limit_num") not in (None, "") else goods_meta.get("buy_limit_num"),
                "category": category
            }

            all_products.append(product)
            if is_active:
                active_products.append(product)

    # 历史记录分组（用于HTML模板）
    today = datetime.fromtimestamp(now_ms / 1000, tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    grouped = {}
    for product in all_products:
        if product["is_active"]:
            continue
        start_ms = product["start_ms"]
        if not start_ms:
            continue
        start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone(timedelta(hours=8)))
        if start_dt.strftime("%Y-%m-%d") != today:
            continue
        key = f"{start_ms}-{product['end_ms'] or ''}"
        if key not in grouped:
            grouped[key] = {
                "time_label": product["time_label"] or "--:--",
                "status_label": product["status_label"] or "其他时段",
                "sort": start_ms,
                "products": []
            }
        group = grouped[key]
        names = {p["name"] for p in group["products"]}
        if product["name"] not in names and len(group["products"]) < 5:
            group["products"].append(product)

    history_groups = [
        {k: v for k, v in g.items() if k != "sort"}
        for g in sorted(grouped.values(), key=lambda x: x["sort"])
        if g["products"]
    ]

    return {
        "title": activity.get("name", "远行商人"),
        "subtitle": activity.get("start_date", "每日 08:00 / 12:00 / 16:00 / 20:00 刷新"),
        "product_count": len(active_products),
        "round_info": round_info,
        "products": active_products,
        "history_groups": history_groups,
        "_res_path": "",
        "background": "img/bg.C8CUoi7I.jpg",
        "titleIcon": True
    }

def check_rare_products(products):
    """从活跃商品中识别稀有道具，返回匹配的关键词列表（去重）"""
    from config import RARE_KEYWORDS
    found = set()
    for p in products:
        name = p.get("name", "")
        for kw in RARE_KEYWORDS:
            if kw in name:
                found.add(kw)
    return list(found)

def build_rare_suffix(rare_list):
    """根据稀有道具列表生成邮件标题后缀"""
    if not rare_list:
        return ""
    rare_str = "/".join(rare_list)
    return f"【内含{rare_str}】"