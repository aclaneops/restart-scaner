/*
 * =====================================================================
 * SCANNER HARDWARE RESTARTER & POWER CONTROLLER
 * Target Board : Arduino Mega 2560 (bisa juga Uno / Nano)
 * Device Target: Scanner Adapter 5V DC via 1-Channel Relay
 * Pin Control  : Digital Pin 7
 * =====================================================================
 * 
 * Skema Relay (Tipe Active-LOW):
 * - LOW  = Relay ON  (Kontak NC terbuka -> Power Scanner MATI / CUT)
 * - HIGH = Relay OFF (Kontak NC tertutup -> Power Scanner NYALA / IDLE)
 */

const int RELAY_PIN = 7;

// Logika Active-LOW
const int RELAY_CUT_POWER = LOW;   // Memutus arus (relay aktif)
const int RELAY_SUPPLY_POWER = HIGH; // Mengalirkan arus (relay idle/mati)

bool isPowerCut = false;
unsigned long restartTimerStart = 0;
unsigned long restartDuration = 0;
bool isRestarting = false;

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  // Default: Pastikan power scanner dalam kondisi nyala (NC tertutup)
  digitalWrite(RELAY_PIN, RELAY_SUPPLY_POWER);
  isPowerCut = false;

  Serial.begin(9600);
  while (!Serial) {
    ; // Tunggu serial terhubung
  }

  Serial.println("STATUS:READY:MEGA2560");
}

void loop() {
  // Cek perintah dari Aplikasi Desktop
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    handleCommand(command);
  }

  // Non-blocking timer untuk siklus restart
  if (isRestarting) {
    if (millis() - restartTimerStart >= restartDuration) {
      // Waktu jeda mati selesai -> hidupkan kembali scanner
      digitalWrite(RELAY_PIN, RELAY_SUPPLY_POWER);
      isPowerCut = false;
      isRestarting = false;
      Serial.println("STATUS:RESTART_COMPLETE:SCANNER_ON");
    }
  }
}

void handleCommand(String cmd) {
  if (cmd == "PING") {
    Serial.println("PONG");
  } 
  else if (cmd.startsWith("RESTART")) {
    // Format: RESTART atau RESTART:5000 (durasi dalam milidetik)
    int duration = 4000; // default 4 detik jeda mati
    int colonIdx = cmd.indexOf(':');
    if (colonIdx > 0) {
      int parsed = cmd.substring(colonIdx + 1).toInt();
      if (parsed >= 1000 && parsed <= 30000) {
        duration = parsed;
      }
    }

    // Eksekusi potong daya
    digitalWrite(RELAY_PIN, RELAY_CUT_POWER);
    isPowerCut = true;
    isRestarting = true;
    restartDuration = duration;
    restartTimerStart = millis();

    Serial.print("STATUS:RESTARTING:DURATION=");
    Serial.println(duration);
  } 
  else if (cmd == "POWER:OFF") {
    // Matikan scanner secara manual (terus mati sampai di-ON-kan)
    isRestarting = false;
    digitalWrite(RELAY_PIN, RELAY_CUT_POWER);
    isPowerCut = true;
    Serial.println("STATUS:POWER_OFF");
  } 
  else if (cmd == "POWER:ON") {
    // Hidupkan scanner secara manual
    isRestarting = false;
    digitalWrite(RELAY_PIN, RELAY_SUPPLY_POWER);
    isPowerCut = false;
    Serial.println("STATUS:POWER_ON");
  } 
  else if (cmd == "STATUS") {
    if (isRestarting) {
      Serial.println("STATUS:STATE_RESTARTING");
    } else if (isPowerCut) {
      Serial.println("STATUS:STATE_OFF");
    } else {
      Serial.println("STATUS:STATE_ON");
    }
  } 
  else {
    Serial.println("ERROR:UNKNOWN_COMMAND");
  }
}
