# Voice Studio Pro

GUI PySide6 tao voice da provider cho project nay.

## Chay tool

```powershell
python voice_studio_qt.py
```

Hoac double click `run_voice_studio.bat` tren Windows.

`python voice_studio.py` van hoat dong va se uu tien mo GUI PySide6. Ban Tkinter cu duoc giu lam fallback.

## Provider

- `Microsoft Edge TTS`: dung logic tu `edge-tts.py`, xuat `.mp3`, ho tro voice/rate/volume/pitch.
- `Google gTTS`: dung logic chia text va ghep audio tu `gtts.py`, xuat `.mp3`, ho tro lang/accent domain/slow/lang check/timeout/chunk size.
- `Piper Local`: dung logic tu `piper-voice.py`, can file model `.onnx`, xuat `.wav`, ho tro config/speaker/length/noise/silence/CUDA.
- `Coqui TTS`: dung logic tu `tts.py`, chon model/vocoder/speaker/language/voice cloning wav/device va xuat `.wav`.
- `System pyttsx3`: dung logic tu `ttsx.py`, chon driver/voice index/rate/volume, xuat `.wav`.
- `Supertonic`: dung logic tu `sptn.py`, chon voice/lang/quality/speed/expression tag, xuat `.wav`.

## Preview audio

- Bat `Auto play` de nghe ngay sau khi generate xong.
- Bam `Play` de nghe lai file output hien tai.
- Bam `Pause` / `Stop` de dieu khien playback trong app.
- Bam `Preview Voice` de nghe nhanh giong dang chon voi cau mau ngan.
- Bam `Open Folder` de mo thu muc chua file audio.

## Voice va export

- `Favorite Voice` luu giong doc yeu thich theo tung provider va dua len dau danh sach khi mo lai.
- `Format` cho phep giu dinh dang mac dinh cua provider hoac xuat MP3/WAV/OGG.
- `Bitrate` ap dung cho MP3/OGG khi dung ffmpeg.
- `Merge text lines` render tung dong khong rong thanh mot doan rieng roi ghep thanh mot file.
- Doi dinh dang va ghep nhieu doan can `ffmpeg` co trong PATH.

## Workflow nang cao

- `History` tu dong luu 30 file gan nhat; double click mot item de nghe lai.
- `Save Preset` luu settings hien tai theo tung provider.
- `Load Preset` khoi phuc settings da luu cho provider dang chon.
- Text panel hien so ky tu va so tu de canh do dai noi dung truoc khi generate.

## Luu y

Moi provider can package Python rieng. Neu provider nao bao loi `No module named ...`,
hay cai package tuong ung trong virtual environment cua project. Piper can model local
`.onnx`; chon file model trong giao dien truoc khi generate.

GUI moi can `PySide6`. Moi truong hien tai da co san PySide6 6.11.1.

## Docs tham khao

- Edge TTS: https://github.com/rany2/edge-tts
- gTTS: https://gtts.readthedocs.io/en/latest/module.html
- Piper: https://github.com/rhasspy/piper
- Coqui TTS: https://docs.coqui.ai/en/latest/inference.html
- pyttsx3: https://pyttsx3.readthedocs.io/en/latest/engine.html
- Supertonic: https://github.com/supertone-inc/supertonic
