from piper import PiperVoice

voice = PiperVoice.load("en_US-lessac-medium.onnx")

with open("piper.wav", "wb") as f:
    voice.synthesize("Hello from Piper", f)
