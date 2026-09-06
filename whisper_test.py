import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
RECORD_SECONDS = 5

print("Loading Whisper...")
model = WhisperModel("base", device="cpu", compute_type="int8")

print("Ready.")
print("Speak for 5 seconds...")

audio = sd.rec(
    int(RECORD_SECONDS * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32"
)

sd.wait()

audio = audio.flatten()

print("Transcribing...")

segments, info = model.transcribe(
    audio,
    language="en"
)

text = ""

for segment in segments:
    text += segment.text

print("You said:")
print(text.strip())