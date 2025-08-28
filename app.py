import streamlit as st
import openai
from PIL import Image
import io

# ✅ APIキーをSecretsから取得
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="写真の先生", layout="centered")
st.title("📷 写真の先生")
st.write("あなたの写真をAIが講評します！")

# ✅ 画像アップロード
uploaded_image = st.file_uploader("写真をアップロードしてください", type=["jpg", "jpeg", "png"])

# ✅ 評価項目を選択
st.subheader("評価オプション")
composition = st.checkbox("構図")
brightness = st.checkbox("明暗")
sharpness = st.checkbox("シャープさ")
emotion = st.checkbox("感情・雰囲気")

# ✅ アクション
if uploaded_image and st.button("講評を生成"):
    with st.spinner("AIが講評を作成中..."):
        image = Image.open(uploaded_image)
        st.image(image, caption="アップロードした写真", use_column_width=True)

        # ✅ 評価リスト
        evaluation_points = []
        if composition: evaluation_points.append("構図")
        if brightness: evaluation_points.append("明暗")
        if sharpness: evaluation_points.append("シャープさ")
        if emotion: evaluation_points.append("感情や雰囲気")

        evaluation_text = "、".join(evaluation_points) if evaluation_points else "全体"

        # ✅ OpenAIで講評生成
        prompt = f"""
あなたは写真評論家です。
以下の観点から、写真を丁寧に日本語で講評してください：
{evaluation_text}
さらに、感じたことや、良い改善点を提案してください。
"""
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "あなたは優秀な写真評論家です。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        commentary = response["choices"][0]["message"]["content"]
        st.subheader("AIによる講評")
        st.write(commentary)

        # ✅ PDFダウンロード対応
        pdf_bytes = io.BytesIO()
        pdf_bytes.write(commentary.encode('utf-8'))
        pdf_bytes.seek(0)
        st.download_button("講評をダウンロード (TXT形式)", data=pdf_bytes, file_name="photo_review.txt")
