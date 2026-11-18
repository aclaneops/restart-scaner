# Scanner Hardware Restarter (Arduino Mega 2560 & Windows App)

Sistem hardware restarter dan power controller untuk perangkat scanner (adaptor 5V DC) menggunakan **Arduino Mega 2560** dan **Relay 1-Channel**, dikendalikan melalui aplikasi desktop Windows dengan dukungan **Manual Restart** dan **Scheduler Otomatis**.

---

## 🔌 1. Skema Pengkabelan (Wiring Diagram)

### A. Arduino Mega 2560 ke Modul Relay (5V):
| Pin Modul Relay | Pin Arduino Mega 2560 | Keterangan |
| :--- | :--- | :--- |
| **VCC** | **5V** | Sumber daya modul relay |
| **GND** | **GND** | Ground bersama |
| **IN** | **Pin D7** | Sinyal kontrol pemicu relay |

### B. Modul Relay ke Jalur Daya Adaptor Scanner (5V DC):
Potong kabel positif (+) dari adaptor 5V scanner, lalu hubungkan ke terminal relay:
- **Kabel Positif (+) dari Adaptor 5V** $\rightarrow$ Terminal **COM** (Common) pada Relay.
- **Kabel Positif (+) menuju Jack Scanner** $\rightarrow$ Terminal **NC** (Normally Closed) pada Relay.
- **Kabel Negatif / Ground (-)** adaptor tetap tersambung langsung ke scanner (tidak dipotong).

> **Mengapa menggunakan NC (Normally Closed)?**
> Saat Arduino mati atau idle, sirkuit tetap tertutup sehingga scanner menyala normal seperti biasa tanpa menguras daya koil relay. Saat perintah restart dikirim, Arduino akan memicu relay selama 4 detik sehingga kontak terbuka (arus terputus sesaat), lalu menutup kembali (arus mengalir lagi, scanner restart).

---

## 🛠️ 2. Cara Flash Firmware ke Arduino Mega 2560 (dari Mac)

1. Buka aplikasi **Arduino IDE** di MacBook Anda.
2. Buka file:
   `scanner_restarter/firmware/scanner_controller.ino`
3. Pada menu Arduino IDE:
   - **Tools** $\rightarrow$ **Board** $\rightarrow$ pilih **Arduino Mega or Mega 2560**.
   - **Tools** $\rightarrow$ **Processor** $\rightarrow$ pilih **ATmega2560 (Mega 2560)**.
   - **Tools** $\rightarrow$ **Port** $\rightarrow$ pilih port USB Arduino (misal `/dev/cu.usbmodem...` atau `/dev/cu.usbserial...`).
4. Klik tombol **Upload** (tanda panah ke kanan).

---

## 💻 3. Menjalankan & Mengetes Aplikasi di MacBook

Aplikasi dibangun menggunakan Python Tkinter (cross-platform), sehingga bisa langsung dites di Mac:

```bash
cd scanner_restarter/desktop_app
pip install -r requirements.txt
python3 app.py
```

---

## 📦 4. Membuat File Standalone `.exe` untuk Windows 7, 10, dan 11

### PENTING untuk Kompatibilitas Windows 7:
- Gunakan **Python 3.8.10 (32-bit atau 64-bit)** saat mengompilasi `.exe`. Python 3.8 adalah versi Python resmi terakhir yang mendukung Windows 7 sekaligus tetap berjalan lancar di Windows 10 & 11.
- Jalankan file `build_windows_exe.bat` di komputer Windows atau jalankan perintah:
  ```cmd
  pip install pyserial pyinstaller
  pyinstaller --onefile --noconsole --name "ScannerRestarter" app.py
  ```
- File siap pakai akan berada di folder: `dist\ScannerRestarter.exe`.

---

## 📋 5. Fitur Aplikasi Desktop

1. **Auto-Detect Port COM**: Memilih port USB serial Arduino Mega secara otomatis.
2. **Kontrol Manual**:
   - **⚡ RESTART SCANNER**: Memutus daya selama durasi yang ditentukan (default 4 detik) lalu menghidupkannya kembali.
   - **🔴 Power OFF**: Mematikan daya scanner terus-menerus.
   - **🟢 Power ON**: Menghidupkan kembali daya scanner.
3. **Scheduler Terjadwal (2 Mode)**:
   - **Mode Harian Spesifik**: Menjalankan restart setiap jam tertentu (contoh: `02:00` tengah malam).
   - **Mode Interval**: Menjalankan restart rutin setiap X menit (contoh: setiap `360` menit / 6 jam).
   - Hitung mundur (*countdown*) waktu eksekusi berikutnya ditampilkan secara real-time.
4. **Auto-Save Settings**: Menyimpan port COM terakhir, durasi restart, dan konfigurasi jadwal ke file `config.json`.
