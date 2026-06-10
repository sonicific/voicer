from TTS.api import TTS

tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")

tts.tts_to_file(
    text="Hello world from Coqui TTS",
    file_path="coqui.wav"
)
