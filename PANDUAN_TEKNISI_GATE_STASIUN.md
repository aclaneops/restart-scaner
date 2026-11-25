# 🚇 PANDUAN TEKNISI: SISTEM HARDWARE RESTARTER GATE QR SCANNER STASIUN

Buku panduan operasional, instalasi, dan SOP penanganan gangguan / penggantian unit **Hardware Restarter Multi-Channel** untuk Scanner QR pada **Turnstile Gate Stasiun Kereta**.

---

## 📌 1. Latar Belakang & Prinsip Kerja Sistem

Perangkat scanner QR di gate turnstile stasiun bekerja 24/7 melayani ribuan penumpang per jam. Beberapa kendala umum di lapangan:
- Scanner mengalami *freeze/hang* akibat penumpukan buffer data tiket.
- Scanner panas di dalam bodi tertutup turnstile gate.
- Lonjakan listrik statis dari penumpang saat tap tiket.

Sistem ini berfungsi untuk **me-reboot daya adaptor 5V scanner secara otomatis (terjadwal) maupun manual via software EPC** tanpa perlu teknisi membongkar bodi turnstile gate.

---

## 🛡️ 2. Konsep Utama: FAIL-SAFE WIRING (Normally Closed / NC)

> **⚠️ ATURAN EMAS KELISTRIKAN TURNSTILE GATE:**  
> Seluruh jalur pemutus daya scanner **WAJIB** disambungkan ke terminal **NC (Normally Closed)** pada modul relay, **BUKAN** NO (Normally Open).

### Mengapa Wajib NC?
| Kondisi Sistem | Terminal NC (Normally Closed) | Jika Pakai NO (Salah) |
| :--- | :--- | :--- |
| **PC EPC Mati Lampu / Shutdown** | Scanner **TETAP MENYALA** | Scanner ikut mati |
| **Kabel USB Arduino Lepas/Senggol** | Scanner **TETAP MENYALA** | Scanner langsung mati total |
| **Arduino Rusak / Hang** | Scanner **TETAP MENYALA** | Gerbang gate macet |
| **Saat Perintah Restart Dikirim** | Relay aktif 4 detik $\rightarrow$ Kontak terbuka $\rightarrow$ **Scanner Reboot** | Scanner menyala sesaat lalu mati |

*Dengan terminal NC, kegagalan pada alat restarter tidak akan pernah melumpuhkan gerbang stasiun!*

---

## 🔌 3. Skema Pengkabelan (Wiring Diagram 2-Channel)

### A. Arduino Mega 2560 ke Modul Relay 2-Channel (5V Active-LOW):
| Pin Modul Relay | Pin Arduino Mega 2560 | Keterangan |
| :--- | :--- | :--- |
| **VCC** | **Pin 5V** | Sumber daya modul relay |
| **GND** | **Pin GND** | Ground bersama |
| **IN1** | **Pin D7** | Kontrol Scanner 1 (Gate In / Masuk) |
| **IN2** | **Pin D8** | Kontrol Scanner 2 (Gate Out / Keluar) |
| *(IN3)* | *Pin D9* | *Cadangan / Scanner 3 (Jika pakai 4-CH)* |
| *(IN4)* | *Pin D10* | *Cadangan / Scanner 4 (Jika pakai 4-CH)* |

---

### B. Modul Relay ke Jalur Daya Adaptor Scanner (5V DC):
> **Rekomendasi Best Practice:** Jangan memotong kabel adaptor asli bawaan scanner stasiun! Gunakan **Jack DC Barrel 5.5 x 2.1 mm (Tipe Baut)** agar rapi dan *plug-and-play*.

```text
Adaptor 5V (+) ───> Jack DC Female ───> Terminal COM Relay
                                                │
                                    (Kontak NC Relai)
                                                │
Jack Scanner (+) <─── Jack DC Male  <─── Terminal NC Relay

Adaptor 5V (-) ────────────────────────> Jack Scanner (-) [Ground langsung terhubung]
```

1. **Jalur Positif (+):**
   - Kabel (+) dari Adaptor Scanner 5V masuk ke terminal **COM** Relay.
   - Kabel (+) menuju Scanner QR masuk ke terminal **NC** Relay.
2. **Jalur Negatif / Ground (-):**
   - Kabel (-) dari adaptor disambung langsung ke kabel (-) jack scanner (tidak diputus oleh relay).

---

## 🛠️ 4. SOP Penggantian Unit Rusak di Gate Stasiun

Jika unit kontroler di salah satu gate dilaporkan bermasalah oleh tim stasiun:

### Langkah 1: Persiapan Unit Pengganti (Spare Part)
1. Siapkan unit cadangan: **Arduino Mega 2560** + **Modul Relay** dalam box enclosure.
2. Pastikan firmware terbaru sudah di-flash:
   - File: `firmware/scanner_controller.ino`
   - Setting Arduino IDE: Board **Arduino Mega 2560**, Processor **ATmega2560**.

### Langkah 2: Proses Penggantian di Turnstile Gate
1. Buka penutup bodi turnstile gate dengan kunci akses teknisi.
2. Cabut kabel USB Arduino dari port PC Host EPC.
3. Cabut konektor **Jack DC Scanner 1** dan **Jack DC Scanner 2** dari box controller lama.
   *(Saat dicabut, scanner otomatis mati sesaat).*
4. Pasang box controller baru:
   - Colokkan kembali Jack DC Scanner 1 ke port output Channel 1.
   - Colokkan kembali Jack DC Scanner 2 ke port output Channel 2.
   - Colokkan kabel USB Arduino ke PC Host EPC.
5. Periksa lampu indikator fisik:
   - **LED Power Arduino** menyala merah/hijau stabil.
   - **LED Relay** dalam kondisi padam (karena koil idle = kontak NC tertutup = scanner langsung menyala).
   - Scanner QR menyala dan mengeluarkan sinar garis laser standby.

### Langkah 3: Uji Fungsi 3 Menit via Aplikasi EPC
1. Di PC EPC, buka aplikasi **`ScannerRestarter.exe`**.
2. Port USB Arduino akan otomatis terhubung (`● TERHUBUNG COMx`).
3. Tekan tombol **[⚡ RESTART SCANNER 1]**:
   - Relay 1 berbunyi *klik*, lampu LED Channel 1 menyala merah selama 4 detik, scanner 1 mati lalu hidup kembali.
4. Tekan tombol **[⚡ RESTART SCANNER 2]**:
   - Relay 2 berbunyi *klik*, scanner 2 mati lalu hidup kembali.
5. Lakukan uji coba tap tiket QR penumpang di kedua gerbang. Pastikan scanner membaca data tiket dengan normal.
6. Tutup dan kunci kembali bodi turnstile gate.

---

## 🚨 5. Prosedur Darurat (Emergency Manual Bypass)

Jika unit Arduino atau relay mengalami kerusakan mendadak pada **jam sibuk (rush hour)** stasiun di mana teknisi tidak sempat mengganti modul:

1. Buka bodi gate.
2. Lepas kabel daya positif (+) scanner dari terminal **COM & NC** relay.
3. Hubungkan kedua kabel positif (+) tersebut secara langsung (bypass relay) menggunakan konektor wago / isolasi darurat.
4. Scanner akan langsung menyala normal tanpa melalui kontroler relay.
5. Gerbang stasiun tetap bisa melayani penumpang tanpa hambatan, dan perbaikan modul dapat dilanjutkan malam hari saat stasiun tutup.

---

## 🔍 6. Panduan Diagnostik Cepat (Troubleshooting)

| Gejala | Kemungkinan Penyebab | Tindakan Teknisi |
| :--- | :--- | :--- |
| **Scanner QR mati total setelah dipasang** | Salah pasang terminal (terpasang di **NO**, bukan **NC**) | Pindahkan kabel output positif scanner dari terminal **NO** ke terminal **NC**. |
| **Aplikasi EPC status: "TERPUTUS"** | Driver USB CH340 belum terpasang di PC EPC | Buka folder `drivers\CH340_Windows` $\rightarrow$ jalankan `CH341SER.EXE` $\rightarrow$ Klik **INSTALL**. |
| **Relay tidak mau klik saat direstart** | Pin kontrol tertukar atau kendor | Periksa kabel jumper: IN1 harus ke **Pin D7**, IN2 ke **Pin D8**, VCC ke **5V**, GND ke **GND**. |
| **Arduino mendadak restart sendiri** | Fitur Watchdog Timer (WDT) bekerja normal | Ini adalah fitur keamanan! Jika ada gangguan listrik statis, WDT 8s me-reboot mikrokontroler agar sistem pulih otomatis. |
| **Aplikasi di PC EPC tampil "Not Compatible"** | Menggunakan versi 64-bit pada EPC 32-bit | Pastikan menggunakan file hasil compile terbaru versi **32-bit (x86)** dari folder `ScannerRestarter_Windows_32bit_Ready`. |

---

## ⏰ 7. Standar Penjadwalan Otomatis Gate Stasiun

Untuk keandalan maksimal, disarankan mengatur scheduler otomatis pada tab **📅 Setiap Hari**:
- **Jam Eksekusi:** `02:00 WIB` (Saat stasiun tutup dan jadwal kereta terakhir selesai).
- **Target:** `Semua Scanner (Staggered / Bergiliran)`.
- **Durasi Jeda:** `4 detik`.

Dengan jadwal ini, setiap pagi hari pukul `04:00 WIB` saat gate stasiun dibuka kembali untuk penumpang pertama, seluruh scanner QR sudah dalam kondisi segar (*fresh reboot*) tanpa sampah memori/cache.
