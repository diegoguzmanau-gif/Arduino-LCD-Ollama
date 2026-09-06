#include <LiquidCrystal.h>
#include <Servo.h>

// LCD: RS, E, D4, D5, D6, D7
LiquidCrystal lcd(7, 6, 5, 4, 3, 2);

const int BUTTON_PIN = 8;

// --- SOUND LOCATOR (4-pin LM393 sensors) ---
// Each sensor: + -> 5V, G -> GND, A0 -> Arduino analog pin, D0 unused
const int leftMic   = A0;
const int centerMic = A1;
const int rightMic  = A2;
int soundThreshold = 200; // tune based on your Serial Monitor testing

// --- SERVO ---
// Signal -> pin 9
// Power (red) -> external power (your second Arduino), NOT this board's 5V
// GND -> tied to BOTH the power source's GND AND this board's GND
Servo screenServo;
const int servoPin = 9;

String message = "";

void setup() {
  Serial.begin(115200);

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(leftMic, INPUT);
  pinMode(centerMic, INPUT);
  pinMode(rightMic, INPUT);

  screenServo.attach(servoPin);
  screenServo.write(90); // start centered

  lcd.begin(16, 2);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Diego Guzman");
  lcd.setCursor(0, 1);
  lcd.print("Ts took too long");
}

void loop() {

  // -------------------------
  // BUTTON / LCD / SERIAL LOGIC (unchanged from your working version)
  // -------------------------
  if (digitalRead(BUTTON_PIN) == LOW) {

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Listening...");

    Serial.println("BUTTON_PRESSED");

    while (digitalRead(BUTTON_PIN) == LOW) {
      delay(10);
    }

    Serial.println("BUTTON_RELEASED");

    delay(100);
  }

  if (Serial.available()) {

    message = Serial.readStringUntil('\n');
    message.trim();

    if (message.length() > 0) {

      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print(message.substring(0, 16));

      if (message.length() > 16) {
        lcd.setCursor(0, 1);
        lcd.print(message.substring(16, 32));
      }
    }
  }

  // -------------------------
  // SOUND LOCATOR + SERVO (non-blocking, runs every loop)
  // -------------------------
  int leftVal   = analogRead(leftMic);
  int centerVal = analogRead(centerMic);
  int rightVal  = analogRead(rightMic);

  if (leftVal > soundThreshold || centerVal > soundThreshold || rightVal > soundThreshold) {

    if (leftVal > centerVal && leftVal > rightVal) {
      screenServo.write(30);    // turn toward left
    }
    else if (rightVal > leftVal && rightVal > centerVal) {
      screenServo.write(150);   // turn toward right
    }
    else {
      screenServo.write(90);    // center
    }
  }
}
