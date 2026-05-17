import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import make_msgid
from config import EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FROM, EMAIL_TO

def send_email(subject, body_text, body_html=None, image_path=None):
    """发送邮件，可选择将图片内嵌到HTML正文尾部"""
    if not all([EMAIL_SMTP_HOST, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FROM, EMAIL_TO]):
        print("❌ 邮件配置不完整，无法发送")
        return

    msg = MIMEMultipart('related')  # 使用 'related' 支持内嵌资源
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO

    # 纯文本版本
    part_text = MIMEText(body_text, 'plain', 'utf-8')
    msg.attach(part_text)

    # 如果有图片且需要内嵌，先准备 HTML 内容并替换 cid
    if body_html and image_path and os.path.exists(image_path):
        with open(image_path, 'rb') as f:
            img_data = f.read()
        # 生成唯一 Content-ID
        cid = make_msgid(domain='merchant')
        # 在 HTML 末尾添加图片标签（如果原HTML没有图片插入点，直接追加到body末尾）
        # 为了美观，加个换行和图片说明
        img_tag = f'<br><br><img src="{cid}" alt="商品截图" style="max-width:100%;"><br><p>以上为商品截图</p>'
        # 将图片标签追加到原 body_html 末尾（通常 body_html 已经包含 </body>，需要插入到 </body> 之前）
        if '</body>' in body_html:
            body_html = body_html.replace('</body>', img_tag + '</body>')
        else:
            body_html = body_html + img_tag
        
        part_html = MIMEText(body_html, 'html', 'utf-8')
        msg.attach(part_html)
        
        # 内嵌图片附件
        img_part = MIMEImage(img_data, name=os.path.basename(image_path))
        img_part.add_header('Content-ID', f'<{cid}>')
        img_part.add_header('Content-Disposition', 'inline', filename=os.path.basename(image_path))
        msg.attach(img_part)
    elif body_html:
        # 无图片或图片不存在，直接附加 HTML
        part_html = MIMEText(body_html, 'html', 'utf-8')
        msg.attach(part_html)

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
