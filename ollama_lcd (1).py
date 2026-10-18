import re
import time
import serial
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

# Models that should fit a 4GB Windows 10 machine (sizes are approximate):
#   "qwen3:1.7b"  ~1.4GB  best instruction following at this size
#   "gemma2:2b"   ~1.6GB  good general knowledge
#   "gemma3:1b"   ~0.8GB  safest fit if memory is very tight
# Run model_test.py to see which one works best on YOUR machine.
OLLAMA_MODEL = "qwen3:1.7b"

LCD_MAX_CHARS = 32          # 16x2 screen
TARGET_CHARS = 28           # aim below the limit, small models overshoot
MAX_ATTEMPTS = 3            # how many times to ask for a shorter answer
KEEP_ALIVE = -1             # never unload the model (default is 5 minutes)
NUM_CTX = 1024              # small context window = less RAM used by the model

# These models "think" out loud by default, which we don't want
THINKING_MODELS = ("qwen3", "deepseek-r1")

client = Client(host="http://127.0.0.1:11434")

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
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)   # safety net for thinking models
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


def chat(messages):
    kwargs = dict(
        model=OLLAMA_MODEL,
        messages=messages,
        keep_alive=KEEP_ALIVE,
        options={"temperature": 0.2, "num_predict": 24, "num_ctx": NUM_CTX}
    )
    if OLLAMA_MODEL.startswith(THINKING_MODELS):
        kwargs["think"] = False    # needs a recent ollama package: pip install -U ollama
    return client.chat(**kwargs)


def ask_ollama(question):
    messages = build_messages(question)
    answer = ""

    for attempt in range(MAX_ATTEMPTS):
        response = chat(messages)

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


def warm_up_ollama():
    print(f"Warming up Ollama with {OLLAMA_MODEL} (this can take a while)...")
    print("Test answer:", ask_ollama("What color is the sky?"))

# -----------------------------
# MAIN
# -----------------------------

def main():

    # Connect to Arduino
    arduino = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)

    time.sleep(2)

    print("Arduino connected.")

    # Load Whisper
    print("Loading Whisper...")

    model = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8"
    )

    print("Whisper loaded.")

    # Warm up everything so the first real question isn't slow
    print("Warming up Whisper...")
    silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
    warm_segments, _ = model.transcribe(silence, language="en")
    list(warm_segments)  # segments are lazy, this forces the run

    warm_up_ollama()

    print("System ready.")

    # Tell the Arduino to leave the "Setting up" screen
    arduino.write(b"SYSTEM_READY\n")

    # Main loop
    while True:

        if arduino.in_waiting:

            command = arduino.readline().decode(
                "utf-8",
                errors="ignore"
            ).strip()

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

                segments, info = model.transcribe(
                    audio,
                    language="en"
                )

                text = ""

                for segment in segments:
                    text += segment.text

                text = text.strip()

                print("You:", text)

                if text:

                    print("Asking Ollama...")

                    try:
                        answer = ask_ollama(text)
                    except Exception as e:
                        print("Ollama error:", e)
                        answer = "AI error"

                    print("AI:", answer)

                    arduino.write(
                        (answer + "\n").encode("utf-8")
                    )

                else:

                    print("No speech detected.")

                    arduino.write(
                        b"No speech detected\n"
                    )


if __name__ == "__main__":
    main()
