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
    "active_tab": 0,               # 0: Daily, 1: Weekly, 2: Monthly, 3: Specific Date, 4: Interval
    "sched_hour": "02",
    "sched_minute": "00",
    "sched_days": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"],
    "sched_month_date": 1,
    "sched_specific_year": 2026,
    "sched_specific_month": 11,
    "sched_specific_day": 20,
    "sched_interval_minutes": 360
}

SIMULATION_PORT = "[Simulasi / Demo Mode (Tanpa Hardware)]"

class NativeModernScannerRestarterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EPC Device Hardware Restarter & Advanced Scheduler")
        self.root.geometry("720x720")
        self.root.minsize(680, 620)
        self.root.configure(bg="#f1f5f9") # Modern Clean Slate Background
        self.root.lift()
        try:
            self.root.attributes('-topmost', True)
            self.root.after_idle(self.root.attributes, '-topmost', False)
        except Exception:
            pass

        self.ser = None
        self.is_simulation = False
        self.is_running = True
        self.config = self.load_config()

        # State Variables
        self.restart_count = 0
        self.relay_state = "ON"
        self.last_interval_trigger = time.time()
        self.day_check_vars = {}

        self.setup_ui()
        self.apply_config_to_ui()
        self.refresh_ports(auto_select=True)

        # Background Engines
        self.start_epc_clock_timer()
        self.start_usb_hotplug_monitor()
        self.start_scheduler_engine()

    # ==========================================
    # CONFIGURATION
    # ==========================================
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
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
            self.config["active_tab"] = self.notebook.index(self.notebook.select())
            self.config["sched_hour"] = self.combo_hour.get()
            self.config["sched_minute"] = self.combo_min.get()
            self.config["sched_days"] = [d for d, v in self.day_check_vars.items() if v.get()]
            self.config["sched_month_date"] = int(self.spin_month_date.get() or 1)
            self.config["sched_specific_year"] = int(self.spin_spec_year.get() or 2026)
            self.config["sched_specific_month"] = self.combo_spec_month.current() + 1
            self.config["sched_specific_day"] = int(self.spin_spec_day.get() or 1)
            self.config["sched_interval_minutes"] = int(self.spin_interval.get() or 60)

            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    # ==========================================
    # UI SETUP (CRISP & CLEAN HIGH-VISIBILITY)
    # ==========================================
    def setup_ui(self):
        # 1. HEADER & JAM REAL-TIME EPC HOST
        header = tk.Frame(self.root, bg="#1e293b", relief="flat")
        header.pack(fill="x", padx=12, pady=(10, 6))

        tbox = tk.Frame(header, bg="#1e293b")
        tbox.pack(side="left", padx=14, pady=8)
        lbl_app = tk.Label(tbox, text="⚡ EPC HARDWARE RESTARTER & SCHEDULER", font=("Arial", 13, "bold"), fg="#ffffff", bg="#1e293b")
        lbl_app.pack(anchor="w")
        lbl_sub = tk.Label(tbox, text="Pengendali Daya Scanner / VoIP via Relay Arduino Mega 2560", font=("Arial", 9), fg="#94a3b8", bg="#1e293b")
        lbl_sub.pack(anchor="w")

        # Digital Clock Box
        cbox = tk.Frame(header, bg="#0f172a", padx=12, pady=6, relief="ridge", bd=1)
        cbox.pack(side="right", padx=14, pady=8)
        self.lbl_clock_time = tk.Label(cbox, text="--:--:--", font=("Courier", 13, "bold"), fg="#38bdf8", bg="#0f172a")
        self.lbl_clock_time.pack(anchor="e")
        self.lbl_clock_date = tk.Label(cbox, text="Waktu Sistem EPC", font=("Arial", 8), fg="#94a3b8", bg="#0f172a")
        self.lbl_clock_date.pack(anchor="e")

        # 2. STATUS BADGES
        sbar = tk.Frame(self.root, bg="#ffffff", relief="groove", bd=1)
        sbar.pack(fill="x", padx=12, pady=4)

        b1 = tk.Frame(sbar, bg="#ffffff", padx=12, pady=6)
        b1.pack(side="left", expand=True, fill="both")
        tk.Label(b1, text="STATUS KONEKSI USB", font=("Arial", 8, "bold"), fg="#64748b", bg="#ffffff").pack(anchor="w")
        self.lbl_conn_badge = tk.Label(b1, text="● TERPUTUS", font=("Arial", 10, "bold"), fg="#ef4444", bg="#ffffff")
        self.lbl_conn_badge.pack(anchor="w")

        b2 = tk.Frame(sbar, bg="#ffffff", padx=12, pady=6)
        b2.pack(side="left", expand=True, fill="both")
        tk.Label(b2, text="STATUS ARUS RELAY", font=("Arial", 8, "bold"), fg="#64748b", bg="#ffffff").pack(anchor="w")
        self.lbl_relay_badge = tk.Label(b2, text="🟢 DAYA MENGALIR (NORMAL)", font=("Arial", 10, "bold"), fg="#16a34a", bg="#ffffff")
        self.lbl_relay_badge.pack(anchor="w")

        b3 = tk.Frame(sbar, bg="#ffffff", padx=12, pady=6)
        b3.pack(side="left", expand=True, fill="both")
        tk.Label(b3, text="TOTAL RESTART", font=("Arial", 8, "bold"), fg="#64748b", bg="#ffffff").pack(anchor="w")
        self.lbl_counter_badge = tk.Label(b3, text="0 Kali", font=("Arial", 10, "bold"), fg="#0f172a", bg="#ffffff")
        self.lbl_counter_badge.pack(anchor="w")

        # 3. KARTU COMBO BOX PORT USB
        usb_card = tk.LabelFrame(
            self.root,
            text=" 🔌 1. PILIH PORT KOMUNIKASI SERIAL / USB (COMBO BOX) ",
            font=("Arial", 9, "bold"),
            fg="#0f172a",
            bg="#ffffff",
            padx=12,
            pady=8
        )
        usb_card.pack(fill="x", padx=12, pady=5)

        row_port = tk.Frame(usb_card, bg="#ffffff")
        row_port.pack(fill="x", pady=2)

        tk.Label(row_port, text="Pilih Port USB:", font=("Arial", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(side="left")

        # COMBO BOX UTAMA PORT
        self.port_combobox = ttk.Combobox(row_port, width=38, font=("Arial", 10), state="readonly")
        self.port_combobox.pack(side="left", padx=8)

        btn_rescan = tk.Button(
            row_port,
            text="🔄 Refresh Port",
            font=("Arial", 9, "bold"),
            bg="#e2e8f0",
            fg="#0f172a",
            relief="groove",
            command=lambda: self.refresh_ports(auto_select=False)
        )
        btn_rescan.pack(side="left", padx=2)

        self.var_autoconnect = tk.BooleanVar(value=True)
        chk_auto = tk.Checkbutton(
            row_port,
            text="Auto-Connect saat USB dicolok",
            variable=self.var_autoconnect,
            font=("Arial", 9),
            bg="#ffffff",
            fg="#475569",
            activebackground="#ffffff",
            command=self.save_config
        )
        chk_auto.pack(side="right", padx=4)

        # Baris Tombol Hubungkan
        row_conn = tk.Frame(usb_card, bg="#ffffff")
        row_conn.pack(fill="x", pady=(6, 2))

        tk.Label(row_conn, text="Baud Rate: 9600 (Mega 2560)", font=("Arial", 8), bg="#ffffff", fg="#64748b").pack(side="left")
        self.baud_combobox = ttk.Combobox(row_conn, values=["9600", "19200", "57600", "115200"], width=6, state="readonly")
        self.baud_combobox.set("9600")

        self.btn_connect = tk.Button(
            row_conn,
            text="🟢 HUBUNGKAN PORT FISIK TERPILIH",
            font=("Arial", 10, "bold"),
            bg="#16a34a",
            fg="#ffffff",
            cursor="hand2",
            relief="raised",
            height=1,
            command=self.toggle_connection
        )
        self.btn_connect.pack(side="right", fill="x", expand=True, padx=(15, 0))

        # 4. KARTU KONTROL RESTART MANUAL
        ctrl_card = tk.LabelFrame(
            self.root,
            text=" ⚡ 2. KONTROL RESTART MANUAL ",
            font=("Arial", 9, "bold"),
            fg="#0f172a",
            bg="#ffffff",
            padx=12,
            pady=6
        )
        ctrl_card.pack(fill="x", padx=12, pady=4)

        dur_frame = tk.Frame(ctrl_card, bg="#ffffff")
        dur_frame.pack(fill="x", pady=(0, 4))
        tk.Label(dur_frame, text="Durasi Jeda Arus Terputus:", font=("Arial", 9), bg="#ffffff", fg="#0f172a").pack(side="left")
        self.spin_duration = ttk.Spinbox(dur_frame, from_=1, to=20, width=5)
        self.spin_duration.set(4)
        self.spin_duration.pack(side="left", padx=8)
        tk.Label(dur_frame, text="detik  (Rekomendasi: Scanner 3–4 dtk, VoIP Phone 4–6 dtk)", font=("Arial", 8), bg="#ffffff", fg="#64748b").pack(side="left")

        self.btn_restart = tk.Button(
            ctrl_card,
            text="⚡ RESTART PERANGKAT SEKARANG",
            font=("Arial", 12, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            height=2,
            cursor="hand2",
            relief="raised",
            command=self.manual_restart_clicked
        )
        self.btn_restart.pack(fill="x", pady=2)

        row_p = tk.Frame(ctrl_card, bg="#ffffff")
        row_p.pack(fill="x", pady=(2, 0))
        self.btn_power_off = tk.Button(row_p, text="🔴 Matikan Arus (Power OFF)", font=("Arial", 9, "bold"), bg="#ef4444", fg="#ffffff", cursor="hand2", command=lambda: self.on_power_click("POWER:OFF"))
        self.btn_power_off.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.btn_power_on = tk.Button(row_p, text="🟢 Alirkan Arus (Power ON)", font=("Arial", 9, "bold"), bg="#16a34a", fg="#ffffff", cursor="hand2", command=lambda: self.on_power_click("POWER:ON"))
        self.btn_power_on.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # 5. KARTU PENJADWALAN FLEKSIBEL DENGAN 5 TAB (FITUR 2)
        sched_card = tk.LabelFrame(
            self.root,
            text=" ⏰ 3. PENJADWALAN FLEKSIBEL (PILIH SETIAP KAPAN / TANGGAL / HARI / JAM EPC) ",
            font=("Arial", 9, "bold"),
            fg="#0f172a",
            bg="#ffffff",
            padx=12,
            pady=8
        )
        sched_card.pack(fill="x", padx=12, pady=5)

        top_sched = tk.Frame(sched_card, bg="#ffffff")
        top_sched.pack(fill="x", pady=(0, 6))

        self.var_sched_enabled = tk.BooleanVar(value=False)
        self.chk_sched = tk.Checkbutton(
            top_sched,
            text="Aktifkan Penjadwalan Otomatis",
            variable=self.var_sched_enabled,
            font=("Arial", 10, "bold"),
            bg="#ffffff",
            fg="#0f172a",
            activebackground="#ffffff",
            command=self.on_scheduler_toggle
        )
        self.chk_sched.pack(side="left")

        # Jam & Menit Eksekusi (Membaca Jam EPC Host)
        t_pick = tk.Frame(top_sched, bg="#ffffff")
        t_pick.pack(side="right")
        tk.Label(t_pick, text="Waktu Eksekusi:", font=("Arial", 9, "bold"), bg="#ffffff", fg="#0f172a").pack(side="left")

        self.combo_hour = ttk.Combobox(t_pick, values=[f"{i:02d}" for i in range(24)], width=3, state="readonly", font=("Arial", 9))
        self.combo_hour.set("02")
        self.combo_hour.pack(side="left", padx=(4, 2))
        tk.Label(t_pick, text=":", font=("Arial", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(side="left")

        self.combo_min = ttk.Combobox(t_pick, values=[f"{i:02d}" for i in range(60)], width=3, state="readonly", font=("Arial", 9))
        self.combo_min.set("00")
        self.combo_min.pack(side="left", padx=(2, 4))
        tk.Label(t_pick, text="WIB", font=("Arial", 9), bg="#ffffff", fg="#64748b").pack(side="left")

        # TABBED NOTEBOOK UNTUK SETIAP KAPAN / TANGGAL KAPAN
        self.notebook = ttk.Notebook(sched_card)
        self.notebook.pack(fill="x", pady=4)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.save_config())

        # TAB 1: SETIAP HARI
        self.tab_daily = tk.Frame(self.notebook, bg="#f8fafc", padx=12, pady=10)
        self.notebook.add(self.tab_daily, text="📅 Setiap Hari (Daily)")
        tk.Label(
            self.tab_daily,
            text="Perangkat akan di-restart otomatis SETIAP HARI pada jam & menit yang ditentukan di atas.",
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#334155"
        ).pack(anchor="w")

        # TAB 2: HARI TERTENTU (SENIN - MINGGU)
        self.tab_weekly = tk.Frame(self.notebook, bg="#f8fafc", padx=12, pady=10)
        self.notebook.add(self.tab_weekly, text="🗓️ Hari Tertentu (Senin-Minggu)")

        wf = tk.Frame(self.tab_weekly, bg="#f8fafc")
        wf.pack(fill="x")
        tk.Label(wf, text="Pilih Hari:", font=("Arial", 9, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="left", padx=(0, 6))

        for day in HARI_INDONESIA:
            var = tk.BooleanVar(value=(day in ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"]))
            self.day_check_vars[day] = var
            chk = tk.Checkbutton(
                wf,
                text=day[:3], # Sen, Sel, Rab, Kam, Jum, Sab, Min
                variable=var,
                font=("Arial", 9, "bold"),
                bg="#f8fafc",
                fg="#0f172a",
                activebackground="#f8fafc",
                command=self.save_config
            )
            chk.pack(side="left", padx=3)

        btn_all = tk.Button(wf, text="Pilih Semua", font=("Arial", 8), bg="#e2e8f0", fg="#0f172a", command=lambda: self.set_all_days(True))
        btn_all.pack(side="left", padx=(8, 2))
        btn_work = tk.Button(wf, text="Sen-Jum Saja", font=("Arial", 8), bg="#e2e8f0", fg="#0f172a", command=self.set_work_days)
        btn_work.pack(side="left", padx=2)

        # TAB 3: TANGGAL TIAP BULAN
        self.tab_monthly = tk.Frame(self.notebook, bg="#f8fafc", padx=12, pady=10)
        self.notebook.add(self.tab_monthly, text="📆 Tanggal Tiap Bulan")

        mf = tk.Frame(self.tab_monthly, bg="#f8fafc")
        mf.pack(fill="x")
        tk.Label(mf, text="Restart otomatis setiap Tanggal:", font=("Arial", 9, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="left", padx=(0, 6))
        self.spin_month_date = ttk.Spinbox(mf, from_=1, to=31, width=4, font=("Arial", 9))
        self.spin_month_date.set(1)
        self.spin_month_date.pack(side="left", padx=4)
        tk.Label(mf, text="pada setiap bulan (Sesuai Jam Eksekusi)", font=("Arial", 9), bg="#f8fafc", fg="#475569").pack(side="left")

        # TAB 4: TANGGAL SPESIFIK 1X JALAN
        self.tab_specific = tk.Frame(self.notebook, bg="#f8fafc", padx=12, pady=10)
        self.notebook.add(self.tab_specific, text="🎯 Tanggal Kalender Spesifik")

        sf = tk.Frame(self.tab_specific, bg="#f8fafc")
        sf.pack(fill="x")
        tk.Label(sf, text="Pilih Tanggal:", font=("Arial", 9, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="left", padx=(0, 6))

        self.spin_spec_day = ttk.Spinbox(sf, from_=1, to=31, width=4, font=("Arial", 9))
        self.spin_spec_day.set(datetime.datetime.now().day)
        self.spin_spec_day.pack(side="left", padx=2)

        self.combo_spec_month = ttk.Combobox(sf, values=BULAN_INDONESIA, width=11, state="readonly", font=("Arial", 9))
        self.combo_spec_month.current(datetime.datetime.now().month - 1)
        self.combo_spec_month.pack(side="left", padx=4)

        self.spin_spec_year = ttk.Spinbox(sf, from_=2025, to=2035, width=6, font=("Arial", 9))
        self.spin_spec_year.set(datetime.datetime.now().year)
        self.spin_spec_year.pack(side="left", padx=2)

        tk.Label(sf, text="(Hanya berjalan 1 kali pada tanggal kalender ini)", font=("Arial", 8), bg="#f8fafc", fg="#64748b").pack(side="left", padx=6)

        # TAB 5: INTERVAL BERKALA
        self.tab_interval = tk.Frame(self.notebook, bg="#f8fafc", padx=12, pady=10)
        self.notebook.add(self.tab_interval, text="⏱️ Interval Rutin")

        inf = tk.Frame(self.tab_interval, bg="#f8fafc")
        inf.pack(fill="x")
        tk.Label(inf, text="Restart otomatis berulang setiap:", font=("Arial", 9, "bold"), bg="#f8fafc", fg="#0f172a").pack(side="left", padx=(0, 6))
        self.spin_interval = ttk.Spinbox(inf, from_=5, to=2880, width=6, font=("Arial", 9))
        self.spin_interval.set(360)
        self.spin_interval.pack(side="left", padx=4)
        tk.Label(inf, text="menit  (Contoh: 120 = 2 jam, 360 = 6 jam, 1440 = 24 jam)", font=("Arial", 9), bg="#f8fafc", fg="#475569").pack(side="left")

        # Label Hitung Mundur Real-Time
        self.lbl_sched_status = tk.Label(
            sched_card,
            text="Status Penjadwalan: NONAKTIF (Centang tombol di atas untuk mengaktifkan)",
            font=("Arial", 9, "bold"),
            fg="#64748b",
            bg="#ffffff"
        )
        self.lbl_sched_status.pack(anchor="w", pady=(8, 0))

        # 6. LOG CONSOLE & RIWAYAT
        log_card = tk.LabelFrame(
            self.root,
            text=" 📜 LOG RIWAYAT AKTIVITAS & PERANGKAT ",
            font=("Arial", 9, "bold"),
            fg="#0f172a",
            bg="#ffffff",
            padx=10,
            pady=4
        )
        log_card.pack(fill="both", expand=True, padx=12, pady=(4, 8))

        self.txt_log = tk.Text(log_card, height=5, font=("Courier", 9), bg="#0f172a", fg="#38bdf8", relief="flat", wrap="word")
        self.txt_log.pack(side="left", fill="both", expand=True)

        scrl = ttk.Scrollbar(log_card, command=self.txt_log.yview)
        scrl.pack(side="right", fill="y")
        self.txt_log.config(yscrollcommand=scrl.set)

    def set_all_days(self, state):
        for v in self.day_check_vars.values():
            v.set(state)
        self.save_config()

    def set_work_days(self):
        for d, v in self.day_check_vars.items():
            v.set(d in ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"])
        self.save_config()

    def apply_config_to_ui(self):
        self.baud_combobox.set(str(self.config.get("baud_rate", 9600)))
        self.spin_duration.set(str(self.config.get("restart_duration_sec", 4)))
        self.var_autoconnect.set(bool(self.config.get("auto_connect_usb", True)))
        self.var_sched_enabled.set(bool(self.config.get("scheduler_enabled", False)))

        active_tab = self.config.get("active_tab", 0)
        try:
            self.notebook.select(int(active_tab))
        except Exception:
            pass

        self.combo_hour.set(str(self.config.get("sched_hour", "02")).zfill(2))
        self.combo_min.set(str(self.config.get("sched_minute", "00")).zfill(2))

        saved_days = self.config.get("sched_days", ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"])
        if isinstance(saved_days, list):
            for d, v in self.day_check_vars.items():
                v.set(d in saved_days)

        self.spin_month_date.set(str(self.config.get("sched_month_date", 1)))
        self.spin_spec_year.set(str(self.config.get("sched_specific_year", 2026)))

        raw_m = self.config.get("sched_specific_month", 11)
        if isinstance(raw_m, str):
            if raw_m in BULAN_INDONESIA:
                m_idx = BULAN_INDONESIA.index(raw_m)
            else:
                try:
                    m_idx = int(raw_m) - 1
                except ValueError:
                    m_idx = 10
        elif isinstance(raw_m, int):
            m_idx = raw_m - 1
        else:
            m_idx = 10

        if 0 <= m_idx < len(BULAN_INDONESIA):
            self.combo_spec_month.current(m_idx)

        self.spin_spec_day.set(str(self.config.get("sched_specific_day", 20)))
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
    # REAL-TIME EPC CLOCK
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
        self.log(f"Perubahan USB terdeteksi: {len(devices)} port fisik tersedia.")

        if not (self.ser and self.ser.is_open) and self.var_autoconnect.get():
            arduino_ports = [d for d in devices if any(k in d.lower() for k in ["usbmodem", "usbserial", "com"])]
            if arduino_ports:
                target_port = arduino_ports[0]
                self.log(f"🔌 Port Arduino baru dicolok: {target_port}. Menghubungkan...")
                for val in self.port_combobox["values"]:
                    if target_port in val:
                        self.port_combobox.set(val)
                        break
                self.connect(silent=True)

    def on_cable_disconnected(self):
        self.log("⚠️ Kabel USB fisik terputus / dicabut!")
        self.disconnect()

    # ==========================================
    # CONNECTION MANAGEMENT
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
            self.btn_connect.config(text="🔴 PUTUSKAN KONEKSI (SIMULASI)", bg="#ef4444")
            self.lbl_conn_badge.config(text="● TERHUBUNG (SIMULASI)", fg="#2563eb")
            self.port_combobox.config(state="disabled")
            self.log("[SIMULASI] Terhubung ke Simulator.")
            self.save_config()
            return True

        baud = int(self.baud_combobox.get() or 9600)

        try:
            self.log(f"Membuka port fisik {port} (Baud {baud})...")
            self.ser = serial.Serial(port, baud, timeout=1)
            time.sleep(2)

            self.is_simulation = False
            self.btn_connect.config(text=f"🔴 PUTUSKAN ({port})", bg="#ef4444")
            self.lbl_conn_badge.config(text=f"● TERHUBUNG ({port})", fg="#16a34a")
            self.port_combobox.config(state="disabled")

            self.save_config()
            self.log(f"✅ Berhasil terhubung ke Arduino Mega di {port}.")

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

        self.btn_connect.config(text="🟢 HUBUNGKAN PORT FISIK TERPILIH", bg="#16a34a")
        self.lbl_conn_badge.config(text="● TERPUTUS", fg="#ef4444")
        self.port_combobox.config(state="readonly")
        self.log("Koneksi ditutup.")

    def serial_reader_worker(self):
        while self.is_running and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self.log(f"[Arduino] {line}")
                        if "RESTARTING" in line:
                            self.update_relay_status("RESTARTING")
                        elif "RESTART_COMPLETE" in line or "POWER_ON" in line or "STATE_ON" in line:
                            self.update_relay_status("ON")
                        elif "POWER_OFF" in line or "STATE_OFF" in line:
                            self.update_relay_status("OFF")
                else:
                    time.sleep(0.05)
            except Exception:
                break

    def update_relay_status(self, state):
        self.relay_state = state
        if state == "ON":
            self.lbl_relay_badge.config(text="🟢 ARUS MENGALIR (NORMAL)", fg="#16a34a")
        elif state == "RESTARTING":
            self.lbl_relay_badge.config(text="🟡 SIKLUS RESTART (ARUS TERPUTUS)", fg="#d97706")
        elif state == "OFF":
            self.lbl_relay_badge.config(text="🔴 DAYA DIMATIKAN TOTAL", fg="#ef4444")

    def send_serial_command(self, cmd):
        if self.is_simulation:
            self.log(f"[SIMULASI] Kirim -> {cmd}")
            if cmd.startswith("RESTART"):
                self.update_relay_status("RESTARTING")
                dur = int(self.spin_duration.get() or 4)
                threading.Timer(dur, lambda: (
                    self.update_relay_status("ON"),
                    self.log("[SIMULASI] STATUS:RESTART_COMPLETE:SCANNER_ON")
                )).start()
            elif cmd == "POWER:OFF":
                self.update_relay_status("OFF")
            elif cmd == "POWER:ON":
                self.update_relay_status("ON")
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

    # ==========================================
    # ACTION CONTROLS
    # ==========================================
    def check_ready(self):
        if self.is_simulation or (self.ser and self.ser.is_open):
            return True
        self.log("Mencoba auto-connect sebelum eksekusi...")
        if self.connect(silent=True):
            return True
        messagebox.showinfo("Belum Terhubung", "Silakan klik tombol '🟢 HUBUNGKAN PORT' di atas atau colokkan kabel USB Arduino.")
        return False

    def manual_restart_clicked(self):
        if not self.check_ready():
            return
        if messagebox.askyesno("Konfirmasi Restart", "Restart perangkat sekarang? (Arus akan diputus beberapa detik lalu menyala kembali)"):
            self.trigger_restart(source="MANUAL")

    def on_power_click(self, cmd):
        if not self.check_ready():
            return
        self.send_serial_command(cmd)

    def trigger_restart(self, source="MANUAL"):
        dur_sec = int(self.spin_duration.get() or 4)
        dur_ms = dur_sec * 1000

        def _exec():
            self.btn_restart.config(state="disabled")
            self.btn_power_off.config(state="disabled")
            self.btn_power_on.config(state="disabled")

            self.restart_count += 1
            self.lbl_counter_badge.config(text=f"{self.restart_count} Kali")

            self.log(f"[{source}] Pemicu restart aktif. Memutus daya selama {dur_sec} detik...")
            self.update_relay_status("RESTARTING")
            success = self.send_serial_command(f"RESTART:{dur_ms}")

            if success:
                time.sleep(dur_sec + 1)
                self.update_relay_status("ON")
                self.log(f"[{source}] Siklus restart sukses. Arus kembali normal.")

            if self.is_simulation or (self.ser and self.ser.is_open):
                self.btn_restart.config(state="normal")
                self.btn_power_off.config(state="normal")
                self.btn_power_on.config(state="normal")

        threading.Thread(target=_exec, daemon=True).start()

    # ==========================================
    # SCHEDULER & ADVANCED EPC TIME ENGINE
    # ==========================================
    def on_scheduler_toggle(self):
        self.save_config()
        if self.var_sched_enabled.get():
            tab_idx = self.notebook.index(self.notebook.select())
            tab_name = self.notebook.tab(tab_idx, "text")
            if tab_idx == 4: # Interval tab
                self.last_interval_trigger = time.time()
            self.log(f"Penjadwalan otomatis DIAKTIFKAN ({tab_name}).")
        else:
            self.log("Penjadwalan otomatis DINONAKTIFKAN.")
            self.lbl_sched_status.config(text="Status Penjadwalan: NONAKTIF (Centang tombol di atas untuk mengaktifkan)", fg="#64748b")

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

                        # TAB 0: SETIAP HARI (DAILY)
                        if tab_idx == 0:
                            th, tm = self.get_target_hour_min()
                            if now.hour == th and now.minute == tm and now.minute != last_fired_minute:
                                last_fired_minute = now.minute
                                self.log(f"[JADWAL EPC] Jam harian {th:02d}:{tm:02d} WIB tercapai! Eksekusi restart...")
                                self.trigger_restart(source="AUTO-DAILY")

                            target_dt = now.replace(hour=th, minute=tm, second=0, microsecond=0)
                            if target_dt <= now:
                                target_dt += datetime.timedelta(days=1)
                            diff = target_dt - now
                            h, rem = divmod(int(diff.total_seconds()), 3600)
                            m, s = divmod(rem, 60)
                            self.root.after(0, lambda: self.lbl_sched_status.config(
                                text=f"Jadwal Harian ({th:02d}:{tm:02d} WIB): Restart berikutnya dlm ~{h} jam {m} mnt {s} dtk",
                                fg="#2563eb"
                            ))

                        # TAB 1: HARI TERTENTU (WEEKLY)
                        elif tab_idx == 1:
                            th, tm = self.get_target_hour_min()
                            active_days = [d for d, v in self.day_check_vars.items() if v.get()]
                            curr_day_name = HARI_INDONESIA[now.weekday()]

                            if curr_day_name in active_days and now.hour == th and now.minute == tm and now.minute != last_fired_minute:
                                last_fired_minute = now.minute
                                self.log(f"[JADWAL EPC] Hari {curr_day_name} jam {th:02d}:{tm:02d} WIB tercapai! Eksekusi restart...")
                                self.trigger_restart(source="AUTO-WEEKLY")

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
                                target_day_str = HARI_INDONESIA[found_dt.weekday()]
                                self.root.after(0, lambda: self.lbl_sched_status.config(
                                    text=f"Jadwal Mingguan: Berikutnya hari {target_day_str} {th:02d}:{tm:02d} (dlm {d}hr {h}j {m}m {s}d)",
                                    fg="#2563eb"
                                ))
                            else:
                                self.root.after(0, lambda: self.lbl_sched_status.config(text="Peringatan: Belum ada hari yang dicentang!", fg="#d97706"))

                        # TAB 2: TANGGAL TERTENTU BULANAN (MONTHLY)
                        elif tab_idx == 2:
                            th, tm = self.get_target_hour_min()
                            target_day = int(self.spin_month_date.get() or 1)

                            if now.day == target_day and now.hour == th and now.minute == tm and now.minute != last_fired_minute:
                                last_fired_minute = now.minute
                                self.log(f"[JADWAL EPC] Tanggal {target_day} jam {th:02d}:{tm:02d} WIB tercapai! Eksekusi restart...")
                                self.trigger_restart(source="AUTO-MONTHLY")

                            try:
                                candidate = now.replace(day=target_day, hour=th, minute=tm, second=0, microsecond=0)
                            except ValueError:
                                candidate = None

                            if not candidate or candidate <= now:
                                next_m = now.month + 1 if now.month < 12 else 1
                                next_y = now.year if now.month < 12 else now.year + 1
                                max_days = calendar.monthrange(next_y, next_m)[1]
                                clamped_day = min(target_day, max_days)
                                candidate = datetime.datetime(next_y, next_m, clamped_day, th, tm, 0)

                            diff = candidate - now
                            d = diff.days
                            h, rem = divmod(diff.seconds, 3600)
                            m, s = divmod(rem, 60)
                            self.root.after(0, lambda: self.lbl_sched_status.config(
                                text=f"Jadwal Bulanan: Setiap Tanggal {target_day} jam {th:02d}:{tm:02d} (dlm {d} hari {h} jam {m} mnt {s} dtk)",
                                fg="#2563eb"
                            ))

                        # TAB 3: TANGGAL KALENDER SPESIFIK 1X JALAN
                        elif tab_idx == 3:
                            th, tm = self.get_target_hour_min()
                            s_year = int(self.spin_spec_year.get() or 2026)
                            s_month = self.combo_spec_month.current() + 1
                            s_day = int(self.spin_spec_day.get() or 1)

                            target_dt = datetime.datetime(s_year, s_month, s_day, th, tm, 0)

                            if now >= target_dt and now.minute == tm and now.minute != last_fired_minute:
                                last_fired_minute = now.minute
                                self.var_sched_enabled.set(False)
                                self.log(f"[JADWAL EPC] Tanggal spesifik {s_day}/{s_month}/{s_year} {th:02d}:{tm:02d} WIB tercapai! Eksekusi restart...")
                                self.trigger_restart(source="AUTO-SPECIFIC")
                                self.root.after(0, lambda: self.lbl_sched_status.config(text="Jadwal spesifik selesai dijalankan (Nonaktif).", fg="#64748b"))

                            elif target_dt > now:
                                diff = target_dt - now
                                d = diff.days
                                h, rem = divmod(diff.seconds, 3600)
                                m, s = divmod(rem, 60)
                                self.root.after(0, lambda: self.lbl_sched_status.config(
                                    text=f"Jadwal Spesifik ({s_day} {BULAN_INDONESIA[s_month-1]} {s_year} {th:02d}:{tm:02d}): dlm {d}hr {h}j {m}m {s}d",
                                    fg="#d97706"
                                ))
                            else:
                                self.root.after(0, lambda: self.lbl_sched_status.config(text="Tanggal spesifik sudah berlalu! Atur tanggal masa depan.", fg="#ef4444"))

                        # TAB 4: INTERVAL RUTIN
                        elif tab_idx == 4:
                            intv_min = int(self.spin_interval.get() or 60)
                            intv_sec = intv_min * 60
                            elapsed = time.time() - self.last_interval_trigger

                            if elapsed >= intv_sec:
                                self.last_interval_trigger = time.time()
                                self.log(f"[JADWAL INTERVAL] Interval {intv_min} menit tercapai! Restarting...")
                                self.trigger_restart(source="AUTO-INTERVAL")

                            rem = max(0, int(intv_sec - elapsed))
                            m, s = divmod(rem, 60)
                            h, m = divmod(m, 60)
                            self.root.after(0, lambda: self.lbl_sched_status.config(
                                text=f"Jadwal Interval ({intv_min} mnt): Hitung mundur {h:02d}:{m:02d}:{s:02d}",
                                fg="#2563eb"
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
    app = NativeModernScannerRestarterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
