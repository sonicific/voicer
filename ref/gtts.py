from ref.gtts import gTTS
import os
import re

def clean_text(text: str) -> str:
    """Làm sạch text trước khi đưa vào TTS"""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def split_text(text: str, max_chars=200):
    """
    gTTS giới hạn độ dài → phải chia nhỏ
    """
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current = ""

    for s in sentences:
        if len(current) + len(s) <= max_chars:
            current += " " + s
        else:
            chunks.append(current.strip())
            current = s

    if current:
        chunks.append(current.strip())

    return chunks


def text_to_speech(
    text,
    lang="vi",
    slow=False,
    output="output.mp3"
):
    """
    Full option:
    - lang: ngôn ngữ
    - slow: đọc chậm
    - auto split text dài
    """

    text = clean_text(text)
    chunks = split_text(text)

    temp_files = []

    for i, chunk in enumerate(chunks):
        tts = gTTS(
            text=chunk,
            lang=lang,
            slow=slow
        )

        filename = f"temp_{i}.mp3"
        tts.save(filename)
        temp_files.append(filename)

    # merge file
    with open(output, "wb") as final:
        for f in temp_files:
            with open(f, "rb") as part:
                final.write(part.read())

    # cleanup
    for f in temp_files:
        os.remove(f)

    print(f"✅ Done: {output}")


# ======================
# 🔥 TEST
# ======================
if __name__ == "__main__":
    text = """
    Xin chào, đây là demo chuyển văn bản thành giọng nói tiếng Việt bằng gTTS.
    Bạn có thể nhập văn bản dài, hệ thống sẽ tự động chia nhỏ và ghép lại.
    """

    text_to_speech(
        text=text,
        lang="vi",
        slow=False,
        output="gtts.mp3"
    )
