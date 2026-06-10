# import pyttsx3

# engine = pyttsx3.init()

# engine.setProperty('rate', 150)   # tốc độ
# engine.setProperty('volume', 1.0) # âm lượng

# voices = engine.getProperty('voices')
# engine.setProperty('voice', voices[0].id)  # đổi giọng

# engine.say("Xin chào")
# engine.runAndWait()

# engine.save_to_file("Xin chào, đây là pyttsx3", "pyttsx3.mp3")
# engine.runAndWait()



import pyttsx3
import os

# =========================
# KHỞI TẠO ENGINE
# =========================
engine = pyttsx3.init()

# =========================
# THÔNG TIN ENGINE
# =========================
print("Driver:", engine)

# =========================
# LẤY DANH SÁCH VOICES
# =========================
voices = engine.getProperty("voices")

print("\n===== DANH SÁCH GIỌNG =====")

for index, voice in enumerate(voices):
    print(f"""
[{index}]
ID      : {voice.id}
Name    : {voice.name}
Gender  : {getattr(voice, 'gender', 'Unknown')}
Langs   : {getattr(voice, 'languages', 'Unknown')}
""")

# =========================
# CHỌN GIỌNG
# =========================
# Thử chọn giọng tiếng Việt nếu có
selected_voice = voices[1]

for voice in voices:
    name = voice.name.lower()

    if "vietnam" in name or "vi" in name:
        selected_voice = voice.id
        break

# Nếu không có thì lấy voice đầu tiên
if selected_voice is None:
    selected_voice = voices[0].id

engine.setProperty("voice", selected_voice)

# =========================
# TỐC ĐỘ ĐỌC
# =========================
# Mặc định khoảng 200
engine.setProperty("rate", 150)

# =========================
# ÂM LƯỢNG
# =========================
# 0.0 -> 1.0
engine.setProperty("volume", 1.0)

# =========================
# TEXT TO SPEECH
# =========================
text = """
Hello world! This is a test of the pyttsx3 text-to-speech library. It allows you to convert text into spoken words using different voices and settings. You can adjust the speed, volume, and even choose from various available voices on your system. This makes it a great tool for creating audio content or adding speech capabilities to your applications.
"""

engine.say(text)

# =========================
# SAVE FILE
# =========================
# pyttsx3 thường hỗ trợ WAV tốt hơn MP3
output_file = "output.wav"

engine.save_to_file(text, output_file)

# Chạy queue
engine.runAndWait()

# =========================
# KIỂM TRA FILE
# =========================
if os.path.exists(output_file):
    print(f"\nĐã lưu file: {output_file}")
else:
    print("\nKhông tạo được file.")


# 1. Lấy tốc độ hiện tại
# rate = engine.getProperty('rate')
# print(rate)
# 2. Lấy âm lượng hiện tại
# volume = engine.getProperty('volume')
# print(volume)
# 3. Dừng nói
# engine.stop()
# 4. Queue nhiều câu
# engine.say("Xin chào")
# engine.say("Tôi là AI")
# engine.say("Rất vui được gặp bạn")

# engine.runAndWait()
# 5. Callback events
# def on_start(name):
#     print("Bắt đầu:", name)

# def on_end(name, completed):
#     print("Kết thúc:", name)

# engine.connect('started-utterance', on_start)
# engine.connect('finished-utterance', on_end)
