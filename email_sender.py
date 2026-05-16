import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from config import EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FROM, EMAIL_TO

def send_email(subject, body_text, body_html=None, image_path=None):
    """发送邮件，可选附带图片附件"""
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
    """从 processed 数据生成纯文本和 HTML 邮件正文"""
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