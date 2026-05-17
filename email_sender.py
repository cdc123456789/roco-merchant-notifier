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

# ================= 邮件发送（确保 HTML 正文 + 图片内嵌）=================
def send_email(subject, body_text, body_html=None, image_path=None):
    """
    发送邮件。如果提供 image_path 且 body_html 存在，则将图片内嵌到 HTML 尾部。
    参数签名保持不变。
    """
    if not all([EMAIL_SMTP_HOST, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FROM, EMAIL_TO]):
        print("❌ 邮件配置不完整，无法发送")
        return

    # 根容器：如果需要内嵌图片，使用 related；否则用 alternative
    if body_html and image_path and os.path.exists(image_path):
        # 有图片：根 MIME 类型为 related，内部包含 alternative 和 图片
        root = MIMEMultipart('related')
        # 创建 alternative 子容器，用于纯文本和 HTML 正文
        alt = MIMEMultipart('alternative')
        root.attach(alt)
    else:
        # 无图片：直接使用 alternative 作为根
        root = MIMEMultipart('alternative')
        alt = root  # 别名，方便后面统一处理

    root['Subject'] = subject
    root['From'] = EMAIL_FROM
    root['To'] = EMAIL_TO

    # 添加纯文本部分
    part_text = MIMEText(body_text, 'plain', 'utf-8')
    alt.attach(part_text)

    # 添加 HTML 部分（可能被修改以包含图片引用）
    if body_html:
        final_html = body_html
        if image_path and os.path.exists(image_path):
            # 读取图片数据
            with open(image_path, 'rb') as f:
                img_data = f.read()
            # 生成唯一 Content-ID（不带尖括号，用于引用）
            cid = make_msgid(domain='merchant')[1:-1]  # 去掉 <>
            # 在 HTML 尾部添加图片标签
            img_tag = (
                '<br><br>'
                '<div style="text-align: center;">'
                f'<img src="cid:{cid}" alt="商品截图" style="max-width: 100%; border: 1px solid #ccc;">'
                '<br><span style="color: #666; font-size: 12px;">📸 远行商人商品截图</span>'
                '</div>'
            )
            if '</body>' in final_html:
                final_html = final_html.replace('</body>', img_tag + '</body>')
            else:
                final_html = final_html + img_tag

            # 附加图片作为内嵌资源（需要放在 root 下，即与 alt 同级）
            img_part = MIMEImage(img_data, name=os.path.basename(image_path))
            img_part.add_header('Content-ID', f'<{cid}>')
            img_part.add_header('Content-Disposition', 'inline', filename=os.path.basename(image_path))
            root.attach(img_part)

        part_html = MIMEText(final_html, 'html', 'utf-8')
        alt.attach(part_html)

    # 发送邮件（根容器为 root）
    try:
        if EMAIL_SMTP_PORT == 465:
            with smtplib.SMTP_SSL(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
                server.login(EMAIL_USER, EMAIL_PASSWORD)
                server.send_message(root)
        else:
            with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PASSWORD)
                server.send_message(root)
        print("✅ 邮件发送成功")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
