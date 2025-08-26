import streamlit as st
import cv2
import numpy as np
from PIL import Image
import os
import sqlite3
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from openai import OpenAI
import base64
from io import BytesIO
import datetime

# === 環境変数読み込み ===
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("環境変数 OPENAI_API_KEY が見つかりません。設定してください。")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

# === DB初期化 ===
def init_db():
    conn = sqlite3.connect("photo_comments.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            composition TEXT,
            brightness TEXT,
            sharpness TEXT,
            gpt_comment TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# === DB保存 ===
def save_to_db(filename, comp, bright, sharp, gpt_comment):
    conn = sqlite3.connect("photo_comments.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO comments (filename, composition, brightness, sharpness, gpt_comment)
        VALUES (?, ?, ?, ?, ?)
    ''', (filename, comp, bright, sharp, gpt_comment))
    conn.commit()
    conn.close()

# === 評価関数 ===
def evaluate_brightness(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    avg = np.mean(gray)
    if avg > 180:
        return "この写真は明るめです。"
    elif avg < 70:
        return "この写真は暗めです。"
    else:
        return "この写真は適度な明るさです。"

def evaluate_sharpness(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    var = lap.var()
    if var < 100:
        return f"シャープさがやや足りません（ピントが甘い可能性）[分散={var:.2f}]"
    else:
        return f"シャープな印象です [分散={var:.2f}]"

def evaluate_composition(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    m = cv2.moments(gray)
    if m["m00"] != 0:
        cx = int(m["m10"] / m["m00"])
        cy = int(m["m01"] / m["m00"])
        h, w = gray.shape
        dx = abs(cx - w // 2) / w
        dy = abs(cy - h // 2) / h
        if dx < 0.1 and dy < 0.1:
            return "被写体が中央にあり、安定した構図です。"
        else:
            return "被写体が中心からずれていて、動きやバランスを感じます。"
    else:
        return "構図の解析ができませんでした。"

# === GPT講評 ===
def generate_natural_comment(comp, bright, sharp):
    prompt = f"""
以下の3つの要素から、写真全体の講評を日本語で自然に書いてください。

- 構図評価: {comp}
- 明暗評価: {bright}
- シャープさ評価: {sharp}

写真全体について、感想や印象、雰囲気を自然な文でまとめてください。
"""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300
    )
    return response.choices[0].message.content.strip()

# === Base64エンコード（画像）===
def encode_image(image):
    image.thumbnail((1024, 1024))
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

# === HTML & PDF保存 ===
def save_html_and_pdf(image_base64, comp, bright, sharp, comment, filename):
    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("report_template.html")

    html_content = template.render(
        image_base64=image_base64,
        composition=comp,
        brightness=bright,
        sharpness=sharp,
        comment=comment
    )

    html_path = f"{filename}_講評.html"
    pdf_path = f"{filename}_講評.pdf"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    HTML(string=html_content).write_pdf(pdf_path)
    return html_path, pdf_path

# === 保存されたコメント読み込み ===
def load_all_comments():
    conn = sqlite3.connect("photo_comments.db")
    c = conn.cursor()
    c.execute("SELECT id, filename, composition, brightness, sharpness, gpt_comment, timestamp FROM comments ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# === Streamlit UI ===
def main():
    st.set_page_config(page_title="写真の先生", layout="wide")
    st.title("📷 写真の先生")
    st.write("画像をアップロードして評価・講評を得ましょう。")

    init_db()

    uploaded = st.file_uploader("画像をアップロード", type=["jpg", "jpeg", "png"])
    if uploaded:
        image = Image.open(uploaded).convert("RGB")
        image_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        comp = evaluate_composition(image_bgr)
        bright = evaluate_brightness(image_bgr)
        sharp = evaluate_sharpness(image_bgr)
        comment = generate_natural_comment(comp, bright, sharp)

        st.image(image, caption="アップロード画像", use_column_width=True)
        st.subheader("📝 評価")
        st.write(comp)
        st.write(bright)
        st.write(sharp)

        st.subheader("🤖 GPTによる講評")
        st.write(comment)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{os.path.splitext(uploaded.name)[0]}_{timestamp}"
        image_base64 = encode_image(image)

        if st.button("📄 HTML/PDFに保存"):
            html_path, pdf_path = save_html_and_pdf(
                image_base64, comp, bright, sharp, comment, filename)
            st.success(f"保存完了: {html_path}, {pdf_path}")

        if st.button("💾 データベースに保存"):
            save_to_db(filename, comp, bright, sharp, comment)
            st.success("データベースに保存しました。")

    # 保存済み講評の表示
    if st.sidebar.button("📂 保存済み講評を表示"):
        st.markdown("## 🗂 保存された講評一覧")
        records = load_all_comments()
        if records:
            for row in records:
                st.markdown("---")
                st.write(f"📄 ファイル名: {row[1]}")
                st.write(f"🕒 日時: {row[6]}")
                st.write("📝 構図:", row[2])
                st.write("💡 明るさ:", row[3])
                st.write("🔍 シャープさ:", row[4])
                st.write("🤖 GPT講評:", row[5])
        else:
            st.info("保存された講評はまだありません。")

if __name__ == "__main__":
    main()
