import os
import sys
import requests
import asyncio
import json
from config import ROCOM_API_KEY, GAME_API_URL
from time_utils import get_beijing_time
from data_processor import process_data_for_template, check_rare_products, build_rare_suffix
from email_sender import send_email, build_email_content
from renderer import render_to_image

async def main():
    # 1. 请求 API 数据
    try:
        resp = requests.get(GAME_API_URL, headers={"X-API-Key": ROCOM_API_KEY}, timeout=30)
        resp.raise_for_status()
        response_json = resp.json()
        raw_data = response_json.get("data", {})
        err = None if response_json.get("code") == 0 else response_json.get("message")

        # 打印原始 JSON（便于调试）
        print("\n========== API 原始响应 JSON ==========")
        print(json.dumps(response_json, indent=2, ensure_ascii=False))
        print("========================================\n")

    except Exception as e:
        raw_data, err = None, f"请求异常: {e}"
        print(f"❌ 请求失败: {err}")

    # 2. 错误处理：发送异常通知邮件
    if err or not raw_data:
        subject = "⚠️ 远行商人监控异常"
        body = f"无法获取数据：{err or '未知错误'}"
        send_email(subject, body, f"<p>{body}</p>", None)
        sys.exit(1)

    # 3. 处理数据
    processed = process_data_for_template(raw_data)

    # 4. 检查稀有道具，生成标题后缀
    rare_items = check_rare_products(processed.get("products", []))
    rare_suffix = build_rare_suffix(rare_items)

    # 5. 无商品情况
    if processed["product_count"] == 0:
        print("无活跃商品，发送无商品邮件")
        subject = f"📢 远行商人已刷新（无商品）{rare_suffix}"
        body_text, body_html = build_email_content(processed)
        send_email(subject, body_text, body_html, None)
        return

    # 6. 有商品：渲染截图并发送邮件
    local_img = await render_to_image(processed)
    subject = f"📢 远行商人已刷新{rare_suffix}"
    body_text, body_html = build_email_content(processed)
    send_email(subject, body_text, body_html, local_img)

    # 7. 清理临时截图
    if local_img and os.path.exists(local_img):
        os.remove(local_img)
        print(f"🗑️ 已删除临时截图 {local_img}")

if __name__ == "__main__":
    asyncio.run(main())
