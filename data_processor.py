from datetime import datetime, timedelta, timezone
from time_utils import get_beijing_time, format_timestamp, get_round_info
from config import RARE_KEYWORDS

# ================= 辅助函数 =================
def ms_to_beijing_datetime(ms: int) -> datetime:
    """毫秒时间戳转北京时间 datetime 对象"""
    return datetime.fromtimestamp(ms / 1000, tz=timezone(timedelta(hours=8)))

def safe_int(value) -> int | None:
    """安全转换为 int，若为 None 或不可转换则返回 None"""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

# ================= 核心处理 =================
def process_data_for_template(data):
    """将原始 API 数据转换为渲染模板所需的字典"""
    if not data:
        return {}

    now_ms = int(get_beijing_time().timestamp() * 1000)
    round_info = get_round_info()

    activities = data.get("merchantActivities") or data.get("merchant_activities") or []
    activity = activities[0] if activities else {}

    # 商品分类
    buckets = [
        ("道具", activity.get("get_props") or []),
        ("额外道具", activity.get("get_extra_props") or []),
        ("精灵", activity.get("get_pets") or []),
    ]

    # 商品元数据字典（用于价格和限购）
    random_goods = data.get("random_goods")
    if not isinstance(random_goods, list):
        random_goods = []
    goods_meta_by_name = {}
    for item in random_goods:
        if not isinstance(item, dict):
            continue
        name = str(item.get("goods_name", "") or item.get("name", "")).strip()
        if name:
            goods_meta_by_name[name] = item

    all_products = []
    active_products = []

    for category, items in buckets:
        for item in items:
            if not isinstance(item, dict):
                continue

            # 商品名称与元数据
            name = item.get("name", "未知商品")
            goods_meta = goods_meta_by_name.get(name.strip(), {})

            # 获取开始/结束时间（优先商品自身，无则继承活动）
            start_ms = safe_int(item.get("start_time"))
            end_ms = safe_int(item.get("end_time"))
            if start_ms is None:
                start_ms = safe_int(activity.get("start_time"))
            if end_ms is None:
                end_ms = safe_int(activity.get("end_time"))

            # 活跃判断
            is_active = False
            if start_ms is not None and end_ms is not None:
                is_active = start_ms <= now_ms < end_ms
            status_label = "当前轮次" if is_active else (
                "未开始" if (start_ms is not None and now_ms < start_ms) else
                "已结束" if (end_ms is not None and now_ms >= end_ms) else
                "其他"
            )

            # 时间标签格式化
            start_str = format_timestamp(start_ms)
            end_str = format_timestamp(end_ms)
            if start_str != "--:--" and end_str != "--:--" and start_str[:5] == end_str[:5]:
                # 同小时，合并显示：08:00 - 30
                time_label = f"{start_str} - {end_str[3:]}" if len(end_str) >= 5 else f"{start_str} - {end_str}"
            else:
                time_label = f"{start_str} - {end_str}"

            product = {
                "name": name,
                "image": item.get("icon_url", ""),
                "time_label": time_label,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "is_active": is_active,
                "status_label": status_label,
                "price": item.get("price") if item.get("price") not in (None, "") else goods_meta.get("price"),
                "buy_limit_num": item.get("buy_limit_num") if item.get("buy_limit_num") not in (None, "") else goods_meta.get("buy_limit_num"),
                "category": category,
            }
            all_products.append(product)
            if is_active:
                active_products.append(product)

    # 历史记录分组（同一时间段的非活跃商品）
    history_groups = _group_history_products(all_products, now_ms)

    return {
        "title": activity.get("name", "远行商人"),
        "subtitle": activity.get("start_date", "每日 08:00 / 12:00 / 16:00 / 20:00 刷新"),
        "product_count": len(active_products),
        "round_info": round_info,
        "products": active_products,
        "history_groups": history_groups,
        "_res_path": "",
        "background": "img/bg.C8CUoi7I.jpg",
        "titleIcon": True,
    }

def _group_history_products(all_products, now_ms):
    """将今天的非活跃商品按时间段分组（每组最多5个商品）"""
    today_date = ms_to_beijing_datetime(now_ms).date()
    groups = {}

    for product in all_products:
        if product["is_active"]:
            continue
        start_ms = product["start_ms"]
        if start_ms is None:
            continue
        product_date = ms_to_beijing_datetime(start_ms).date()
        if product_date != today_date:
            continue

        # 分组键：时间段标识（start_ms + end_ms）
        group_key = f"{start_ms}-{product['end_ms'] or ''}"
        if group_key not in groups:
            groups[group_key] = {
                "time_label": product["time_label"] or "--:--",
                "status_label": product["status_label"] or "其他时段",
                "sort": start_ms,
                "products": [],
                "_names": set(),  # 用于去重
            }
        group = groups[group_key]
        # 避免重复商品名，且每组最多5个
        if product["name"] not in group["_names"] and len(group["products"]) < 5:
            group["products"].append(product)
            group["_names"].add(product["name"])

    # 按开始时间排序，并移除内部辅助字段
    sorted_groups = sorted(groups.values(), key=lambda g: g["sort"])
    result = []
    for g in sorted_groups:
        # 只保留需要暴露的字段
        result.append({
            "time_label": g["time_label"],
            "status_label": g["status_label"],
            "products": g["products"],
        })
    return result

# ================= 稀有道具处理 =================
def check_rare_products(products):
    """从活跃商品中识别稀有道具，返回匹配的关键词列表（去重）"""
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
    return "【内含" + "/".join(rare_list) + "】"
