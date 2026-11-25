/*
 * =====================================================================
 * SISTEM HARDWARE RESTARTER SCANNER QR GATE STASIUN KERETA (MULTI-CHANNEL)
 * =====================================================================
 * Target Board : Arduino Mega 2560 (Didukung juga untuk Uno / Nano)
 * Perangkat    : 2x (atau hingga 4x) Scanner QR Turnstile Gate Kereta
 * Logika Relay : Active-LOW dengan Terminal NORMALLY CLOSED (NC)
 * Fitur Khusus :
 *   1. Hardware Watchdog Timer (WDT) 8 Detik (Auto Self-Reset jika hang)
 *   2. Fail-Safe NC Wiring (Daya tetap mengalir jika Arduino mati/rusak)
 *   3. Staggered Restart (Restart bergiliran dengan jeda antar scanner)
 *   4. Kontrol Terpisah Per-Channel & Kontrol Serentak (ALL)
 * =====================================================================
 *
 * PEMETAAN PIN RELAY:
 * - Channel 1 (Scanner QR Gate 1 / In)  : Digital Pin D7
 * - Channel 2 (Scanner QR Gate 2 / Out) : Digital Pin D8
 * - Channel 3 (Cadangan / Scanner 3)    : Digital Pin D9
 * - Channel 4 (Cadangan / Scanner 4)    : Digital Pin D10
 *
 * SKEMA KONTROL ARUS (ACTIVE-LOW):
 * - LOW  = Relay ON  (Kontak NC terbuka -> Power Scanner MATI / CUT)
 * - HIGH = Relay OFF (Kontak NC tertutup -> Power Scanner NYALA / IDLE)
 * =====================================================================
 */

#include <avr/wdt.h>

const int NUM_CHANNELS = 4;
const int RELAY_PINS[NUM_CHANNELS] = {7, 8, 9, 10};

// Definisi Logika Active-LOW
const int RELAY_CUT_POWER = LOW;     // Memutuskan arus adaptor scanner
const int RELAY_SUPPLY_POWER = HIGH; // Mengalirkan arus (keadaan normal/idle)

// Status tiap channel
bool isPowerCut[NUM_CHANNELS] = {false, false, false, false};
bool isRestarting[NUM_CHANNELS] = {false, false, false, false};
unsigned long restartTimerStart[NUM_CHANNELS] = {0, 0, 0, 0};
unsigned long restartDuration[NUM_CHANNELS] = {4000, 4000, 4000, 4000};

// Manajemen Staggered Restart (Semua Scanner bergiliran)
bool isStaggeredRunning = false;
int staggeredCurrentStep = 0;
unsigned long staggeredStepTimer = 0;
unsigned long staggeredDurationParam = 4000;

void setup() {
  // Inisialisasi semua pin relay ke kondisi SAFE (Daya Mengalir)
  for (int i = 0; i < NUM_CHANNELS; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], RELAY_SUPPLY_POWER);
    isPowerCut[i] = false;
    isRestarting[i] = false;
  }

  Serial.begin(9600);
  while (!Serial) {
    ; // Tunggu koneksi serial USB
  }

  // Aktifkan Hardware Watchdog Timer (WDT) 8 Detik
  // Jika Arduino hang atau kena noise listrik statis stasiun, WDT akan reboot otomatis
  wdt_enable(WDTO_8S);

  Serial.println("STATUS:READY:GATE_SCANNER_CONTROLLER_4CH");
}

void loop() {
  // Reset watchdog timer setiap siklus loop normal
  wdt_reset();

  // 1. Baca Perintah dari PC Host EPC via USB Serial
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      handleCommand(cmd);
    }
  }

  unsigned long currentMillis = millis();

  // 2. Timer Independen Restart Per-Channel
  for (int i = 0; i < NUM_CHANNELS; i++) {
    if (isRestarting[i]) {
      if (currentMillis - restartTimerStart[i] >= restartDuration[i]) {
        // Waktu jeda mati selesai -> Hidupkan kembali scanner channel ini
        digitalWrite(RELAY_PINS[i], RELAY_SUPPLY_POWER);
        isPowerCut[i] = false;
        isRestarting[i] = false;

        Serial.print("STATUS:RESTART_COMPLETE:CH");
        Serial.println(i + 1);
      }
    }
  }

  // 3. Mesin Sekuensial Staggered Restart (ALL)
  // Menghindari inrush current bersamaan pada power supply EPC Gate
  if (isStaggeredRunning) {
    if (staggeredCurrentStep == 1) {
      // Step 1: Matikan Channel 1
      digitalWrite(RELAY_PINS[0], RELAY_CUT_POWER);
      isPowerCut[0] = true;
      isRestarting[0] = true;
      restartDuration[0] = staggeredDurationParam;
      restartTimerStart[0] = currentMillis;
      staggeredStepTimer = currentMillis;
      staggeredCurrentStep = 2;
      Serial.println("STATUS:STAGGERED:CH1_CUT");
    }
    else if (staggeredCurrentStep == 2) {
      // Tunggu jeda staggered (misal 1500ms setelah CH1 mulai mati) sebelum giliran CH2
      if (currentMillis - staggeredStepTimer >= 1500) {
        // Step 2: Matikan Channel 2
        digitalWrite(RELAY_PINS[1], RELAY_CUT_POWER);
        isPowerCut[1] = true;
        isRestarting[1] = true;
        restartDuration[1] = staggeredDurationParam;
        restartTimerStart[1] = currentMillis;
        staggeredStepTimer = currentMillis;
        staggeredCurrentStep = 3;
        Serial.println("STATUS:STAGGERED:CH2_CUT");
      }
    }
    else if (staggeredCurrentStep == 3) {
      // Tunggu sampai kedua channel selesai menyala kembali
      if (!isRestarting[0] && !isRestarting[1]) {
        isStaggeredRunning = false;
        staggeredCurrentStep = 0;
        Serial.println("STATUS:STAGGERED_COMPLETE:ALL_ON");
      }
    }
  }
}

// =====================================================================
// PEMROSES PERINTAH SERIAL
// Format Perintah:
// - PING                  -> Balas PONG
// - STATUS                -> Balas status daya tiap channel
// - RESTART:1:[ms]        -> Restart Scanner 1 (Default: 4000ms)
// - RESTART:2:[ms]        -> Restart Scanner 2
// - RESTART:ALL:[ms]      -> Restart Semua Scanner secara Staggered
// - POWER:1:ON / OFF      -> Kontrol manual Scanner 1
// - POWER:2:ON / OFF      -> Kontrol manual Scanner 2
// - POWER:ALL:ON / OFF    -> Kontrol manual Semua Scanner
// =====================================================================
void handleCommand(String cmd) {
  if (cmd == "PING") {
    Serial.println("PONG");
    return;
  }

  // --- CEK PERINTAH STATUS ---
  if (cmd == "STATUS") {
    Serial.print("STATUS:CH1=");
    Serial.print(isRestarting[0] ? "RESTARTING" : (isPowerCut[0] ? "OFF" : "ON"));
    Serial.print(":CH2=");
    Serial.print(isRestarting[1] ? "RESTARTING" : (isPowerCut[1] ? "OFF" : "ON"));
    Serial.print(":CH3=");
    Serial.print(isRestarting[2] ? "RESTARTING" : (isPowerCut[2] ? "OFF" : "ON"));
    Serial.print(":CH4=");
    Serial.println(isRestarting[3] ? "RESTARTING" : (isPowerCut[3] ? "OFF" : "ON"));
    return;
  }

  // --- CEK PERINTAH RESTART ---
  if (cmd.startsWith("RESTART")) {
    int duration = 4000;
    int targetChannel = 1; // 1 = CH1, 2 = CH2, 99 = ALL
    bool isAll = false;

    // Parsing: RESTART, RESTART:1, RESTART:2:4000, RESTART:ALL:4000
    int firstColon = cmd.indexOf(':');
    if (firstColon > 0) {
      int secondColon = cmd.indexOf(':', firstColon + 1);
      String chStr = "";
      if (secondColon > 0) {
        chStr = cmd.substring(firstColon + 1, secondColon);
        int parsedDur = cmd.substring(secondColon + 1).toInt();
        if (parsedDur >= 1000 && parsedDur <= 30000) duration = parsedDur;
      } else {
        chStr = cmd.substring(firstColon + 1);
      }

      chStr.toUpperCase();
      if (chStr == "ALL") {
        isAll = true;
      } else {
        int parsedCh = chStr.toInt();
        if (parsedCh >= 1 && parsedCh <= NUM_CHANNELS) {
          targetChannel = parsedCh;
        }
      }
    }

    if (isAll) {
      // Eksekusi Staggered Restart
      staggeredDurationParam = duration;
      staggeredCurrentStep = 1;
      isStaggeredRunning = true;
      Serial.print("STATUS:STARTING_STAGGERED_RESTART:DURATION=");
      Serial.println(duration);
    } else {
      // Eksekusi Single Channel
      int idx = targetChannel - 1;
      digitalWrite(RELAY_PINS[idx], RELAY_CUT_POWER);
      isPowerCut[idx] = true;
      isRestarting[idx] = true;
      restartDuration[idx] = duration;
      restartTimerStart[idx] = millis();

      Serial.print("STATUS:RESTARTING:CH=");
      Serial.print(targetChannel);
      Serial.print(":DURATION=");
      Serial.println(duration);
    }
    return;
  }

  // --- CEK PERINTAH POWER MANUAL (ON / OFF) ---
  if (cmd.startsWith("POWER:")) {
    // Format: POWER:1:OFF, POWER:1:ON, POWER:ALL:OFF, POWER:ALL:ON
    int firstColon = cmd.indexOf(':');
    int secondColon = cmd.indexOf(':', firstColon + 1);
    if (secondColon > 0) {
      String chStr = cmd.substring(firstColon + 1, secondColon);
      String action = cmd.substring(secondColon + 1);
      chStr.toUpperCase();
      action.toUpperCase();

      bool turnOn = (action == "ON");

      if (chStr == "ALL") {
        for (int i = 0; i < NUM_CHANNELS; i++) {
          isRestarting[i] = false;
          digitalWrite(RELAY_PINS[i], turnOn ? RELAY_SUPPLY_POWER : RELAY_CUT_POWER);
          isPowerCut[i] = !turnOn;
        }
        Serial.println(turnOn ? "STATUS:POWER:ALL:ON" : "STATUS:POWER:ALL:OFF");
      } else {
        int ch = chStr.toInt();
        if (ch >= 1 && ch <= NUM_CHANNELS) {
          int idx = ch - 1;
          isRestarting[idx] = false;
          digitalWrite(RELAY_PINS[idx], turnOn ? RELAY_SUPPLY_POWER : RELAY_CUT_POWER);
          isPowerCut[idx] = !turnOn;

          Serial.print("STATUS:POWER:CH");
          Serial.print(ch);
          Serial.println(turnOn ? ":ON" : ":OFF");
        }
      }
      return;
    }
  }

  Serial.println("ERROR:UNKNOWN_COMMAND");
}
