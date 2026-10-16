import re
import serial
import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from ollama import Client

# -----------------------------
# SETTINGS
# -----------------------------

COM_PORT = "COM3"
BAUD_RATE = 115200

SAMPLE_RATE = 16000
RECORD_SECONDS = 5          # keep in sync with LISTEN_TIME in the Arduino sketch

OLLAMA_MODEL = "gemma:2b"

LCD_MAX_CHARS = 32          # 16x2 screen
TARGET_CHARS = 28           # aim below the limit, small models overshoot
MAX_ATTEMPTS = 3            # how many times to ask for a shorter answer
KEEP_ALIVE = -1             # never unload the model (default is 5 minutes)

# -----------------------------
# PROMPT
# -----------------------------

SYSTEM_PROMPT = (
    "You are a robot with a tiny screen that fits 28 characters. "
    "Reply with ONLY the answer, as short as possible: one to four words, "
    "never a full sentence. "
    "Never repeat the question. "
    "Never start with 'The answer is' or 'Sure'. "
    "No emojis, no special characters, no line breaks."
)

# Small models copy examples much better than they follow rules
EXAMPLES = [
    ("What is the biggest animal on earth?", "Blue whale"),
    ("What is the capital of France?", "Paris"),
    ("How many legs does a spider have?", "8"),
    ("What is 6 plus 7?", "13"),
    ("Who wrote Hamlet?", "Shakespeare"),
    ("Why is the sky blue?", "Light scattering"),
]

# -----------------------------
# HELPERS
# -----------------------------

def clean_answer(text):
    text = text.replace("\n", " ")
    text = text.encode("ascii", "ignore").decode()      # LCD can't show emojis/accents
    text = re.sub(r'[*_`#"]', "", text)                 # markdown and quotes
    text = re.sub(r"^(sure|okay|ok)[,!.:]?\s+", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def trim_to_lcd(text):
    """Last resort: cut at a word boundary instead of mid-word."""
    if len(text) <= LCD_MAX_CHARS:
        return text
    cut = text[:LCD_MAX_CHARS]
    if text[LCD_MAX_CHARS] != " " and " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" ,;:-")


def build_messages(question):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for q, a in EXAMPLES:
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": question})
    return messages


def ask_ollama(question):
    messages = build_messages(question)
    answer = ""

    for attempt in range(MAX_ATTEMPTS):
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            keep_alive=KEEP_ALIVE,
            options={"temperature": 0.2, "num_predict": 24}
        )

        answer = clean_answer(response.message.content)

        if answer and len(answer) <= LCD_MAX_CHARS:
            return answer

        print(f"  Too long ({len(answer)} chars), asking again...")

        if answer:
            messages.append({"role": "assistant", "content": answer})
        messages.append({
            "role": "user",
            "content": f"Too long. Answer again in {TARGET_CHARS} characters or fewer. Just the answer."
        })

    return trim_to_lcd(answer) if answer else "Not sure"

# -----------------------------
# CONNECT TO ARDUINO
# -----------------------------

arduino = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)

time.sleep(2)

print("Arduino connected.")

# -----------------------------
# LOAD MODELS
# -----------------------------

client = Client(host="http://127.0.0.1:11434")

print("Loading Whisper...")

model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

print("Whisper loaded.")

# -----------------------------
# WARM UP (so the first real question isn't slow)
# -----------------------------

print("Warming up Whisper...")
silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
warm_segments, _ = model.transcribe(silence, language="en")
list(warm_segments)  # segments are lazy, this forces the run

print("Warming up Ollama (loading the model, this can take a while)...")
print("Test answer:", ask_ollama("What color is the sky?"))

print("System ready.")

# Tell the Arduino to leave the "Setting up" screen
arduino.write(b"SYSTEM_READY\n")

# -----------------------------
# MAIN LOOP
# -----------------------------

while True:

    if arduino.in_waiting:

        command = arduino.readline().decode(
            "utf-8",
            errors="ignore"
        ).strip()

        # -------------------------
        # BUTTON PRESSED
        # -------------------------

        if command == "BUTTON_PRESSED":

            print("Listening...")

            # Record microphone
            audio = sd.rec(
                int(RECORD_SECONDS * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32"
            )

            sd.wait()

            audio = audio.flatten()

            print("Transcribing...")

            # Whisper
            segments, info = model.transcribe(
                audio,
                language="en"
            )

            text = ""

            for segment in segments:
                text += segment.text

            text = text.strip()

            print("You:", text)

            # -------------------------
            # SEND TO OLLAMA
            # -------------------------

            if text:

                print("Asking Ollama...")

                try:
                    answer = ask_ollama(text)
                except Exception as e:
                    print("Ollama error:", e)
                    answer = "AI error"

                print("AI:", answer)

                # Send answer to Arduino
                arduino.write(
                    (answer + "\n").encode("utf-8")
                )

            else:

                print("No speech detected.")

                arduino.write(
                    b"No speech detected\n"
                )
