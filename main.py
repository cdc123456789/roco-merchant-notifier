import os
import requests
import asyncio
import smtplib
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime, timedelta, timezone
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright

# ================= 1. 配置区域 =================
ROCOM_API_KEY = os.environ.get("ROCOM_API_KEY")

# 邮件配置（必须）
EMAIL_SMTP_HOST = os.environ.get("EMAIL_SMTP_HOST")
EMAIL_SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", 465))
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_FROM = os.environ.get("EMAIL_FROM")
EMAIL_TO = os.environ.get("EMAIL_TO")

GAME_API_URL = "https://wegame.shallow.ink/api/v1/games/rocom/merchant/info"
ASSETS_DIR = os.path.abspath("assets/yuanxing-shangren")
HTML_TEMPLATE_FILE = "index.html"
TEMP_RENDER_FILE = "temp_render.html"

# 稀有道具关键词
RARE_KEYWORDS = ["国王球", "棱镜球", "炫彩精灵蛋"]

# ================= 2. 时间与数据处理逻辑 =================
def get_beijing_time():
    return datetime.now(timezone(timedelta(hours=8)))

def format_timestamp(ts_ms):
    if not ts_ms:
        return "--:--"
    dt = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone(timedelta(hours=8)))
    return dt.strftime("%H:%M")

def get_round_info():
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

def process_data_for_template(data):
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

    # 历史记录分组（保留用于HTML模板）
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

# ================= 3. 图像渲染 =================
async def render_to_image(processed_data):
    if not processed_data or processed_data["product_count"] == 0:
        print("当前无活跃商品，跳过渲染")
        return None

    screenshot_file = "merchant_render.jpg"
    temp_html_path = os.path.join(ASSETS_DIR, TEMP_RENDER_FILE)

    try:
        env = Environment(loader=FileSystemLoader(ASSETS_DIR))
        template = env.get_template(HTML_TEMPLATE_FILE)
        rendered_html = template.render(processed_data)

        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_viewport_size({"width": 900, "height": 1600})
            await page.goto(f"file://{temp_html_path}")
            await page.evaluate("document.fonts.ready")
            await page.wait_for_load_state("networkidle")
            data_region = page.locator('.merchant-page')
            await data_region.screenshot(path=screenshot_file, type="jpeg", quality=90)
            await browser.close()
            print(f"✅ 图片渲染成功: {screenshot_file}")
            return screenshot_file
    except Exception as e:
        print(f"❌ 渲染图片失败: {e}")
        return None
    finally:
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)

# ================= 4. 邮件发送 =================
def send_email(subject, body_text, body_html=None, image_path=None):
    if not all([EMAIL_SMTP_HOST, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FROM, EMAIL_TO]):
        print("❌ 邮件配置不完整，无法发送")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO

    part_text = MIMEText(body_text, 'plain', 'utf-8')
    msg.attach(part_text)

    if body_html:
        part_html = MIMEText(body_html, 'html', 'utf-8')
        msg.attach(part_html)

    if image_path and os.path.exists(image_path):
        with open(image_path, 'rb') as f:
            img_data = f.read()
        img_attachment = MIMEImage(img_data, name=os.path.basename(image_path))
        msg.attach(img_attachment)

    try:
        if EMAIL_SMTP_PORT == 465:
            with smtplib.SMTP_SSL(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
                server.login(EMAIL_USER, EMAIL_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PASSWORD)
                server.send_message(msg)
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

def build_email_content(processed):
    round_info = processed["round_info"]
    products = processed["products"]
    title = processed["title"]

    if isinstance(round_info["current"], int):
        round_text = f"第 {round_info['current']} / {round_info['total']} 轮"
    else:
        round_text = round_info["current"]
    countdown = round_info["countdown"]

    if products:
        items_text = "\n".join(
            f"• {p['name']}（{p.get('category','')}） - 价格：{p.get('price','?')} - 限购：{p.get('buy_limit_num','无')} - 时间：{p['time_label']}"
            for p in products
        )
        items_html = "<ul>" + "".join(
            f"<li><b>{p['name']}</b>（{p.get('category','')}） - 价格：{p.get('price','?')} - 限购：{p.get('buy_limit_num','无')} - 时间：{p['time_label']}</li>"
            for p in products
        ) + "</ul>"
    else:
        items_text = "当前暂无商品"
        items_html = "<p>当前暂无商品</p>"

    body_text = f"""【{title}】{round_text}，倒计时 {countdown}

活跃商品：
{items_text}

截图请见附件。
"""

    body_html = f"""
    <html>
    <body>
    <h2>{title}</h2>
    <p><strong>{round_text}</strong>，倒计时 <strong>{countdown}</strong></p>
    <h3>活跃商品</h3>
    {items_html}
    <p>截图请见附件。</p>
    </body>
    </html>
    """
    return body_text, body_html

# ================= 5. 辅助：检查稀有物品 =================
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
    # 例如 ['国王球', '炫彩精灵蛋'] -> "【内含国王球/炫彩精灵蛋】"
    rare_str = "/".join(rare_list)
    return f"【内含{rare_str}】"

# ================= 6. 主入口 =================
async def main():
    try:
        resp = requests.get(GAME_API_URL, headers={"X-API-Key": ROCOM_API_KEY}, timeout=30)
        resp.raise_for_status()
        response_json = resp.json()
        raw_data = response_json.get("data", {})
        err = None if response_json.get("code") == 0 else response_json.get("message")

        print("\n========== API 原始响应 JSON ==========")
        print(json.dumps(response_json, indent=2, ensure_ascii=False))
        print("========================================\n")

    except Exception as e:
        raw_data, err = None, f"请求异常: {e}"
        print(f"❌ 请求失败: {err}")

    if err or not raw_data:
        subject = "⚠️ 远行商人监控异常"
        body = f"无法获取数据：{err or '未知错误'}"
        send_email(subject, body, f"<p>{body}</p>", None)
        return

    processed = process_data_for_template(raw_data)

    # 检查活跃商品中是否有稀有道具
    rare_items = check_rare_products(processed.get("products", []))
    rare_suffix = build_rare_suffix(rare_items)

    if processed["product_count"] == 0:
        print("无活跃商品，发送无商品邮件")
        subject = f"📢 远行商人已刷新（无商品）{rare_suffix}"
        body_text, body_html = build_email_content(processed)
        send_email(subject, body_text, body_html, None)
        return

    local_img = await render_to_image(processed)
    # 根据是否有稀有道具构造标题
    subject = f"📢 远行商人已刷新{rare_suffix}"
    body_text, body_html = build_email_content(processed)
    send_email(subject, body_text, body_html, local_img)

    if local_img and os.path.exists(local_img):
        os.remove(local_img)
        print(f"🗑️ 已删除临时截图 {local_img}")

if __name__ == "__main__":
    asyncio.run(main())