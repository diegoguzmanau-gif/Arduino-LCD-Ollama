#include <Wire.h>
#include "Waveshare_LCD1602.h"
#include <Servo.h>

// --- LCD (Waveshare I2C, AiP31068L chip) ---
Waveshare_LCD1602 lcd(16, 2);

// --- BUTTON (triggers voice assistant via Python) ---
const int BUTTON_PIN = 8;

// --- SERVO ---
// Signal -> pin 9
// Power (red) -> second Arduino's 5V, GND tied to BOTH boards' GND
Servo screenServo;
const int servoPin = 9;

const int CENTER_ANGLE = 90;
const int SWEEP_MIN = 30;
const int SWEEP_MAX = 150;
const unsigned long SWEEP_STEP_DELAY = 30; // ms per degree (higher = slower sweep)

// --- TIMING (all tunable) ---
const unsigned long SETUP_DURATION = 80000UL;  // 1:20 startup timer
const unsigned long LISTEN_TIME    = 5000UL;   // matches RECORD_SECONDS in Python
const unsigned long THINK_TIMEOUT  = 60000UL;  // give up waiting for an answer after this

// --- STATE MACHINE ---
enum State { STATE_SETUP, STATE_READY, STATE_LISTENING, STATE_THINKING, STATE_ANSWER };
State state = STATE_SETUP;

unsigned long stateStart = 0;
int lastCountdownShown = -1;

// Servo sweep tracking
int sweepAngle = CENTER_ANGLE;
int sweepDirection = 1;
unsigned long lastSweepStep = 0;

// Button tracking
bool wasPressed = false;
unsigned long lastPressTime = 0;

// ---------------------------------------------------------
// Helpers
// ---------------------------------------------------------

void showText(const char* line1, const char* line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.send_string(line1);
  lcd.setCursor(0, 1);
  lcd.send_string(line2);
}

void setState(State newState) {
  state = newState;
  stateStart = millis();
}

void lookStraight() {
  screenServo.write(CENTER_ANGLE);
  sweepAngle = CENTER_ANGLE;
}

void updateIdleSweep() {
  unsigned long now = millis();
  if (now - lastSweepStep >= SWEEP_STEP_DELAY) {
    lastSweepStep = now;

    sweepAngle += sweepDirection;

    if (sweepAngle >= SWEEP_MAX) {
      sweepAngle = SWEEP_MAX;
      sweepDirection = -1;
    }
    else if (sweepAngle <= SWEEP_MIN) {
      sweepAngle = SWEEP_MIN;
      sweepDirection = 1;
    }

    screenServo.write(sweepAngle);
  }
}

void showAnswer(String text) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.send_string(text.substring(0, 16).c_str());

  if (text.length() > 16) {
    lcd.setCursor(0, 1);
    lcd.send_string(text.substring(16, 32).c_str());
  }
}

// ---------------------------------------------------------
// Setup
// ---------------------------------------------------------

void setup() {
  Serial.begin(115200);

  pinMode(BUTTON_PIN, INPUT_PULLUP);

  screenServo.attach(servoPin);
  lookStraight();

  lcd.init();
  showText("Setting up...", "Ready in 1:20");

  setState(STATE_SETUP);
}

// ---------------------------------------------------------
// Main loop
// ---------------------------------------------------------

void loop() {
  unsigned long now = millis();

  // -------------------------
  // BUTTON (edge detection, non-blocking)
  // -------------------------
  bool pressed = (digitalRead(BUTTON_PIN) == LOW);
  bool buttonEdge = pressed && !wasPressed && (now - lastPressTime > 200);
  if (buttonEdge) lastPressTime = now;
  wasPressed = pressed;

  // -------------------------
  // INCOMING SERIAL FROM PYTHON (the AI answer)
  // -------------------------
  if (Serial.available()) {
    String message = Serial.readStringUntil('\n');
    message.trim();

    // Ignore anything that arrives during startup
    if (state != STATE_SETUP && message.length() > 0) {
      showAnswer(message);
      setState(STATE_ANSWER);
    }
  }

  // -------------------------
  // STATE LOGIC
  // -------------------------
  switch (state) {

    case STATE_SETUP: {
      unsigned long elapsed = now - stateStart;

      if (elapsed >= SETUP_DURATION) {
        showText("Ready for", "user input");
        setState(STATE_READY);
      }
      else {
        // Update the countdown once per second
        int remaining = (SETUP_DURATION - elapsed + 999) / 1000; // seconds, rounded up
        if (remaining != lastCountdownShown) {
          lastCountdownShown = remaining;
          char line2[17];
          snprintf(line2, sizeof(line2), "Ready in %d:%02d   ", remaining / 60, remaining % 60);
          lcd.setCursor(0, 1);
          lcd.send_string(line2);
        }
        updateIdleSweep();
      }
      break;
    }

    case STATE_READY:
    case STATE_ANSWER:
      updateIdleSweep();

      if (buttonEdge) {
        lookStraight();
        showText("Listening...", "");
        Serial.println("BUTTON_PRESSED");
        setState(STATE_LISTENING);
      }
      break;

    case STATE_LISTENING:
      // Servo stays straight; after the recording window, switch to "Thinking"
      if (now - stateStart >= LISTEN_TIME) {
        showText("Thinking...", "");
        setState(STATE_THINKING);
      }
      break;

    case STATE_THINKING:
      // Servo stays straight until an answer arrives (handled in the serial block above)
      if (now - stateStart >= THINK_TIMEOUT) {
        showText("No response", "Is Python on?");
        setState(STATE_ANSWER);
      }
      break;
  }
}
