import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import make_msgid
from config import EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FROM, EMAIL_TO

# ================= 邮件内容构建（原样保留）=================
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
        items_text_lines = []
        items_html_lines = []
        for p in products:
            line = f"• {p['name']}（{p.get('category','')}） - 价格：{p.get('price','?')} - 限购：{p.get('buy_limit_num','无')} - 时间：{p['time_label']}"
            items_text_lines.append(line)
            items_html_lines.append(f"<li><b>{p['name']}</b>（{p.get('category','')}） - 价格：{p.get('price','?')} - 限购：{p.get('buy_limit_num','无')} - 时间：{p['time_label']}</li>")
        items_text = "\n".join(items_text_lines)
        items_html = "<ul>" + "".join(items_html_lines) + "</ul>"
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

# ================= 邮件发送（图片内嵌版）=================
def send_email(subject, body_text, body_html=None, image_path=None):
    """
    发送邮件，如果提供 image_path 且 body_html 存在，则将图片内嵌到 HTML 尾部。
    保持原有参数不变。
    """
    if not all([EMAIL_SMTP_HOST, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FROM, EMAIL_TO]):
        print("❌ 邮件配置不完整，无法发送")
        return

    # 选择容器类型：有内嵌图片时用 'related'，否则用 'alternative'
    if body_html and image_path and os.path.exists(image_path):
        msg = MIMEMultipart('related')
    else:
        msg = MIMEMultipart('alternative')

    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO

    # 纯文本部分
    part_text = MIMEText(body_text, 'plain', 'utf-8')
    msg.attach(part_text)

    # 处理 HTML 与内嵌图片
    if body_html:
        final_html = body_html
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img_data = f.read()
            cid = make_msgid(domain='merchant')
            # 去掉 cid 字符串两边的尖括号，以便直接插入 src="cid:xxx"
            cid_clean = cid[1:-1] if cid.startswith('<') and cid.endswith('>') else cid
            # 在 HTML 尾部（</body> 前）插入图片标签
            img_tag = (
                '<br><br>'
                '<div style="text-align: center;">'
                f'<img src="cid:{cid_clean}" alt="商品截图" style="max-width: 100%; border: 1px solid #ccc;">'
                '<br><span style="color: #666; font-size: 12px;">📸 远行商人商品截图</span>'
                '</div>'
            )
            if '</body>' in final_html:
                final_html = final_html.replace('</body>', img_tag + '</body>')
            else:
                final_html = final_html + img_tag

            # 附加内嵌图片
            img_part = MIMEImage(img_data, name=os.path.basename(image_path))
            img_part.add_header('Content-ID', cid)
            img_part.add_header('Content-Disposition', 'inline', filename=os.path.basename(image_path))
            msg.attach(img_part)

        part_html = MIMEText(final_html, 'html', 'utf-8')
        msg.attach(part_html)

    # 发送邮件
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
