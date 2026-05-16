from datetime import datetime, timedelta, timezone

def get_beijing_time():
    """获取当前北京时间（带时区）"""
    return datetime.now(timezone(timedelta(hours=8)))

def format_timestamp(ts_ms):
    """毫秒时间戳 -> HH:MM 格式（北京时间）"""
    if not ts_ms:
        return "--:--"
    dt = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone(timedelta(hours=8)))
    return dt.strftime("%H:%M")

def get_round_info():
    """计算当前远行商人的轮次与倒计时"""
    now = get_beijing_time()
    start_time = now.replace(hour=8, minute=0, second=0, microsecond=0)

    if now < start_time:
        return {"current": "未开放", "total": 4, "countdown": "尚未开市"}

    delta_seconds = int((now - start_time).total_seconds())
    round_index = (delta_seconds // (4 * 3600)) + 1

    if round_index > 4:
        return {"current": 4, "total": 4, "countdown": "今日已收市"}

    round_end = start_time + timedelta(hours=round_index * 4)
    remaining = round_end - now
    hours, rem = divmod(int(remaining.total_seconds()), 3600)
    minutes, _ = divmod(rem, 60)

    countdown_str = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"

    return {
        "current": round_index,
        "total": 4,
        "countdown": countdown_str
    }