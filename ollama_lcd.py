import serial
import time
import sounddevice as sd
from faster_whisper import WhisperModel
from ollama import Client

# -----------------------------
# SETTINGS
# -----------------------------

COM_PORT = "COM3"
BAUD_RATE = 115200

SAMPLE_RATE = 16000
RECORD_SECONDS = 5

OLLAMA_MODEL = "gemma:2b"

# -----------------------------
# CONNECT TO ARDUINO
# -----------------------------

arduino = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)

time.sleep(2)

print("Arduino connected.")

# -----------------------------
# CONNECT TO OLLAMA
# -----------------------------

client = Client(host="http://127.0.0.1:11434")

print("Loading Whisper...")

model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

print("Whisper ready.")
print("System ready.")

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

                response = client.chat(
                    model=OLLAMA_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an AI running on a "
                                "16x2 LCD. "
                                "Answer using 32 characters "
                                "and spaces "
                                "or fewer. "
                                "Never use emojis. "
                                "Never use line breaks. "
                                "Never use special "
                                "characters. "
                                "Be concise."
                                "Do not add Sure before "
                                "you answer. "
                            )
                        },
                        {
                            "role": "user",
                            "content": text
                        }
                    ]
                )

                answer = response.message.content

                answer = answer.replace("\n", " ")
                answer = answer.strip()

                # Hard limit for LCD
                answer = answer[:32]

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