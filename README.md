# 🚇 Railway Station Gate QR Scanner Hardware Restarter (Multi-Channel)

Sistem pengendali dan hardware restarter untuk **Scanner QR Turnstile Gate Stasiun Kereta** menggunakan **Arduino Mega 2560** dan **Relay Multi-Channel (2-CH / 4-CH)** berbasis logika **Normally Closed (NC) Fail-Safe** dan **Hardware Watchdog Timer (WDT)**.

Dikendalikan melalui aplikasi desktop Windows (kompatibel penuh dengan **Windows 7 32-bit/64-bit, POSReady 7, Windows 10, Windows 11**) dengan dukungan **Manual Restart Per-Channel**, **Staggered Restart Serentak**, dan **Advanced Scheduler Otomatis**.

---

## 📑 Dokumen & Panduan Penting
* 📘 **[PANDUAN_TEKNISI_GATE_STASIUN.md](PANDUAN_TEKNISI_GATE_STASIUN.md)**: SOP Penggantian Unit di Lapangan, Diagram Kelistrikan, dan Prosedur Darurat (Emergency Bypass) bagi teknisi gate stasiun.
* 🌐 **[simulator_gate.html](simulator_gate.html)**: Simulasi visual interaktif turnstile gate, tapping tiket penumpang, relay click, dan serial monitor log (bisa dibuka langsung di browser Safari/Chrome pada MacBook tanpa perlu hardware fisik).
* 🔌 **[drivers/README.md](drivers/README.md)**: Panduan instalasi driver USB CH340 dan Arduino Official untuk PC EPC Host.

---

## 🔌 1. Skema Pengkabelan (Wiring Diagram 2-Channel Fail-Safe)

### A. Arduino Mega 2560 ke Modul Relay 2-Channel (5V Active-LOW):
| Pin Modul Relay | Pin Arduino Mega 2560 | Keterangan |
| :--- | :--- | :--- |
| **VCC** | **Pin 5V** | Sumber daya modul relay |
| **GND** | **Pin GND** | Ground bersama |
| **IN1** | **Pin D7** | Kontrol Scanner 1 (Gate In / Masuk) |
| **IN2** | **Pin D8** | Kontrol Scanner 2 (Gate Out / Keluar) |
| *(IN3)* | *Pin D9* | *Cadangan / Scanner 3 (Jika pakai 4-CH)* |
| *(IN4)* | *Pin D10* | *Cadangan / Scanner 4 (Jika pakai 4-CH)* |

### B. Modul Relay ke Jalur Daya Adaptor Scanner (5V DC):
Gunakan **Jack DC Barrel 5.5 x 2.1 mm (Tipe Baut)** agar kabel adaptor bawaan scanner tidak dipotong:
- **Kabel Positif (+) dari Adaptor 5V** $\rightarrow$ Terminal **COM** (Common) pada Relay.
- **Kabel Positif (+) menuju Jack Scanner** $\rightarrow$ Terminal **NC** (Normally Closed) pada Relay.
- **Kabel Negatif / Ground (-)** adaptor tetap tersambung langsung ke scanner (tidak melalui relay).

> **Mengapa wajib NC (Normally Closed)?**
> Saat Arduino mati, kabel USB tercabut, atau terjadi lonjakan listrik, kontak NC tetap tertutup sehingga scanner QR **tetap menyala normal** dan penumpang tetap bisa tap tiket. Relay hanya bekerja (berenergi) beberapa detik saat perintah restart dikirim dari aplikasi host EPC.

---

## 🛠️ 2. Cara Flash Firmware ke Arduino Mega 2560 (dari Mac)

1. Buka aplikasi **Arduino IDE** di MacBook.
2. Buka file: `firmware/scanner_controller.ino`.
3. Pada menu Arduino IDE:
   - **Tools** $\rightarrow$ **Board** $\rightarrow$ **Arduino Mega or Mega 2560**.
   - **Tools** $\rightarrow$ **Processor** $\rightarrow$ **ATmega2560 (Mega 2560)**.
   - **Tools** $\rightarrow$ **Port** $\rightarrow$ pilih port USB Arduino.
4. Klik tombol **Upload** (tanda panah ke kanan).

---

## 💻 3. Menjalankan & Mengetes Simulasi di MacBook

### Opsi A: Simulasi Visual di Browser (Paling Mudah)
Buka file **`simulator_gate.html`** di browser Chrome atau Safari di MacBook Anda. Anda dapat langsung mengklik tombol restart, melihat lampu indikator, mendengar bunyi klik relay, dan melihat log komunikasi serial secara interaktif!

### Opsi B: Menjalankan Aplikasi Python di Mac
```bash
cd desktop_app
pip install -r requirements.txt
python3 app.py
```
Pada dropdown **Port USB**, pilih:
`[SIMULASI / DEMO VIRTUAL GATE STASIUN]`
Aplikasi akan mensimulasikan respons serial Arduino Mega secara langsung tanpa memerlukan perangkat fisik.

---

## 📦 4. Build Otomatis Windows 32-bit (x86) via GitHub Actions

Aplikasi ini otomatis di-build menjadi file `.exe` 32-bit standalone menggunakan **Python 3.8.10 (x86)** via GitHub Actions setiap kali ada push ke repository. File `.exe` ini kompatibel dengan **Windows 7 32-bit / POSReady 7 EPC** maupun Windows 10/11 64-bit.
