"""
=====================================================================
EPC HARDWARE RESTARTER & SCHEDULER (MULTI-CHANNEL GATE SCANNER)
=====================================================================
Target Perangkat : 2x (hingga 4x) Scanner QR Turnstile Gate Kereta
Target Board     : Arduino Mega 2560 (Relay 2-Channel / 4-Channel Active-LOW)
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
    "sched_target": "ALL",         # "ALL", "CH1", "CH2"
    "active_tab": 0,               # 0: Daily, 1: Weekly, 2: Monthly, 3: Specific Date, 4: Interval
    "sched_hour": "02",
    "sched_minute": "00",
    "sched_days": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"],
    "sched_month_date": 1,
    "sched_specific_year": 2026,
    "sched_specific_month": 11,
    "sched_specific_day": 26,
    "sched_interval_minutes": 360
}

SIMULATION_PORT = "[SIMULASI / DEMO VIRTUAL GATE STASIUN]"

# Palet Warna Industrial Modern (Kompatibel 100% Windows & macOS Dark/Light Mode)
BG_DARK = "#0f172a"      # Slate 900
BG_HEADER = "#1e293b"    # Slate 800
BG_PANEL = "#f8fafc"     # Slate 50
BG_CARD = "#ffffff"      # Pure White
FG_TEXT = "#0f172a"      # High contrast dark text
FG_MUTED = "#64748b"     # Slate 500
BORDER_COLOR = "#cbd5e1" # Slate 300

CLR_BLUE = "#2563eb"     # Blue 600
CLR_GREEN = "#16a34a"    # Green 600
CLR_RED = "#dc2626"      # Red 600
CLR_AMBER = "#d97706"    # Amber 600
CLR_CYAN = "#0284c7"     # Sky 600

class ModernStationGateRestarterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ GATE SCANNER RESTARTER & ADVANCED SCHEDULER (MULTI-CHANNEL)")
        self.root.geometry("780x780")
        self.root.minsize(720, 680)
        self.root.configure(bg=BG_PANEL)

        # Mencegah glitch hitam pada macOS Tkinter
        self.setup_crossplatform_theme()

        self.ser = None
        self.is_simulation = False
        self.is_running = True
        self.config = self.load_config()

        # State Variables Per-Channel
        self.relay_states = {
            1: "ON", # Scanner 1 (Gate In)
            2: "ON", # Scanner 2 (Gate Out)
            3: "ON", # Aux 3
            4: "ON"  # Aux 4
        }
        self.restart_count_ch1 = 0
        self.restart_count_ch2 = 0
        self.restart_count_all = 0
        self.last_interval_trigger = time.time()
        self.day_check_vars = {}

        self.setup_ui()
        self.apply_config_to_ui()
        self.refresh_ports(auto_select=True)

        # Background Engines
        self.start_epc_clock_timer()
        self.start_usb_hotplug_monitor()
        self.start_scheduler_engine()

    def setup_crossplatform_theme(self):
        style = ttk.Style()
        try:
            # Gunakan theme clam agar render warna konsisten di Mac & Windows
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        # Konfigurasi style ttk agar tidak glitch ke warna hitam di Mac Dark Mode
        style.configure("TNotebook", background=BG_PANEL, borderwidth=0)
        style.configure("TNotebook.Tab", background="#e2e8f0", foreground=FG_TEXT, padding=[10, 4], font=("Arial", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", BG_CARD)], foreground=[("selected", CLR_BLUE)])
        style.configure("TCombobox", fieldbackground="#ffffff", background="#ffffff", foreground=FG_TEXT)
        style.configure("TSpinbox", fieldbackground="#ffffff", background="#ffffff", foreground=FG_TEXT)

    # ==========================================
    # KONFIGURASI PERSISTEN
    # ==========================================
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
    # DESAIN TAMPILAN GUI (HIGH-CONTRAST & CRISP)
    # ==========================================
    def setup_ui(self):
        # 1. HEADER UTAMA & JAM EPC HOST
        header = tk.Frame(self.root, bg=BG_HEADER, relief="flat")
        header.pack(fill="x", padx=10, pady=(8, 4))

        tbox = tk.Frame(header, bg=BG_HEADER)
        tbox.pack(side="left", padx=12, pady=8)
        lbl_app = tk.Label(tbox, text="⚡ EPC RAILWAY GATE RESTARTER (MULTI-CHANNEL)", font=("Arial", 12, "bold"), fg="#ffffff", bg=BG_HEADER)
        lbl_app.pack(anchor="w")
        lbl_sub = tk.Label(tbox, text="Pengendali Scanner QR Gate Stasiun (Relay NC Fail-Safe + Watchdog Timer)", font=("Arial", 8), fg="#94a3b8", bg=BG_HEADER)
        lbl_sub.pack(anchor="w")

        # Jam Host EPC
        cbox = tk.Frame(header, bg=BG_DARK, padx=10, pady=4, relief="ridge", bd=1)
        cbox.pack(side="right", padx=12, pady=6)
        self.lbl_clock_time = tk.Label(cbox, text="--:--:-- WIB", font=("Courier", 12, "bold"), fg="#38bdf8", bg=BG_DARK)
        self.lbl_clock_time.pack(anchor="e")
        self.lbl_clock_date = tk.Label(cbox, text="Waktu Host Gate EPC", font=("Arial", 8), fg="#94a3b8", bg=BG_DARK)
        self.lbl_clock_date.pack(anchor="e")

        # 2. STATUS BADGES PER-CHANNEL SCANNER
        sbar = tk.Frame(self.root, bg=BG_CARD, relief="solid", bd=1, highlightbackground=BORDER_COLOR)
        sbar.pack(fill="x", padx=10, pady=4)

        # Status USB
        b0 = tk.Frame(sbar, bg=BG_CARD, padx=8, pady=5)
        b0.pack(side="left", expand=True, fill="both")
        tk.Label(b0, text="KONEKSI USB ARDUINO", font=("Arial", 7, "bold"), fg=FG_MUTED, bg=BG_CARD).pack(anchor="w")
        self.lbl_conn_badge = tk.Label(b0, text="● TERPUTUS", font=("Arial", 9, "bold"), fg=CLR_RED, bg=BG_CARD)
        self.lbl_conn_badge.pack(anchor="w")

        # Status Scanner 1 (Gate In)
        b1 = tk.Frame(sbar, bg=BG_CARD, padx=8, pady=5)
        b1.pack(side="left", expand=True, fill="both")
        tk.Label(b1, text="SCANNER 1 (GATE IN)", font=("Arial", 7, "bold"), fg=FG_MUTED, bg=BG_CARD).pack(anchor="w")
        self.lbl_ch1_badge = tk.Label(b1, text="🟢 DAYA ON (NC)", font=("Arial", 9, "bold"), fg=CLR_GREEN, bg=BG_CARD)
        self.lbl_ch1_badge.pack(anchor="w")

        # Status Scanner 2 (Gate Out)
        b2 = tk.Frame(sbar, bg=BG_CARD, padx=8, pady=5)
        b2.pack(side="left", expand=True, fill="both")
        tk.Label(b2, text="SCANNER 2 (GATE OUT)", font=("Arial", 7, "bold"), fg=FG_MUTED, bg=BG_CARD).pack(anchor="w")
        self.lbl_ch2_badge = tk.Label(b2, text="🟢 DAYA ON (NC)", font=("Arial", 9, "bold"), fg=CLR_GREEN, bg=BG_CARD)
        self.lbl_ch2_badge.pack(anchor="w")

        # Total Counter
        b3 = tk.Frame(sbar, bg=BG_CARD, padx=8, pady=5)
        b3.pack(side="left", expand=True, fill="both")
        tk.Label(b3, text="TOTAL EKSEKUSI RESTART", font=("Arial", 7, "bold"), fg=FG_MUTED, bg=BG_CARD).pack(anchor="w")
        self.lbl_counter_badge = tk.Label(b3, text="0x", font=("Arial", 9, "bold"), fg=FG_TEXT, bg=BG_CARD)
        self.lbl_counter_badge.pack(anchor="w")

        # 3. KARTU SELEKSI PORT USB
        usb_card = tk.LabelFrame(
            self.root,
            text=" 🔌 1. PORT KOMUNIKASI SERIAL / USB ARDUINO ",
            font=("Arial", 8, "bold"),
            fg=FG_TEXT,
            bg=BG_CARD,
            padx=10,
            pady=6,
            relief="solid",
            bd=1
        )
        usb_card.pack(fill="x", padx=10, pady=4)

        row_u1 = tk.Frame(usb_card, bg=BG_CARD)
        row_u1.pack(fill="x", pady=2)

        tk.Label(row_u1, text="Port USB:", font=("Arial", 9, "bold"), bg=BG_CARD, fg=FG_TEXT).pack(side="left")
        self.port_combobox = ttk.Combobox(row_u1, width=36, font=("Arial", 9), state="readonly")
        self.port_combobox.pack(side="left", padx=6)

        btn_rescan = tk.Button(
            row_u1,
            text="🔄 Refresh",
            font=("Arial", 8, "bold"),
            bg="#e2e8f0",
            fg=FG_TEXT,
            command=lambda: self.refresh_ports(auto_select=False)
        )
        btn_rescan.pack(side="left", padx=2)

        self.var_autoconnect = tk.BooleanVar(value=True)
        chk_auto = tk.Checkbutton(
            row_u1,
            text="Auto-Connect saat USB dicolok",
            variable=self.var_autoconnect,
            font=("Arial", 8),
            bg=BG_CARD,
            fg=FG_MUTED,
            activebackground=BG_CARD,
            command=self.save_config
        )
        chk_auto.pack(side="right")

        row_u2 = tk.Frame(usb_card, bg=BG_CARD)
        row_u2.pack(fill="x", pady=(4, 2))

        tk.Label(row_u2, text="Baud: 9600 (Mega 2560)", font=("Arial", 8), bg=BG_CARD, fg=FG_MUTED).pack(side="left")
        self.baud_combobox = ttk.Combobox(row_u2, values=["9600", "19200", "57600", "115200"], width=6, state="readonly")
        self.baud_combobox.set("9600")

        self.btn_connect = tk.Button(
            row_u2,
            text="🟢 HUBUNGKAN KE HARDWARE",
            font=("Arial", 9, "bold"),
            bg=CLR_GREEN,
            fg="#ffffff",
            cursor="hand2",
            relief="raised",
            command=self.toggle_connection
        )
        self.btn_connect.pack(side="right", fill="x", expand=True, padx=(15, 0))

        # 4. KARTU KONTROL RESTART MULTI-CHANNEL (MANUAL)
        ctrl_card = tk.LabelFrame(
            self.root,
            text=" ⚡ 2. KONTROL MANUAL SCANNER QR (PER-CHANNEL & SERENTAK) ",
            font=("Arial", 8, "bold"),
            fg=FG_TEXT,
            bg=BG_CARD,
            padx=10,
            pady=6,
            relief="solid",
            bd=1
        )
        ctrl_card.pack(fill="x", padx=10, pady=4)

        # Durasi Jeda
        dur_frame = tk.Frame(ctrl_card, bg=BG_CARD)
        dur_frame.pack(fill="x", pady=(0, 4))
        tk.Label(dur_frame, text="Durasi Jeda Arus Terputus:", font=("Arial", 9), bg=BG_CARD, fg=FG_TEXT).pack(side="left")
        self.spin_duration = ttk.Spinbox(dur_frame, from_=2, to=15, width=4)
        self.spin_duration.set(4)
        self.spin_duration.pack(side="left", padx=6)
        tk.Label(dur_frame, text="detik  (Standar Turnstile Gate Kereta: 3–4 detik)", font=("Arial", 8), bg=BG_CARD, fg=FG_MUTED).pack(side="left")

        # Baris Tombol Kontrol Per-Channel
        row_ch = tk.Frame(ctrl_card, bg=BG_CARD)
        row_ch.pack(fill="x", pady=2)

        # Scanner 1 Box
        box_ch1 = tk.LabelFrame(row_ch, text=" Scanner 1 (Gate In) ", font=("Arial", 8, "bold"), fg=CLR_BLUE, bg="#eff6ff")
        box_ch1.pack(side="left", fill="both", expand=True, padx=(0, 4), pady=2)

        self.btn_restart_ch1 = tk.Button(
            box_ch1,
            text="⚡ RESTART SCANNER 1",
            font=("Arial", 9, "bold"),
            bg=CLR_BLUE,
            fg="#ffffff",
            cursor="hand2",
            command=lambda: self.manual_restart_clicked(channel=1)
        )
        self.btn_restart_ch1.pack(fill="x", padx=4, pady=3)

        row_p1 = tk.Frame(box_ch1, bg="#eff6ff")
        row_p1.pack(fill="x", padx=4, pady=(0, 3))
        self.btn_off_ch1 = tk.Button(row_p1, text="🔴 OFF", font=("Arial", 7, "bold"), bg=CLR_RED, fg="#ffffff", command=lambda: self.on_power_click("POWER:1:OFF"))
        self.btn_off_ch1.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.btn_on_ch1 = tk.Button(row_p1, text="🟢 ON", font=("Arial", 7, "bold"), bg=CLR_GREEN, fg="#ffffff", command=lambda: self.on_power_click("POWER:1:ON"))
        self.btn_on_ch1.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # Scanner 2 Box
        box_ch2 = tk.LabelFrame(row_ch, text=" Scanner 2 (Gate Out) ", font=("Arial", 8, "bold"), fg=CLR_CYAN, bg="#f0f9ff")
        box_ch2.pack(side="left", fill="both", expand=True, padx=4, pady=2)

        self.btn_restart_ch2 = tk.Button(
            box_ch2,
            text="⚡ RESTART SCANNER 2",
            font=("Arial", 9, "bold"),
            bg=CLR_CYAN,
            fg="#ffffff",
            cursor="hand2",
            command=lambda: self.manual_restart_clicked(channel=2)
        )
        self.btn_restart_ch2.pack(fill="x", padx=4, pady=3)

        row_p2 = tk.Frame(box_ch2, bg="#f0f9ff")
        row_p2.pack(fill="x", padx=4, pady=(0, 3))
        self.btn_off_ch2 = tk.Button(row_p2, text="🔴 OFF", font=("Arial", 7, "bold"), bg=CLR_RED, fg="#ffffff", command=lambda: self.on_power_click("POWER:2:OFF"))
        self.btn_off_ch2.pack(side="left", fill="x", expand=True, padx=(0, 2))
        self.btn_on_ch2 = tk.Button(row_p2, text="🟢 ON", font=("Arial", 7, "bold"), bg=CLR_GREEN, fg="#ffffff", command=lambda: self.on_power_click("POWER:2:ON"))
        self.btn_on_ch2.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # Tombol Restart Serentak (Staggered)
        self.btn_restart_all = tk.Button(
            ctrl_card,
            text="⚡ RESTART SEMUA SCANNER (STAGGERED / BERGILIRAN DENGAN JEDA)",
            font=("Arial", 10, "bold"),
            bg="#3b82f6",
            fg="#ffffff",
            height=1,
            cursor="hand2",
            command=lambda: self.manual_restart_clicked(channel="ALL")
        )
        self.btn_restart_all.pack(fill="x", pady=(4, 2))

        # 5. KARTU PENJADWALAN FLEKSIBEL (5 TAB)
        sched_card = tk.LabelFrame(
            self.root,
            text=" ⏰ 3. PENJADWALAN OTOMATIS GATE KERETA ",
            font=("Arial", 8, "bold"),
            fg=FG_TEXT,
            bg=BG_CARD,
            padx=10,
            pady=6,
            relief="solid",
            bd=1
        )
        sched_card.pack(fill="x", padx=10, pady=4)

        top_sched = tk.Frame(sched_card, bg=BG_CARD)
        top_sched.pack(fill="x", pady=(0, 4))

        self.var_sched_enabled = tk.BooleanVar(value=False)
        self.chk_sched = tk.Checkbutton(
            top_sched,
            text="Aktifkan Scheduler Otomatis",
            variable=self.var_sched_enabled,
            font=("Arial", 9, "bold"),
            bg=BG_CARD,
            fg=FG_TEXT,
            activebackground=BG_CARD,
            command=self.on_scheduler_toggle
        )
        self.chk_sched.pack(side="left")

        # Target Scanner
        tk.Label(top_sched, text="Target:", font=("Arial", 8, "bold"), bg=BG_CARD, fg=FG_TEXT).pack(side="left", padx=(10, 2))
        self.combo_sched_target = ttk.Combobox(top_sched, values=["Semua Scanner (ALL)", "Scanner 1 Saja (Gate In)", "Scanner 2 Saja (Gate Out)"], width=22, state="readonly")
        self.combo_sched_target.set("Semua Scanner (ALL)")
        self.combo_sched_target.pack(side="left", padx=(0, 10))
        self.combo_sched_target.bind("<<ComboboxSelected>>", lambda e: self.save_config())

        # Jam & Menit
        t_pick = tk.Frame(top_sched, bg=BG_CARD)
        t_pick.pack(side="right")
        tk.Label(t_pick, text="Jam:", font=("Arial", 8, "bold"), bg=BG_CARD, fg=FG_TEXT).pack(side="left")

        self.combo_hour = ttk.Combobox(t_pick, values=[f"{i:02d}" for i in range(24)], width=3, state="readonly")
        self.combo_hour.set("02")
        self.combo_hour.pack(side="left", padx=(2, 2))
        tk.Label(t_pick, text=":", font=("Arial", 9, "bold"), bg=BG_CARD, fg=FG_TEXT).pack(side="left")

        self.combo_min = ttk.Combobox(t_pick, values=[f"{i:02d}" for i in range(60)], width=3, state="readonly")
        self.combo_min.set("00")
        self.combo_min.pack(side="left", padx=(2, 2))
        tk.Label(t_pick, text="WIB", font=("Arial", 8), bg=BG_CARD, fg=FG_MUTED).pack(side="left")

        # NOTEBOOK 5 TAB
        self.notebook = ttk.Notebook(sched_card)
        self.notebook.pack(fill="x", pady=2)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.save_config())

        # TAB 1: SETIAP HARI
        self.tab_daily = tk.Frame(self.notebook, bg=BG_PANEL, padx=8, pady=6)
        self.notebook.add(self.tab_daily, text="📅 Setiap Hari")
        tk.Label(self.tab_daily, text="Restart otomatis SETIAP HARI saat jam operasional stasiun tutup (misal: 02:00 WIB).", font=("Arial", 8), bg=BG_PANEL, fg=FG_TEXT).pack(anchor="w")

        # TAB 2: HARI TERTENTU
        self.tab_weekly = tk.Frame(self.notebook, bg=BG_PANEL, padx=8, pady=6)
        self.notebook.add(self.tab_weekly, text="🗓️ Hari Tertentu")
        wf = tk.Frame(self.tab_weekly, bg=BG_PANEL)
        wf.pack(fill="x")
        tk.Label(wf, text="Pilih Hari:", font=("Arial", 8, "bold"), bg=BG_PANEL, fg=FG_TEXT).pack(side="left", padx=(0, 4))
        for day in HARI_INDONESIA:
            var = tk.BooleanVar(value=True)
            self.day_check_vars[day] = var
            chk = tk.Checkbutton(wf, text=day[:3], variable=var, font=("Arial", 8), bg=BG_PANEL, fg=FG_TEXT, activebackground=BG_PANEL, command=self.save_config)
            chk.pack(side="left", padx=2)

        # TAB 3: TANGGAL BULANAN
        self.tab_monthly = tk.Frame(self.notebook, bg=BG_PANEL, padx=8, pady=6)
        self.notebook.add(self.tab_monthly, text="📆 Tanggal Tiap Bulan")
        mf = tk.Frame(self.tab_monthly, bg=BG_PANEL)
        mf.pack(fill="x")
        tk.Label(mf, text="Setiap Tanggal:", font=("Arial", 8, "bold"), bg=BG_PANEL, fg=FG_TEXT).pack(side="left")
        self.spin_month_date = ttk.Spinbox(mf, from_=1, to=31, width=3)
        self.spin_month_date.set(1)
        self.spin_month_date.pack(side="left", padx=4)
        tk.Label(mf, text="tiap bulan sesuai jam yang dipilih.", font=("Arial", 8), bg=BG_PANEL, fg=FG_MUTED).pack(side="left")

        # TAB 4: TANGGAL SPESIFIK
        self.tab_specific = tk.Frame(self.notebook, bg=BG_PANEL, padx=8, pady=6)
        self.notebook.add(self.tab_specific, text="🎯 Tanggal Spesifik")
        sf = tk.Frame(self.tab_specific, bg=BG_PANEL)
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
        tk.Label(sf, text="(Hanya 1x jalan pada tanggal ini)", font=("Arial", 8), bg=BG_PANEL, fg=FG_MUTED).pack(side="left", padx=4)

        # TAB 5: INTERVAL BERKALA
        self.tab_interval = tk.Frame(self.notebook, bg=BG_PANEL, padx=8, pady=6)
        self.notebook.add(self.tab_interval, text="⏱️ Interval Rutin")
        inf = tk.Frame(self.tab_interval, bg=BG_PANEL)
        inf.pack(fill="x")
        tk.Label(inf, text="Restart berkala setiap:", font=("Arial", 8, "bold"), bg=BG_PANEL, fg=FG_TEXT).pack(side="left")
        self.spin_interval = ttk.Spinbox(inf, from_=10, to=2880, width=5)
        self.spin_interval.set(360)
        self.spin_interval.pack(side="left", padx=4)
        tk.Label(inf, text="menit (misal: 360 = 6 jam, 1440 = 24 jam)", font=("Arial", 8), bg=BG_PANEL, fg=FG_MUTED).pack(side="left")

        # Label Hitung Mundur
        self.lbl_sched_status = tk.Label(
            sched_card,
            text="Status Penjadwalan: NONAKTIF",
            font=("Arial", 8, "bold"),
            fg=FG_MUTED,
            bg=BG_CARD
        )
        self.lbl_sched_status.pack(anchor="w", pady=(4, 0))

        # 6. LOG CONSOLE AKTIVITAS GATE
        log_card = tk.LabelFrame(
            self.root,
            text=" 📜 4. LOG AKTIVITAS & MONITORING GATE KERETA ",
            font=("Arial", 8, "bold"),
            fg=FG_TEXT,
            bg=BG_CARD,
            padx=8,
            pady=4,
            relief="solid",
            bd=1
        )
        log_card.pack(fill="both", expand=True, padx=10, pady=(2, 6))

        self.txt_log = tk.Text(log_card, height=5, font=("Courier", 8), bg=BG_DARK, fg="#38bdf8", relief="flat", wrap="word")
        self.txt_log.pack(side="left", fill="both", expand=True)

        scrl = ttk.Scrollbar(log_card, command=self.txt_log.yview)
        scrl.pack(side="right", fill="y")
        self.txt_log.config(yscrollcommand=scrl.set)

    def apply_config_to_ui(self):
        self.baud_combobox.set(str(self.config.get("baud_rate", 9600)))
        self.spin_duration.set(str(self.config.get("restart_duration_sec", 4)))
        self.var_autoconnect.set(bool(self.config.get("auto_connect_usb", True)))
        self.var_sched_enabled.set(bool(self.config.get("scheduler_enabled", False)))

        raw_target = self.config.get("sched_target", "ALL")
        if "1" in raw_target:
            self.combo_sched_target.set("Scanner 1 Saja (Gate In)")
        elif "2" in raw_target:
            self.combo_sched_target.set("Scanner 2 Saja (Gate Out)")
        else:
            self.combo_sched_target.set("Semua Scanner (ALL)")

        active_tab = self.config.get("active_tab", 0)
        try:
            self.notebook.select(int(active_tab))
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

    # ==========================================
    # JAM EPC HOST REAL-TIME
    # ==========================================
    def start_epc_clock_timer(self):
        def _tick():
            now = datetime.datetime.now()
            time_str = now.strftime("%H:%M:%S WIB")
            date_str = f"{HARI_INDONESIA[now.weekday()]}, {now.day} {BULAN_INDONESIA[now.month-1]} {now.year}"
            self.lbl_clock_time.config(text=time_str)
            self.lbl_clock_date.config(text=date_str)
            if self.is_running:
                self.root.after(1000, _tick)
        self.root.after(200, _tick)

    # ==========================================
    # USB PORT SCAN & HOTPLUG MONITOR
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
        self.log(f"Deteksi USB: {len(devices)} port fisik tersedia.")

        if not (self.ser and self.ser.is_open) and self.var_autoconnect.get():
            arduino_ports = [d for d in devices if any(k in d.lower() for k in ["usbmodem", "usbserial", "com"])]
            if arduino_ports:
                target_port = arduino_ports[0]
                self.log(f"🔌 Port Arduino baru terdeteksi: {target_port}. Menghubungkan...")
                for val in self.port_combobox["values"]:
                    if target_port in val:
                        self.port_combobox.set(val)
                        break
                self.connect(silent=True)

    def on_cable_disconnected(self):
        self.log("⚠️ Kabel USB Arduino terputus dari EPC!")
        self.disconnect()

    # ==========================================
    # MANAJEMEN KONEKSI SERIAL / SIMULATOR
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
                messagebox.showwarning("Peringatan", "Pilih port fisik USB terlebih dahulu pada combo box!")
            return False

        if port == SIMULATION_PORT:
            self.is_simulation = True
            self.btn_connect.config(text="🔴 PUTUSKAN SIMULATOR", bg=CLR_RED)
            self.lbl_conn_badge.config(text="● TERHUBUNG (SIMULASI)", fg=CLR_BLUE)
            self.port_combobox.config(state="disabled")
            self.log("==================================================")
            self.log("[SIMULATOR] MODE VIRTUAL GATE STASIUN DIAKTIFKAN")
            self.log("[SIMULATOR] Arduino Mega 2560 Virtual siap (WDT 8s Aktif).")
            self.log("[SIMULATOR] Scanner 1 & 2 Normal (Relay NC tertutup, arus mengalir).")
            self.log("==================================================")
            self.save_config()
            return True

        baud = int(self.baud_combobox.get() or 9600)

        try:
            self.log(f"Membuka port fisik {port} (Baud {baud})...")
            self.ser = serial.Serial(port, baud, timeout=1)
            time.sleep(2)

            self.is_simulation = False
            self.btn_connect.config(text=f"🔴 PUTUSKAN ({port})", bg=CLR_RED)
            self.lbl_conn_badge.config(text=f"● TERHUBUNG ({port})", fg=CLR_GREEN)
            self.port_combobox.config(state="disabled")

            self.save_config()
            self.log(f"✅ Berhasil terhubung ke Arduino Mega Gate di {port}.")

            threading.Thread(target=self.serial_reader_worker, daemon=True).start()
            self.send_serial_command("STATUS")
            return True

        except Exception as e:
            err = str(e)
            self.log(f"Koneksi gagal ke {port}: {err}")
            if not silent:
                if "Resource busy" in err:
                    msg = "Port sedang sibuk! Pastikan Serial Monitor di Arduino IDE sudah DITUTUP."
                else:
                    msg = f"Tidak bisa membuka {port}:\n{err}"
                messagebox.showerror("Gagal Membuka Port", msg)
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

        self.btn_connect.config(text="🟢 HUBUNGKAN KE HARDWARE", bg=CLR_GREEN)
        self.lbl_conn_badge.config(text="● TERPUTUS", fg=CLR_RED)
        self.port_combobox.config(state="readonly")
        self.log("Koneksi USB / Simulator ditutup.")

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
        # Format: STATUS:CH1=ON:CH2=OFF
        if line.startswith("STATUS:CH1="):
            parts = line.split(":")
            for p in parts[1:]:
                if "=" in p:
                    k, v = p.split("=")
                    ch_num = int(k.replace("CH", ""))
                    self.update_channel_badge(ch_num, v)

        elif "RESTARTING:CH=" in line:
            # STATUS:RESTARTING:CH=1:DURATION=4000
            for part in line.split(":"):
                if part.startswith("CH="):
                    ch = int(part.replace("CH=", ""))
                    self.update_channel_badge(ch, "RESTARTING")

        elif "STATUS:STAGGERED:CH1_CUT" in line:
            self.update_channel_badge(1, "RESTARTING")
        elif "STATUS:STAGGERED:CH2_CUT" in line:
            self.update_channel_badge(2, "RESTARTING")

        elif "STATUS:RESTART_COMPLETE:CH" in line:
            ch_str = line.split("CH")[-1]
            ch = int(ch_str)
            self.update_channel_badge(ch, "ON")

        elif "STATUS:STAGGERED_COMPLETE:ALL_ON" in line:
            self.update_channel_badge(1, "ON")
            self.update_channel_badge(2, "ON")

    def update_channel_badge(self, channel, state):
        self.relay_states[channel] = state
        badge = self.lbl_ch1_badge if channel == 1 else self.lbl_ch2_badge

        if state == "ON":
            badge.config(text="🟢 DAYA ON (NC)", fg=CLR_GREEN)
        elif state == "RESTARTING":
            badge.config(text="🟡 RESTART (CUT)", fg=CLR_AMBER)
        elif state == "OFF":
            badge.config(text="🔴 MATI TOTAL (OFF)", fg=CLR_RED)

    def send_serial_command(self, cmd):
        if self.is_simulation:
            self.log(f"[SIMULATOR Kirim] -> {cmd}")
            self.simulate_hardware_reaction(cmd)
            return True

        if not (self.ser and self.ser.is_open):
            self.log(f"Perintah gagal: Port fisik belum terhubung.")
            return False

        try:
            self.ser.write((cmd + "\n").encode('utf-8'))
            self.ser.flush()
            self.log(f"[Kirim] -> {cmd}")
            return True
        except Exception as e:
            self.log(f"Error kirim: {e}")
            return False

    def simulate_hardware_reaction(self, cmd):
        dur = int(self.spin_duration.get() or 4)

        if cmd.startswith("RESTART:ALL"):
            self.log("[SIMULATOR] Staggered Restart dimulai...")
            self.update_channel_badge(1, "RESTARTING")
            self.log("[SIMULATOR] Scanner 1 (Gate In) Arus Terputus (Relay 1 ON).")

            def _step2():
                self.update_channel_badge(2, "RESTARTING")
                self.log("[SIMULATOR] Jeda 1.5s -> Scanner 2 (Gate Out) Arus Terputus (Relay 2 ON).")

            def _finish():
                self.update_channel_badge(1, "ON")
                self.update_channel_badge(2, "ON")
                self.log("[SIMULATOR] STATUS:STAGGERED_COMPLETE:ALL_ON (Kedua Scanner Menyala Normal).")

            threading.Timer(1.5, _step2).start()
            threading.Timer(dur + 2.0, _finish).start()

        elif cmd.startswith("RESTART:1"):
            self.update_channel_badge(1, "RESTARTING")
            self.log(f"[SIMULATOR] Scanner 1 diputus selama {dur} detik...")
            threading.Timer(dur, lambda: (
                self.update_channel_badge(1, "ON"),
                self.log("[SIMULATOR] STATUS:RESTART_COMPLETE:CH1 (Scanner 1 Menyala Normal)")
            )).start()

        elif cmd.startswith("RESTART:2"):
            self.update_channel_badge(2, "RESTARTING")
            self.log(f"[SIMULATOR] Scanner 2 diputus selama {dur} detik...")
            threading.Timer(dur, lambda: (
                self.update_channel_badge(2, "ON"),
                self.log("[SIMULATOR] STATUS:RESTART_COMPLETE:CH2 (Scanner 2 Menyala Normal)")
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
    # KONTROL AKSI
    # ==========================================
    def check_ready(self):
        if self.is_simulation or (self.ser and self.ser.is_open):
            return True
        self.log("Mencoba auto-connect ke USB sebelum eksekusi...")
        if self.connect(silent=True):
            return True
        messagebox.showinfo("Belum Terhubung", "Silakan klik tombol '🟢 HUBUNGKAN KE HARDWARE' di atas atau colokkan kabel USB Arduino.")
        return False

    def manual_restart_clicked(self, channel=1):
        if not self.check_ready():
            return

        ch_name = "Scanner 1 (Gate In)" if channel == 1 else ("Scanner 2 (Gate Out)" if channel == 2 else "SEMUA Scanner (Gate In & Out)")
        if messagebox.askyesno("Konfirmasi Restart", f"Restart {ch_name} sekarang?\nArus adaptor akan diputus sesaat lalu normal kembali."):
            self.trigger_restart(channel=channel, source="MANUAL")

    def on_power_click(self, cmd):
        if not self.check_ready():
            return
        self.send_serial_command(cmd)

    def trigger_restart(self, channel="ALL", source="MANUAL"):
        dur_sec = int(self.spin_duration.get() or 4)
        dur_ms = dur_sec * 1000

        def _exec():
            # Disable buttons saat eksekusi
            self.btn_restart_ch1.config(state="disabled")
            self.btn_restart_ch2.config(state="disabled")
            self.btn_restart_all.config(state="disabled")

            total = int(self.lbl_counter_badge.cget("text").replace("x", "") or 0) + 1
            self.lbl_counter_badge.config(text=f"{total}x")

            if channel == "ALL":
                self.log(f"[{source}] Pemicu RESTART SEMUA SCANNER (Staggered). Durasi: {dur_sec}s...")
                self.send_serial_command(f"RESTART:ALL:{dur_ms}")
                time.sleep(dur_sec + 3.0)
            else:
                self.log(f"[{source}] Pemicu RESTART SCANNER {channel}. Durasi: {dur_sec}s...")
                self.send_serial_command(f"RESTART:{channel}:{dur_ms}")
                time.sleep(dur_sec + 1.0)

            if self.is_simulation or (self.ser and self.ser.is_open):
                self.btn_restart_ch1.config(state="normal")
                self.btn_restart_ch2.config(state="normal")
                self.btn_restart_all.config(state="normal")

        threading.Thread(target=_exec, daemon=True).start()

    # ==========================================
    # ENGINE PENJADWALAN FLEKSIBEL
    # ==========================================
    def on_scheduler_toggle(self):
        self.save_config()
        if self.var_sched_enabled.get():
            tab_idx = self.notebook.index(self.notebook.select())
            tab_name = self.notebook.tab(tab_idx, "text")
            target_str = self.combo_sched_target.get()
            if tab_idx == 4:
                self.last_interval_trigger = time.time()
            self.log(f"Penjadwalan otomatis DIAKTIFKAN: {tab_name} -> Target: {target_str}")
        else:
            self.log("Penjadwalan otomatis DINONAKTIFKAN.")
            self.lbl_sched_status.config(text="Status Penjadwalan: NONAKTIF", fg=FG_MUTED)

    def get_target_channel_param(self):
        raw = self.combo_sched_target.get()
        if "1" in raw:
            return 1
        elif "2" in raw:
            return 2
        return "ALL"

    def get_target_hour_min(self):
        try:
            h = int(self.combo_hour.get() or 2)
            m = int(self.combo_min.get() or 0)
            return h, m
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

                        # TAB 0: SETIAP HARI
                        if tab_idx == 0:
                            th, tm = self.get_target_hour_min()
                            if now.hour == th and now.minute == tm and now.minute != last_fired_minute:
                                last_fired_minute = now.minute
                                self.log(f"[JADWAL GATE] Jam {th:02d}:{tm:02d} WIB tercapai! Eksekusi restart target: {target_ch}")
                                self.trigger_restart(channel=target_ch, source="AUTO-DAILY")

                            target_dt = now.replace(hour=th, minute=tm, second=0, microsecond=0)
                            if target_dt <= now:
                                target_dt += datetime.timedelta(days=1)
                            diff = target_dt - now
                            h, rem = divmod(int(diff.total_seconds()), 3600)
                            m, s = divmod(rem, 60)
                            self.root.after(0, lambda: self.lbl_sched_status.config(
                                text=f"Jadwal Harian ({th:02d}:{tm:02d} WIB): Eksekusi berikutnya dlm ~{h}j {m}m {s}d (Target: {target_ch})",
                                fg=CLR_BLUE
                            ))

                        # TAB 1: HARI TERTENTU
                        elif tab_idx == 1:
                            th, tm = self.get_target_hour_min()
                            active_days = [d for d, v in self.day_check_vars.items() if v.get()]
                            curr_day_name = HARI_INDONESIA[now.weekday()]

                            if curr_day_name in active_days and now.hour == th and now.minute == tm and now.minute != last_fired_minute:
                                last_fired_minute = now.minute
                                self.log(f"[JADWAL GATE] Hari {curr_day_name} jam {th:02d}:{tm:02d} WIB tercapai! Eksekusi target: {target_ch}")
                                self.trigger_restart(channel=target_ch, source="AUTO-WEEKLY")

                            found_dt = None
                            for add_days in range(8):
                                candidate = (now + datetime.timedelta(days=add_days)).replace(hour=th, minute=tm, second=0, microsecond=0)
                                if candidate > now and HARI_INDONESIA[candidate.weekday()] in active_days:
                                    found_dt = candidate
                                    break

                            if found_dt:
                                diff = found_dt - now
                                d = diff.days
                                h, rem = divmod(diff.seconds, 3600)
                                m, s = divmod(rem, 60)
                                self.root.after(0, lambda: self.lbl_sched_status.config(
                                    text=f"Jadwal Mingguan: {HARI_INDONESIA[found_dt.weekday()]} {th:02d}:{tm:02d} (dlm {d}hr {h}j {m}m {s}d)",
                                    fg=CLR_BLUE
                                ))

                        # TAB 2: TANGGAL BULANAN
                        elif tab_idx == 2:
                            th, tm = self.get_target_hour_min()
                            target_day = int(self.spin_month_date.get() or 1)

                            if now.day == target_day and now.hour == th and now.minute == tm and now.minute != last_fired_minute:
                                last_fired_minute = now.minute
                                self.log(f"[JADWAL GATE] Tanggal {target_day} jam {th:02d}:{tm:02d} WIB tercapai! Eksekusi target: {target_ch}")
                                self.trigger_restart(channel=target_ch, source="AUTO-MONTHLY")

                            next_m = now.month + 1 if now.month < 12 else 1
                            next_y = now.year if now.month < 12 else now.year + 1
                            candidate = datetime.datetime(next_y, next_m, min(target_day, 28), th, tm, 0)
                            diff = candidate - now
                            self.root.after(0, lambda: self.lbl_sched_status.config(
                                text=f"Jadwal Bulanan: Tgl {target_day} jam {th:02d}:{tm:02d} (dlm {diff.days} hari)",
                                fg=CLR_BLUE
                            ))

                        # TAB 3: TANGGAL SPESIFIK
                        elif tab_idx == 3:
                            th, tm = self.get_target_hour_min()
                            s_year = int(self.spin_spec_year.get() or 2026)
                            s_month = self.combo_spec_month.current() + 1
                            s_day = int(self.spin_spec_day.get() or 1)
                            target_dt = datetime.datetime(s_year, s_month, s_day, th, tm, 0)

                            if now >= target_dt and now.minute == tm and now.minute != last_fired_minute:
                                last_fired_minute = now.minute
                                self.var_sched_enabled.set(False)
                                self.log(f"[JADWAL GATE] Tanggal {s_day}/{s_month}/{s_year} tercapai! Eksekusi target: {target_ch}")
                                self.trigger_restart(channel=target_ch, source="AUTO-SPECIFIC")

                        # TAB 4: INTERVAL BERKALA
                        elif tab_idx == 4:
                            intv_min = int(self.spin_interval.get() or 360)
                            intv_sec = intv_min * 60
                            elapsed = time.time() - self.last_interval_trigger

                            if elapsed >= intv_sec:
                                self.last_interval_trigger = time.time()
                                self.log(f"[JADWAL GATE] Interval {intv_min} menit tercapai! Eksekusi target: {target_ch}")
                                self.trigger_restart(channel=target_ch, source="AUTO-INTERVAL")

                            rem = max(0, int(intv_sec - elapsed))
                            m, s = divmod(rem, 60)
                            h, m = divmod(m, 60)
                            self.root.after(0, lambda: self.lbl_sched_status.config(
                                text=f"Jadwal Interval ({intv_min} mnt): Eksekusi dlm {h:02d}:{m:02d}:{s:02d} (Target: {target_ch})",
                                fg=CLR_BLUE
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
    app = ModernStationGateRestarterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
