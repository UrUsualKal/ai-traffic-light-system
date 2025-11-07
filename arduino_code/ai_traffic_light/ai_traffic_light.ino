// Traffic Light A (AI-controlled)
const int A_RED_PIN = 2;
const int A_YELLOW_PIN = 3;
const int A_GREEN_PIN = 4;

// Traffic Light B (Opposite)
const int B_RED_PIN = 5;
const int B_YELLOW_PIN = 6;
const int B_GREEN_PIN = 7;

// Buzzer for high traffic alerts only
const int BUZZER_PIN = 8;

String command = "";
String lastCommand = ""; // Store last command to detect changes

void setup() {
  Serial.begin(9600);
  
  // Initialize Traffic Light A pins
  pinMode(A_RED_PIN, OUTPUT);
  pinMode(A_YELLOW_PIN, OUTPUT);
  pinMode(A_GREEN_PIN, OUTPUT);
  
  // Initialize Traffic Light B pins
  pinMode(B_RED_PIN, OUTPUT);
  pinMode(B_YELLOW_PIN, OUTPUT);
  pinMode(B_GREEN_PIN, OUTPUT);
  
  // Initialize buzzer
  pinMode(BUZZER_PIN, OUTPUT);
  
  // Start with all lights off
  turnOffAllLights();
  
  // Initial startup sequence
  startupSequence();
  
  Serial.println("Dual Traffic Light Controller Ready");
  Serial.println("Command format: A[R/Y/G]B[R/Y/G] or A[R/Y/G]B[R/Y/G]H (high traffic)");
  Serial.println("Example: AGBR = Traffic A Green, Traffic B Red");
  Serial.println("Example: ARBGH = Traffic A Red, Traffic B Green + HIGH TRAFFIC ALERT");
}

void loop() {
  if (Serial.available()) {
    command = Serial.readStringUntil('\n');
    command.trim(); // Remove whitespace
    
    // Check for high traffic alert (commands ending with 'H')
    bool highTrafficAlert = command.endsWith("H");
    if (highTrafficAlert) {
      command.remove(command.length() - 1); // Remove the 'H' flag
    }
    
    // Parse command format: A[R/Y/G]B[R/Y/G]
    // Example: "AGBR" = A=Green, B=Red
    if (command.length() == 4 && command.charAt(0) == 'A' && command.charAt(2) == 'B') {
      
      // Check if this is a new command (different from last)
      bool isNewCommand = (command != lastCommand);
      
      if (isNewCommand || highTrafficAlert) {
        char lightA = command.charAt(1);
        char lightB = command.charAt(3);
        
        // Set Traffic Light A
        setTrafficLight('A', lightA);
        
        // Set Traffic Light B
        setTrafficLight('B', lightB);
        
        if (highTrafficAlert) {
          Serial.print("HIGH TRAFFIC ALERT - Traffic A: ");
          Serial.print(getLightName(lightA));
          Serial.print(", Traffic B: ");
          Serial.println(getLightName(lightB));
          
          // Special high traffic buzzer alert
          playHighTrafficAlert();
        } else {
          Serial.print("CHANGED - Traffic A: ");
          Serial.print(getLightName(lightA));
          Serial.print(", Traffic B: ");
          Serial.println(getLightName(lightB));
          
          // No buzzer for normal changes
        }
        
        // Update last command
        lastCommand = command;
      } else {
        // Same command as before - no buzzer, just acknowledge
        Serial.println("Same state - No change needed");
      }
    }
    // Handle standalone high traffic alert
    else if (command == "H") {
      Serial.println("HIGH TRAFFIC ALERT - Current state");
      playHighTrafficAlert();
    }
    else if (command == "OFF") {
      if (lastCommand != "OFF") {
        turnOffAllLights();
        Serial.println("All lights OFF");
        // No buzzer for OFF command
        lastCommand = "OFF";
      }
    }
    else if (command == "TEST") {
      testSequence();
      lastCommand = "TEST"; // Prevent repeated test sequences
    }
    else {
      Serial.println("Unknown command: " + command);
      Serial.println("Use format: A[R/Y/G]B[R/Y/G] (e.g., AGBR)");
      Serial.println("Or with high traffic alert: A[R/Y/G]B[R/Y/G]H (e.g., ARBGH)");
    }
  }
}

void setTrafficLight(char traffic, char color) {
  int redPin, yellowPin, greenPin;
  
  // Select pins based on traffic light
  if (traffic == 'A') {
    redPin = A_RED_PIN;
    yellowPin = A_YELLOW_PIN;
    greenPin = A_GREEN_PIN;
  } else if (traffic == 'B') {
    redPin = B_RED_PIN;
    yellowPin = B_YELLOW_PIN;
    greenPin = B_GREEN_PIN;
  } else {
    return; // Invalid traffic light
  }
  
  // Turn off all colors for this traffic light first
  digitalWrite(redPin, LOW);
  digitalWrite(yellowPin, LOW);
  digitalWrite(greenPin, LOW);
  
  // Set the requested color
  switch (color) {
    case 'R':
      digitalWrite(redPin, HIGH);
      break;
    case 'Y':
      digitalWrite(yellowPin, HIGH);
      break;
    case 'G':
      digitalWrite(greenPin, HIGH);
      break;
  }
}

void turnOffAllLights() {
  digitalWrite(A_RED_PIN, LOW);
  digitalWrite(A_YELLOW_PIN, LOW);
  digitalWrite(A_GREEN_PIN, LOW);
  digitalWrite(B_RED_PIN, LOW);
  digitalWrite(B_YELLOW_PIN, LOW);
  digitalWrite(B_GREEN_PIN, LOW);
}

void playHighTrafficAlert() {
  // Special alert pattern for high traffic mode
  // Three urgent beeps with increasing pitch
  for (int i = 0; i < 3; i++) {
    tone(BUZZER_PIN, 800 + (i * 200), 300);
    delay(400);
  }
  
  // Final warning tone
  tone(BUZZER_PIN, 1500, 500);
}

String getLightName(char color) {
  switch (color) {
    case 'R': return "RED";
    case 'Y': return "YELLOW";
    case 'G': return "GREEN";
    default: return "UNKNOWN";
  }
}

void startupSequence() {
  Serial.println("Starting up...");
  
  // Test Traffic Light A
  setTrafficLight('A', 'R');
  delay(300);
  setTrafficLight('A', 'Y');
  delay(300);
  setTrafficLight('A', 'G');
  delay(300);
  
  // Test Traffic Light B
  setTrafficLight('B', 'R');
  delay(300);
  setTrafficLight('B', 'Y');
  delay(300);
  setTrafficLight('B', 'G');
  delay(300);
  
  turnOffAllLights();
  delay(500);
  
  // Flash both
  for (int i = 0; i < 2; i++) {
    setTrafficLight('A', 'G');
    setTrafficLight('B', 'R');
    delay(200);
    setTrafficLight('A', 'R');
    setTrafficLight('B', 'G');
    delay(200);
  }
  
  // End with A=Red, B=Green (default state - no cars detected)
  setTrafficLight('A', 'R');
  setTrafficLight('B', 'G');
  
  // Startup sound - single beep only
  tone(BUZZER_PIN, 1000, 200);
}

void testSequence() {
  Serial.println("Running test sequence...");
  
  // Test all combinations
  String tests[] = {"ARBG", "AYBG", "AGBR", "AYBY", "ARBR"};
  
  for (int i = 0; i < 5; i++) {
    Serial.println("Testing: " + tests[i]);
    
    char lightA = tests[i].charAt(1);
    char lightB = tests[i].charAt(3);
    
    setTrafficLight('A', lightA);
    setTrafficLight('B', lightB);
    
    delay(1000);
  }
  
  // Test high traffic alert
  Serial.println("Testing high traffic alert...");
  playHighTrafficAlert();
  delay(1000);
  
  // Return to default (no cars detected)
  setTrafficLight('A', 'R');
  setTrafficLight('B', 'G');
  Serial.println("Test complete - returned to default state (cross traffic)");
}