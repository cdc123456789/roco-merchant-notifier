import os

# API 与邮件配置（从环境变量读取）
ROCOM_API_KEY = os.environ.get("ROCOM_API_KEY")

EMAIL_SMTP_HOST = os.environ.get("EMAIL_SMTP_HOST")
EMAIL_SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", 465))
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_FROM = os.environ.get("EMAIL_FROM")
EMAIL_TO = os.environ.get("EMAIL_TO")          # 多个收件人用逗号分隔

# API 地址与本地资源路径
GAME_API_URL = "https://wegame.shallow.ink/api/v1/games/rocom/merchant/info"
ASSETS_DIR = os.path.abspath("assets/yuanxing-shangren")
HTML_TEMPLATE_FILE = "index.html"
TEMP_RENDER_FILE = "temp_render.html"

# 稀有道具关键词（用于邮件标题高亮）
RARE_KEYWORDS = ["国王球", "棱镜球", "炫彩精灵蛋"]