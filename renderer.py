import os
import asyncio
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
from config import ASSETS_DIR, HTML_TEMPLATE_FILE, TEMP_RENDER_FILE

async def render_to_image(processed_data):
    """渲染 HTML 模板并截图为 JPG，返回本地路径；若无商品则返回 None"""
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