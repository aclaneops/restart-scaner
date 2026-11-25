"""
=====================================================================
EPC HARDWARE RESTARTER (SIMPLIFIED & CLEAN MODERN UI)
=====================================================================
Target Perangkat : 2x Scanner QR Turnstile Gate Kereta
Target Board     : Arduino Mega 2560 (Relay 2-CH / 4-CH Active-LOW)
Platform Host    : Windows 7, POSReady 7, Windows 10, Windows 11 & macOS
=====================================================================
"""

import os
os.environ["TK_SILENCE_DEPRECATION"] = "1"
import sys
import json
import time
import datetime
import calendar
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports

CONFIG_FILE = "config.json"
LOG_FILE = "scanner_activity.log"

HARI_INDONESIA = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN_INDONESIA = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", 
                   "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

DEFAULT_CONFIG = {
    "last_port": "",
    "baud_rate": 9600,
    "restart_duration_sec": 4,
    "auto_connect_usb": True,
    "scheduler_enabled": False,
    "sched_target": "ALL",
    "active_tab": 0,
    "sched_hour": "02",
    "sched_minute": "00",
    "sched_days": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"],
    "sched_month_date": 1,
    "sched_specific_year": 2026,
    "sched_specific_month": 11,
    "sched_specific_day": 26,
    "sched_interval_minutes": 360
}

SIMULATION_PORT = "[Simulasi / Virtual Arduino Mega]"

# Palet Warna Minimalis & Tenang (Clean Slate UI - Tidak Rame)
CLR_BG = "#f8fafc"         # Background utama abu-abu sangat muda
CLR_CARD = "#ffffff"       # Card putih bersih
CLR_BORDER = "#e2e8f0"     # Garis batas halus
CLR_TEXT = "#1e293b"       # Teks utama slate gelap
CLR_MUTED = "#64748b"      # Teks sekunder abu-abu
CLR_PRIMARY = "#2563eb"    # Biru profesional
CLR_GREEN = "#16a34a"      # Hijau indikator normal
CLR_RED = "#dc2626"        # Merah indikator putus
CLR_AMBER = "#d97706"      # Kuning saat restart
CLR_DARK = "#0f172a"       # Hitam untuk console log

class SimplifiedStationGateRestarterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EPC Gate Scanner Restarter")
        self.root.geometry("640x700")
        self.root.minsize(600, 640)
        self.root.configure(bg=CLR_BG)

        self.setup_theme()

        self.ser = None
        self.is_simulation = False
        self.is_running = True
        self.config = self.load_config()

        self.relay_states = {1: "ON", 2: "ON"}
        self.restart_count = 0
        self.last_interval_trigger = time.time()
        self.day_check_vars = {}

        self.setup_ui()
        self.apply_config_to_ui()
        self.refresh_ports(auto_select=True)

        self.start_epc_clock_timer()
        self.start_usb_hotplug_monitor()
        self.start_scheduler_engine()

    def setup_theme(self):
        style = ttk.Style()
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass
        style.configure("TNotebook", background=CLR_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background="#e2e8f0", foreground=CLR_TEXT, padding=[12, 5], font=("Arial", 9))
        style.map("TNotebook.Tab", background=[("selected", CLR_CARD)], foreground=[("selected", CLR_PRIMARY)])
        style.configure("TCombobox", fieldbackground="#ffffff", background="#ffffff", foreground=CLR_TEXT)
        style.configure("TSpinbox", fieldbackground="#ffffff", background="#ffffff", foreground=CLR_TEXT)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return {**DEFAULT_CONFIG, **cfg}
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            self.config["last_port"] = self.get_selected_device_port()
            self.config["baud_rate"] = int(self.baud_combobox.get() or 9600)
            self.config["restart_duration_sec"] = int(self.spin_duration.get() or 4)
            self.config["auto_connect_usb"] = self.var_autoconnect.get()
            self.config["scheduler_enabled"] = self.var_sched_enabled.get()
            self.config["sched_target"] = self.combo_sched_target.get()
            self.config["active_tab"] = self.notebook.index(self.notebook.select())
            self.config["sched_hour"] = self.combo_hour.get()
            self.config["sched_minute"] = self.combo_min.get()
            self.config["sched_days"] = [d for d, v in self.day_check_vars.items() if v.get()]
            self.config["sched_month_date"] = int(self.spin_month_date.get() or 1)
            self.config["sched_specific_year"] = int(self.spin_spec_year.get() or 2026)
            self.config["sched_specific_month"] = self.combo_spec_month.current() + 1
            self.config["sched_specific_day"] = int(self.spin_spec_day.get() or 1)
            self.config["sched_interval_minutes"] = int(self.spin_interval.get() or 360)

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    # ==========================================
    # UI SETUP: LEBIH SIMPEL, BERSIH & RAPI
    # ==========================================
    def setup_ui(self):
        # 1. HEADER RINGKAS
        header = tk.Frame(self.root, bg=CLR_CARD, bd=1, relief="solid", highlightbackground=CLR_BORDER)
        header.pack(fill="x", padx=12, pady=(10, 8))

        h_left = tk.Frame(header, bg=CLR_CARD)
        h_left.pack(side="left", padx=12, pady=10)
        tk.Label(h_left, text="Gate Scanner Restarter", font=("Arial", 13, "bold"), fg=CLR_TEXT, bg=CLR_CARD).pack(anchor="w")
        self.lbl_usb_status_top = tk.Label(h_left, text="● Port USB Belum Terhubung", font=("Arial", 9), fg=CLR_RED, bg=CLR_CARD)
        self.lbl_usb_status_top.pack(anchor="w", pady=(2, 0))

        h_right = tk.Frame(header, bg=CLR_CARD)
        h_right.pack(side="right", padx=12, pady=10)
        self.lbl_clock_time = tk.Label(h_right, text="--:--:-- WIB", font=("Courier", 13, "bold"), fg=CLR_PRIMARY, bg=CLR_CARD)
        self.lbl_clock_time.pack(anchor="e")
        self.lbl_counter = tk.Label(h_right, text="Total Restart: 0x", font=("Arial", 9), fg=CLR_MUTED, bg=CLR_CARD)
        self.lbl_counter.pack(anchor="e")

        # 2. CARD KONTROL SCANNER (FOKUS UTAMA & PALING BERSIH)
        card_scan = tk.Frame(self.root, bg=CLR_CARD, bd=1, relief="solid", highlightbackground=CLR_BORDER)
        card_scan.pack(fill="x", padx=12, pady=(0, 8))

        tk.Label(card_scan, text="KONTROL SCANNER QR", font=("Arial", 9, "bold"), fg=CLR_MUTED, bg=CLR_CARD).pack(anchor="w", padx=12, pady=(8, 4))

        # 2 Kolom: Scanner 1 & Scanner 2
        row_gates = tk.Frame(card_scan, bg=CLR_CARD)
        row_gates.pack(fill="x", padx=10, pady=(0, 6))

        # Kolom Scanner 1
        box1 = tk.Frame(row_gates, bg="#f8fafc", bd=1, relief="solid", highlightbackground=CLR_BORDER, padx=10, pady=8)
        box1.pack(side="left", fill="both", expand=True, padx=(0, 5))

        tk.Label(box1, text="Scanner 1 (Gate In)", font=("Arial", 10, "bold"), fg=CLR_TEXT, bg="#f8fafc").pack(anchor="w")
        self.lbl_status_ch1 = tk.Label(box1, text="🟢 Normal (Power ON)", font=("Arial", 9), fg=CLR_GREEN, bg="#f8fafc")
        self.lbl_status_ch1.pack(anchor="w", pady=(1, 6))

        self.btn_restart_ch1 = tk.Button(
            box1,
            text="⚡ Restart Scanner 1",
            font=("Arial", 9, "bold"),
            bg=CLR_PRIMARY,
            fg="#ffffff",
            cursor="hand2",
            relief="flat",
            pady=4,
            command=lambda: self.manual_restart(1)
        )
        self.btn_restart_ch1.pack(fill="x")

        # Kolom Scanner 2
        box2 = tk.Frame(row_gates, bg="#f8fafc", bd=1, relief="solid", highlightbackground=CLR_BORDER, padx=10, pady=8)
        box2.pack(side="left", fill="both", expand=True, padx=(5, 0))

        tk.Label(box2, text="Scanner 2 (Gate Out)", font=("Arial", 10, "bold"), fg=CLR_TEXT, bg="#f8fafc").pack(anchor="w")
        self.lbl_status_ch2 = tk.Label(box2, text="🟢 Normal (Power ON)", font=("Arial", 9), fg=CLR_GREEN, bg="#f8fafc")
        self.lbl_status_ch2.pack(anchor="w", pady=(1, 6))

        self.btn_restart_ch2 = tk.Button(
            box2,
            text="⚡ Restart Scanner 2",
            font=("Arial", 9, "bold"),
            bg=CLR_PRIMARY,
            fg="#ffffff",
            cursor="hand2",
            relief="flat",
            pady=4,
            command=lambda: self.manual_restart(2)
        )
        self.btn_restart_ch2.pack(fill="x")

        # Tombol Restart Kedua Scanner Sekaligus (Staggered)
        self.btn_restart_all = tk.Button(
            card_scan,
            text="⚡ Restart Kedua Scanner (Bergiliran / Jeda 1.5s)",
            font=("Arial", 9, "bold"),
            bg="#3b82f6",
            fg="#ffffff",
            cursor="hand2",
            relief="flat",
            pady=5,
            command=lambda: self.manual_restart("ALL")
        )
        self.btn_restart_all.pack(fill="x", padx=10, pady=(2, 6))

        # Opsi Pengaturan Jeda Ringkas (Single Line)
        row_dur = tk.Frame(card_scan, bg=CLR_CARD)
        row_dur.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(row_dur, text="Durasi jeda putus daya:", font=("Arial", 8), fg=CLR_MUTED, bg=CLR_CARD).pack(side="left")
        self.spin_duration = ttk.Spinbox(row_dur, from_=2, to=15, width=3)
        self.spin_duration.set(4)
        self.spin_duration.pack(side="left", padx=4)
        tk.Label(row_dur, text="detik", font=("Arial", 8), fg=CLR_MUTED, bg=CLR_CARD).pack(side="left")

        # Tombol Manual Override yang Rapi
        btn_power_cut = tk.Button(row_dur, text="Matikan Total", font=("Arial", 7), fg=CLR_RED, bd=0, bg=CLR_CARD, cursor="hand2", command=self.open_power_menu)
        btn_power_cut.pack(side="right")

        # 3. CARD KONEKSI USB SERIAL (KOMPAK 1 BARIS)
        card_usb = tk.Frame(self.root, bg=CLR_CARD, bd=1, relief="solid", highlightbackground=CLR_BORDER)
        card_usb.pack(fill="x", padx=12, pady=(0, 8))

        row_u = tk.Frame(card_usb, bg=CLR_CARD, padx=10, pady=8)
        row_u.pack(fill="x")

        tk.Label(row_u, text="Port USB:", font=("Arial", 9, "bold"), fg=CLR_TEXT, bg=CLR_CARD).pack(side="left")
        self.port_combobox = ttk.Combobox(row_u, width=32, state="readonly")
        self.port_combobox.pack(side="left", padx=6)

        btn_rescan = tk.Button(row_u, text="🔄", font=("Arial", 8), bg="#e2e8f0", fg=CLR_TEXT, bd=1, command=lambda: self.refresh_ports(auto_select=False))
        btn_rescan.pack(side="left", padx=(0, 6))

        self.baud_combobox = ttk.Combobox(row_u, values=["9600", "19200", "115200"], width=6, state="readonly")
        self.baud_combobox.set("9600")

        self.btn_connect = tk.Button(
            row_u,
            text="Hubungkan",
            font=("Arial", 9, "bold"),
            bg=CLR_GREEN,
            fg="#ffffff",
            cursor="hand2",
            relief="flat",
            padx=8,
            command=self.toggle_connection
        )
        self.btn_connect.pack(side="right")

        self.var_autoconnect = tk.BooleanVar(value=True)
        chk_auto = tk.Checkbutton(row_u, text="Auto-Connect", variable=self.var_autoconnect, font=("Arial", 8), fg=CLR_MUTED, bg=CLR_CARD, activebackground=CLR_CARD, command=self.save_config)
        chk_auto.pack(side="right", padx=6)

        # 4. CARD PENJADWALAN OTOMATIS (LEBIH RINGKAS & BERSIH)
        card_sched = tk.Frame(self.root, bg=CLR_CARD, bd=1, relief="solid", highlightbackground=CLR_BORDER)
        card_sched.pack(fill="x", padx=12, pady=(0, 8))

        top_s = tk.Frame(card_sched, bg=CLR_CARD, padx=10, pady=(8, 4))
        top_s.pack(fill="x")

        self.var_sched_enabled = tk.BooleanVar(value=False)
        self.chk_sched = tk.Checkbutton(
            top_s,
            text="Aktifkan Jadwal Otomatis",
            variable=self.var_sched_enabled,
            font=("Arial", 9, "bold"),
            fg=CLR_TEXT,
            bg=CLR_CARD,
            activebackground=CLR_CARD,
            command=self.on_scheduler_toggle
        )
        self.chk_sched.pack(side="left")

        # Jam Eksekusi
        tk.Label(top_s, text="Jam:", font=("Arial", 8, "bold"), fg=CLR_MUTED, bg=CLR_CARD).pack(side="right", padx=(4, 0))
        self.combo_min = ttk.Combobox(top_s, values=[f"{i:02d}" for i in range(60)], width=3, state="readonly")
        self.combo_min.set("00")
        self.combo_min.pack(side="right", padx=2)
        tk.Label(top_s, text=":", font=("Arial", 9, "bold"), bg=CLR_CARD).pack(side="right")
        self.combo_hour = ttk.Combobox(top_s, values=[f"{i:02d}" for i in range(24)], width=3, state="readonly")
        self.combo_hour.set("02")
        self.combo_hour.pack(side="right", padx=2)

        # Target Dropdown
        self.combo_sched_target = ttk.Combobox(top_s, values=["Semua Scanner (ALL)", "Scanner 1 Saja", "Scanner 2 Saja"], width=18, state="readonly")
        self.combo_sched_target.set("Semua Scanner (ALL)")
        self.combo_sched_target.pack(side="right", padx=8)

        # Tabs Header
        self.notebook = ttk.Notebook(card_sched)
        self.notebook.pack(fill="x", padx=10, pady=2)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.save_config())

        # TAB 1: Setiap Hari
        self.tab_daily = tk.Frame(self.notebook, bg=CLR_CARD, padx=8, pady=6)
        self.notebook.add(self.tab_daily, text="Setiap Hari")
        tk.Label(self.tab_daily, text="Restart otomatis setiap hari pada jam yang dipilih (Rekomendasi stasiun: 02:00 WIB).", font=("Arial", 8), fg=CLR_MUTED, bg=CLR_CARD).pack(anchor="w")

        # TAB 2: Hari Tertentu
        self.tab_weekly = tk.Frame(self.notebook, bg=CLR_CARD, padx=8, pady=6)
        self.notebook.add(self.tab_weekly, text="Hari Tertentu")
        wf = tk.Frame(self.tab_weekly, bg=CLR_CARD)
        wf.pack(fill="x")
        for day in HARI_INDONESIA:
            var = tk.BooleanVar(value=True)
            self.day_check_vars[day] = var
            chk = tk.Checkbutton(wf, text=day[:3], variable=var, font=("Arial", 8), bg=CLR_CARD, fg=CLR_TEXT, activebackground=CLR_CARD, command=self.save_config)
            chk.pack(side="left", padx=2)

        # TAB 3: Tanggal Bulanan
        self.tab_monthly = tk.Frame(self.notebook, bg=CLR_CARD, padx=8, pady=6)
        self.notebook.add(self.tab_monthly, text="Tanggal Bulanan")
        mf = tk.Frame(self.tab_monthly, bg=CLR_CARD)
        mf.pack(fill="x")
        tk.Label(mf, text="Setiap Tanggal:", font=("Arial", 8), fg=CLR_TEXT, bg=CLR_CARD).pack(side="left")
        self.spin_month_date = ttk.Spinbox(mf, from_=1, to=31, width=3)
        self.spin_month_date.set(1)
        self.spin_month_date.pack(side="left", padx=4)
        tk.Label(mf, text="tiap bulan.", font=("Arial", 8), fg=CLR_MUTED, bg=CLR_CARD).pack(side="left")

        # TAB 4: Tanggal Spesifik
        self.tab_specific = tk.Frame(self.notebook, bg=CLR_CARD, padx=8, pady=6)
        self.notebook.add(self.tab_specific, text="Tanggal Spesifik")
        sf = tk.Frame(self.tab_specific, bg=CLR_CARD)
        sf.pack(fill="x")
        self.spin_spec_day = ttk.Spinbox(sf, from_=1, to=31, width=3)
        self.spin_spec_day.set(datetime.datetime.now().day)
        self.spin_spec_day.pack(side="left", padx=2)
        self.combo_spec_month = ttk.Combobox(sf, values=BULAN_INDONESIA, width=9, state="readonly")
        self.combo_spec_month.current(datetime.datetime.now().month - 1)
        self.combo_spec_month.pack(side="left", padx=2)
        self.spin_spec_year = ttk.Spinbox(sf, from_=2025, to=2035, width=5)
        self.spin_spec_year.set(datetime.datetime.now().year)
        self.spin_spec_year.pack(side="left", padx=2)

        # TAB 5: Interval
        self.tab_interval = tk.Frame(self.notebook, bg=CLR_CARD, padx=8, pady=6)
        self.notebook.add(self.tab_interval, text="Interval Rutin")
        inf = tk.Frame(self.tab_interval, bg=CLR_CARD)
        inf.pack(fill="x")
        tk.Label(inf, text="Ulangi setiap:", font=("Arial", 8), fg=CLR_TEXT, bg=CLR_CARD).pack(side="left")
        self.spin_interval = ttk.Spinbox(inf, from_=10, to=2880, width=5)
        self.spin_interval.set(360)
        self.spin_interval.pack(side="left", padx=4)
        tk.Label(inf, text="menit", font=("Arial", 8), fg=CLR_MUTED, bg=CLR_CARD).pack(side="left")

        # Status Hitung Mundur Jadwal
        self.lbl_sched_status = tk.Label(
            card_sched,
            text="Jadwal: Nonaktif",
            font=("Arial", 8),
            fg=CLR_MUTED,
            bg=CLR_CARD
        )
        self.lbl_sched_status.pack(anchor="w", padx=10, pady=(3, 8))

        # 5. CARD LOG AKTIVITAS (RINGKAS)
        card_log = tk.Frame(self.root, bg=CLR_CARD, bd=1, relief="solid", highlightbackground=CLR_BORDER)
        card_log.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        log_head = tk.Frame(card_log, bg=CLR_CARD, padx=10, pady=(6, 2))
        log_head.pack(fill="x")
        tk.Label(log_head, text="LOG AKTIVITAS", font=("Arial", 8, "bold"), fg=CLR_MUTED, bg=CLR_CARD).pack(side="left")
        tk.Button(log_head, text="Bersihkan", font=("Arial", 7), fg=CLR_MUTED, bd=0, bg=CLR_CARD, cursor="hand2", command=self.clear_log).pack(side="right")

        self.txt_log = tk.Text(card_log, height=4, font=("Courier", 8), bg=CLR_DARK, fg="#38bdf8", relief="flat", wrap="word")
        self.txt_log.pack(fill="both", expand=True, padx=8, pady=(0, 6))

    def apply_config_to_ui(self):
        self.baud_combobox.set(str(self.config.get("baud_rate", 9600)))
        self.spin_duration.set(str(self.config.get("restart_duration_sec", 4)))
        self.var_autoconnect.set(bool(self.config.get("auto_connect_usb", True)))
        self.var_sched_enabled.set(bool(self.config.get("scheduler_enabled", False)))

        raw_target = self.config.get("sched_target", "ALL")
        if "1" in raw_target:
            self.combo_sched_target.set("Scanner 1 Saja")
        elif "2" in raw_target:
            self.combo_sched_target.set("Scanner 2 Saja")
        else:
            self.combo_sched_target.set("Semua Scanner (ALL)")

        try:
            self.notebook.select(int(self.config.get("active_tab", 0)))
        except Exception:
            pass

        self.combo_hour.set(str(self.config.get("sched_hour", "02")).zfill(2))
        self.combo_min.set(str(self.config.get("sched_minute", "00")).zfill(2))

        saved_days = self.config.get("sched_days", HARI_INDONESIA)
        if isinstance(saved_days, list):
            for d, v in self.day_check_vars.items():
                v.set(d in saved_days)

        self.spin_month_date.set(str(self.config.get("sched_month_date", 1)))
        self.spin_spec_year.set(str(self.config.get("sched_specific_year", 2026)))

        raw_m = self.config.get("sched_specific_month", 11)
        m_idx = (raw_m - 1) if isinstance(raw_m, int) else 10
        if 0 <= m_idx < len(BULAN_INDONESIA):
            self.combo_spec_month.current(m_idx)

        self.spin_spec_day.set(str(self.config.get("sched_specific_day", 26)))
        self.spin_interval.set(str(self.config.get("sched_interval_minutes", 360)))

    # ==========================================
    # LOGGING
    # ==========================================
    def log(self, message):
        ts = time.strftime("%H:%M:%S")
        ts_full = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {message}"

        def _ui():
            self.txt_log.config(state="normal")
            self.txt_log.insert("end", line + "\n")
            self.txt_log.see("end")
            self.txt_log.config(state="disabled")
        self.root.after(0, _ui)

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts_full}] {message}\n")
        except Exception:
            pass

    def clear_log(self):
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.config(state="disabled")

    # ==========================================
    # EPC CLOCK
    # ==========================================
    def start_epc_clock_timer(self):
        def _tick():
            now = datetime.datetime.now()
            time_str = now.strftime("%H:%M:%S WIB")
            self.lbl_clock_time.config(text=time_str)
            if self.is_running:
                self.root.after(1000, _tick)
        self.root.after(200, _tick)

    # ==========================================
    # USB PORT SCAN & HOTPLUG
    # ==========================================
    def get_valid_physical_ports(self):
        ports = serial.tools.list_ports.comports()
        valid = []
        for p in ports:
            dev = p.device
            desc = p.description or ""
            if any(ign in dev.lower() for ign in ["debug-console", "bluetooth", "wlan"]):
                continue
            valid.append((dev, desc))
        return valid

    def refresh_ports(self, auto_select=True):
        valid_ports = self.get_valid_physical_ports()
        display_list = [SIMULATION_PORT]

        arduino_candidate = None
        for dev, desc in valid_ports:
            display_str = f"{dev} ({desc})" if desc and desc != "n/a" else dev
            display_list.append(display_str)
            if any(k in dev.lower() for k in ["usbmodem", "usbserial", "com"]) or "arduino" in desc.lower():
                if not arduino_candidate:
                    arduino_candidate = display_str

        self.port_combobox["values"] = display_list

        if auto_select:
            last_saved = self.config.get("last_port", "")
            matched = [item for item in display_list if last_saved and last_saved in item]
            if matched:
                self.port_combobox.set(matched[0])
            elif arduino_candidate:
                self.port_combobox.set(arduino_candidate)
            elif len(display_list) > 1:
                self.port_combobox.set(display_list[1])
            else:
                self.port_combobox.set(SIMULATION_PORT)

    def get_selected_device_port(self):
        raw = self.port_combobox.get()
        if not raw:
            return ""
        if raw == SIMULATION_PORT:
            return SIMULATION_PORT
        return raw.split(" ")[0].strip()

    def start_usb_hotplug_monitor(self):
        def _monitor():
            last_ports_set = None
            while self.is_running:
                try:
                    ports = self.get_valid_physical_ports()
                    current_devices = tuple(sorted(p[0] for p in ports))

                    if last_ports_set is None:
                        last_ports_set = current_devices
                    elif current_devices != last_ports_set:
                        last_ports_set = current_devices
                        self.root.after(0, lambda: self.on_usb_change(ports))

                    if self.ser and self.ser.is_open:
                        if not any(self.ser.port == p[0] for p in ports):
                            self.root.after(0, self.on_cable_disconnected)

                except Exception:
                    pass
                time.sleep(2.0)

        threading.Thread(target=_monitor, daemon=True).start()

    def on_usb_change(self, ports):
        self.refresh_ports(auto_select=False)
        devices = [p[0] for p in ports]
        self.log(f"USB: {len(devices)} port terdeteksi.")

        if not (self.ser and self.ser.is_open) and self.var_autoconnect.get():
            arduino_ports = [d for d in devices if any(k in d.lower() for k in ["usbmodem", "usbserial", "com"])]
            if arduino_ports:
                target_port = arduino_ports[0]
                for val in self.port_combobox["values"]:
                    if target_port in val:
                        self.port_combobox.set(val)
                        break
                self.connect(silent=True)

    def on_cable_disconnected(self):
        self.log("Kabel USB terputus!")
        self.disconnect()

    # ==========================================
    # KONEKSI
    # ==========================================
    def toggle_connection(self):
        if self.is_simulation or (self.ser and self.ser.is_open):
            self.disconnect()
        else:
            self.connect(silent=False)

    def connect(self, silent=False):
        port = self.get_selected_device_port()
        if not port:
            if not silent:
                messagebox.showwarning("Peringatan", "Pilih port USB terlebih dahulu.")
            return False

        if port == SIMULATION_PORT:
            self.is_simulation = True
            self.btn_connect.config(text="Putuskan", bg=CLR_RED)
            self.lbl_usb_status_top.config(text="● Terhubung (Simulasi Virtual)", fg=CLR_PRIMARY)
            self.port_combobox.config(state="disabled")
            self.log("[Simulasi] Mode Virtual Arduino Mega aktif.")
            self.save_config()
            return True

        baud = int(self.baud_combobox.get() or 9600)
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            time.sleep(2)
            self.is_simulation = False
            self.btn_connect.config(text="Putuskan", bg=CLR_RED)
            self.lbl_usb_status_top.config(text=f"● Terhubung ({port})", fg=CLR_GREEN)
            self.port_combobox.config(state="disabled")
            self.save_config()
            self.log(f"Terhubung ke Arduino Mega di {port}.")
            threading.Thread(target=self.serial_reader_worker, daemon=True).start()
            self.send_serial_command("STATUS")
            return True
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Gagal membuka {port}:\n{e}")
            self.disconnect()
            return False

    def disconnect(self):
        self.is_simulation = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None

        self.btn_connect.config(text="Hubungkan", bg=CLR_GREEN)
        self.lbl_usb_status_top.config(text="● Port USB Terputus", fg=CLR_RED)
        self.port_combobox.config(state="readonly")
        self.log("Koneksi USB ditutup.")

    def serial_reader_worker(self):
        while self.is_running and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self.log(f"[Arduino] {line}")
                        self.parse_arduino_response(line)
                else:
                    time.sleep(0.05)
            except Exception:
                break

    def parse_arduino_response(self, line):
        if line.startswith("STATUS:CH1="):
            parts = line.split(":")
            for p in parts[1:]:
                if "=" in p:
                    k, v = p.split("=")
                    ch = int(k.replace("CH", ""))
                    self.update_channel_badge(ch, v)
        elif "RESTARTING:CH=" in line:
            for part in line.split(":"):
                if part.startswith("CH="):
                    ch = int(part.replace("CH=", ""))
                    self.update_channel_badge(ch, "RESTARTING")
        elif "STATUS:STAGGERED:CH1_CUT" in line:
            self.update_channel_badge(1, "RESTARTING")
        elif "STATUS:STAGGERED:CH2_CUT" in line:
            self.update_channel_badge(2, "RESTARTING")
        elif "STATUS:RESTART_COMPLETE:CH" in line:
            ch = int(line.split("CH")[-1])
            self.update_channel_badge(ch, "ON")
        elif "STATUS:STAGGERED_COMPLETE:ALL_ON" in line:
            self.update_channel_badge(1, "ON")
            self.update_channel_badge(2, "ON")

    def update_channel_badge(self, channel, state):
        self.relay_states[channel] = state
        lbl = self.lbl_status_ch1 if channel == 1 else self.lbl_status_ch2

        if state == "ON":
            lbl.config(text="🟢 Normal (Power ON)", fg=CLR_GREEN)
        elif state == "RESTARTING":
            lbl.config(text="🟡 Sedang Restart (4s)...", fg=CLR_AMBER)
        elif state == "OFF":
            lbl.config(text="🔴 Daya Mati (OFF)", fg=CLR_RED)

    def send_serial_command(self, cmd):
        if self.is_simulation:
            self.log(f"[Simulasi] -> {cmd}")
            self.simulate_hardware(cmd)
            return True

        if not (self.ser and self.ser.is_open):
            self.log("Perintah dibatalkan: Port USB belum terhubung.")
            return False

        try:
            self.ser.write((cmd + "\n").encode('utf-8'))
            self.ser.flush()
            self.log(f"[Kirim] -> {cmd}")
            return True
        except Exception as e:
            self.log(f"Error kirim: {e}")
            return False

    def simulate_hardware(self, cmd):
        dur = int(self.spin_duration.get() or 4)

        if cmd.startswith("RESTART:ALL"):
            self.update_channel_badge(1, "RESTARTING")
            threading.Timer(1.5, lambda: self.update_channel_badge(2, "RESTARTING")).start()
            threading.Timer(dur + 2.0, lambda: (
                self.update_channel_badge(1, "ON"),
                self.update_channel_badge(2, "ON"),
                self.log("[Simulasi] Kedua scanner normal kembali.")
            )).start()

        elif cmd.startswith("RESTART:1"):
            self.update_channel_badge(1, "RESTARTING")
            threading.Timer(dur, lambda: (
                self.update_channel_badge(1, "ON"),
                self.log("[Simulasi] Scanner 1 normal kembali.")
            )).start()

        elif cmd.startswith("RESTART:2"):
            self.update_channel_badge(2, "RESTARTING")
            threading.Timer(dur, lambda: (
                self.update_channel_badge(2, "ON"),
                self.log("[Simulasi] Scanner 2 normal kembali.")
            )).start()

        elif cmd == "POWER:1:OFF":
            self.update_channel_badge(1, "OFF")
        elif cmd == "POWER:1:ON":
            self.update_channel_badge(1, "ON")
        elif cmd == "POWER:2:OFF":
            self.update_channel_badge(2, "OFF")
        elif cmd == "POWER:2:ON":
            self.update_channel_badge(2, "ON")

    # ==========================================
    # AKSI
    # ==========================================
    def check_ready(self):
        if self.is_simulation or (self.ser and self.ser.is_open):
            return True
        if self.connect(silent=True):
            return True
        messagebox.showinfo("Info", "Silakan klik tombol 'Hubungkan' terlebih dahulu.")
        return False

    def manual_restart(self, channel):
        if not self.check_ready():
            return
        ch_name = f"Scanner {channel}" if channel != "ALL" else "Kedua Scanner"
        if messagebox.askyesno("Konfirmasi", f"Restart {ch_name} sekarang?"):
            self.trigger_restart(channel=channel, source="MANUAL")

    def trigger_restart(self, channel="ALL", source="MANUAL"):
        dur_sec = int(self.spin_duration.get() or 4)
        dur_ms = dur_sec * 1000

        def _exec():
            self.btn_restart_ch1.config(state="disabled")
            self.btn_restart_ch2.config(state="disabled")
            self.btn_restart_all.config(state="disabled")

            self.restart_count += 1
            self.lbl_counter.config(text=f"Total Restart: {self.restart_count}x")

            if channel == "ALL":
                self.log(f"[{source}] Restart Semua Scanner (Staggered)...")
                self.send_serial_command(f"RESTART:ALL:{dur_ms}")
                time.sleep(dur_sec + 2.5)
            else:
                self.log(f"[{source}] Restart Scanner {channel}...")
                self.send_serial_command(f"RESTART:{channel}:{dur_ms}")
                time.sleep(dur_sec + 0.8)

            if self.is_simulation or (self.ser and self.ser.is_open):
                self.btn_restart_ch1.config(state="normal")
                self.btn_restart_ch2.config(state="normal")
                self.btn_restart_all.config(state="normal")

        threading.Thread(target=_exec, daemon=True).start()

    def open_power_menu(self):
        # Dialog ringkas jika teknisi butuh matikan total arus
        win = tk.Toplevel(self.root)
        win.title("Kontrol Daya Manual")
        win.geometry("300x160")
        win.configure(bg=CLR_CARD)
        win.transient(self.root)

        tk.Label(win, text="Matikan / Nyalakan Daya Scanner:", font=("Arial", 9, "bold"), bg=CLR_CARD).pack(pady=8)
        
        f1 = tk.Frame(win, bg=CLR_CARD)
        f1.pack(fill="x", padx=12, pady=4)
        tk.Label(f1, text="Scanner 1:", font=("Arial", 9), bg=CLR_CARD).pack(side="left")
        tk.Button(f1, text="Matikan (OFF)", bg=CLR_RED, fg="white", font=("Arial", 8), command=lambda: self.send_serial_command("POWER:1:OFF")).pack(side="right", padx=2)
        tk.Button(f1, text="Nyalakan (ON)", bg=CLR_GREEN, fg="white", font=("Arial", 8), command=lambda: self.send_serial_command("POWER:1:ON")).pack(side="right", padx=2)

        f2 = tk.Frame(win, bg=CLR_CARD)
        f2.pack(fill="x", padx=12, pady=4)
        tk.Label(f2, text="Scanner 2:", font=("Arial", 9), bg=CLR_CARD).pack(side="left")
        tk.Button(f2, text="Matikan (OFF)", bg=CLR_RED, fg="white", font=("Arial", 8), command=lambda: self.send_serial_command("POWER:2:OFF")).pack(side="right", padx=2)
        tk.Button(f2, text="Nyalakan (ON)", bg=CLR_GREEN, fg="white", font=("Arial", 8), command=lambda: self.send_serial_command("POWER:2:ON")).pack(side="right", padx=2)

    # ==========================================
    # SCHEDULER ENGINE
    # ==========================================
    def on_scheduler_toggle(self):
        self.save_config()
        if self.var_sched_enabled.get():
            if self.notebook.index(self.notebook.select()) == 4:
                self.last_interval_trigger = time.time()
            self.log("Jadwal otomatis diaktifkan.")
        else:
            self.log("Jadwal otomatis dinonaktifkan.")
            self.lbl_sched_status.config(text="Jadwal: Nonaktif", fg=CLR_MUTED)

    def get_target_channel_param(self):
        raw = self.combo_sched_target.get()
        if "1" in raw:
            return 1
        elif "2" in raw:
            return 2
        return "ALL"

    def get_target_hour_min(self):
        try:
            return int(self.combo_hour.get() or 2), int(self.combo_min.get() or 0)
        except Exception:
            return 2, 0

    def start_scheduler_engine(self):
        def _loop():
            last_fired_minute = -1
            while self.is_running:
                try:
                    if self.var_sched_enabled.get():
                        now = datetime.datetime.now()
                        tab_idx = self.notebook.index(self.notebook.select())
                        target_ch = self.get_target_channel_param()

                        if tab_idx == 0: # Setiap Hari
                            th, tm = self.get_target_hour_min()
                            if now.hour == th and now.minute == tm and now.minute != last_fired_minute:
                                last_fired_minute = now.minute
                                self.log(f"[Jadwal] Jam {th:02d}:{tm:02d} tercapai. Restart target: {target_ch}")
                                self.trigger_restart(channel=target_ch, source="AUTO-DAILY")

                            target_dt = now.replace(hour=th, minute=tm, second=0, microsecond=0)
                            if target_dt <= now:
                                target_dt += datetime.timedelta(days=1)
                            diff = target_dt - now
                            h, rem = divmod(int(diff.total_seconds()), 3600)
                            m, s = divmod(rem, 60)
                            self.root.after(0, lambda: self.lbl_sched_status.config(
                                text=f"Jadwal Harian: Pukul {th:02d}:{tm:02d} WIB (dlm ~{h}j {m}m {s}d)",
                                fg=CLR_PRIMARY
                            ))

                        elif tab_idx == 4: # Interval
                            intv_min = int(self.spin_interval.get() or 360)
                            intv_sec = intv_min * 60
                            elapsed = time.time() - self.last_interval_trigger

                            if elapsed >= intv_sec:
                                self.last_interval_trigger = time.time()
                                self.log(f"[Jadwal] Interval {intv_min} menit tercapai. Restart...")
                                self.trigger_restart(channel=target_ch, source="AUTO-INTERVAL")

                            rem = max(0, int(intv_sec - elapsed))
                            m, s = divmod(rem, 60)
                            h, m = divmod(m, 60)
                            self.root.after(0, lambda: self.lbl_sched_status.config(
                                text=f"Jadwal Interval ({intv_min}m): Hitung mundur {h:02d}:{m:02d}:{s:02d}",
                                fg=CLR_PRIMARY
                            ))

                    time.sleep(1)
                except Exception:
                    time.sleep(1)

        threading.Thread(target=_loop, daemon=True).start()

    def on_closing(self):
        self.is_running = False
        self.save_config()
        self.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SimplifiedStationGateRestarterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
