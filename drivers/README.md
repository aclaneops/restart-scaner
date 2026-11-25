# 🔌 Panduan Driver USB Arduino untuk Windows / PC Host EPC

Folder ini berisi paket driver USB Serial untuk memastikan Arduino Mega 2560 dikenali oleh PC Host EPC (Windows 7, 8, 10, dan 11).

---

## 🔍 Cara Mengetahui Driver Mana yang Diperlukan

Periksa fisik chip kecil di dekat soket USB Arduino Mega 2560 Anda:

### 1. Arduino Mega Kloning (Chip CH340 / CH340G / CH341) — *Paling Umum Digunakan*
* **Ciri fisik:** Chip IC berbentuk persegi panjang bertuliskan **WCH / CH340G**.
* **Kebutuhan Driver:** Memerlukan instalasi driver di **semua versi Windows** (7, 8, 10, 11).
* **Cara Install:**
  1. Masuk ke folder `CH340_Windows/`.
  2. Klik kanan file `CH341SER.EXE` $\rightarrow$ pilih **Run as administrator**.
  3. Klik tombol **INSTALL**.
  4. Tunggu beberapa detik sampai muncul notifikasi *"Driver install success!"*.
  5. Cabut lalu colokkan kembali kabel USB Arduino ke EPC.

---

### 2. Arduino Mega Original / Chip ATmega16U2 (CDC ACM)
* **Ciri fisik:** Chip kecil berbentuk bujur sangkar dengan logo Atmel / tulisan **MEGA 16U2**.
* **Kebutuhan Driver:**
  - **Windows 10 / 11:** *Plug & Play* otomatis, **tidak perlu install driver manual**.
  - **Windows 7 / POSReady 7 / Windows 8:** Memerlukan instalasi driver dari folder `Arduino_Official/`.
* **Cara Install (Khusus Windows 7 / 8):**
  * **Opsi Otomatis (Direkomendasikan):**
    - Untuk Windows 64-bit: Jalankan `Arduino_Official/dpinst-amd64.exe` (Run as administrator).
    - Untuk Windows 32-bit: Jalankan `Arduino_Official/dpinst-x86.exe` (Run as administrator).
  * **Opsi Manual via INF:**
    - Buka folder `Arduino_Official/`.
    - Klik kanan file `arduino.inf` $\rightarrow$ klik **Install**.
    - Atau melalui **Device Manager** $\rightarrow$ cari perangkat bertanda seru kuning $\rightarrow$ *Update Driver* $\rightarrow$ *Browse my computer for drivers* $\rightarrow$ arahkan ke folder `Arduino_Official/`.

---

## ✅ Cara Verifikasi Driver Sudah Terpasang di EPC

1. Buka **Device Manager** di Windows (`Win + R` $\rightarrow$ ketik `devmgmt.msc` $\rightarrow$ Enter).
2. Perluas bagian **Ports (COM & LPT)**.
3. Anda akan melihat salah satu dari berikut tanpa tanda seru kuning:
   - `USB-SERIAL CH340 (COMx)` (untuk chip CH340)
   - `Arduino Mega 2560 (COMx)` (untuk chip ATmega16U2)
4. Buka aplikasi **ScannerRestarter.exe**, port COM tersebut akan otomatis terdeteksi.
