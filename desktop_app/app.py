"""
=====================================================================
KCI_restart _qrscan (LEGACY WINFORMS STYLE)
=====================================================================
Target Perangkat : Scanner QR Turnstile Gate Kereta (Gate In & Gate Out)
Target Board     : Arduino Mega 2560 (Relay 2-CH / 4-CH Active-LOW)
Platform Host    : Windows 7, POSReady 7, Windows 10, Windows 11 & macOS
Tampilan         : Classic WinForms Industrial (Sandingan Aplikasi KCI_GATE)
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

SIMULATION_PORT = "[SIMULASI / DEMO VIRTUAL]"

# Palet Warna Classic Windows Forms (KCI Industrial POS)
WIN_BG = "#d4d0c8"        # Classic Windows 7 / WinForms Dialog Gray
WIN_BTN = "#e0dfd8"       # Classic Button Face
WIN_BORDER = "#808080"    # Dark Shadow
BAR_BLACK = "#000000"     # Header Hitam
STATUS_GREEN = "#00e600"  # Hijau Terang KCI (Normal)
STATUS_RED = "#ff3333"    # Merah KCI (Error/Terputus)
STATUS_AMBER = "#ffcc00"  # Kuning KCI (Restarting)
TERM_BG = "#000000"       # Terminal Hitam Pekat
TERM_FG = "#00ff00"       # Terminal Hijau Monospace
FONT_MAIN = ("Tahoma", 8)
FONT_BOLD = ("Tahoma", 8, "bold")
FONT_TITLE = ("Tahoma", 8, "bold")
FONT_TERM = ("Courier", 8)

class KciGateRestarterApp:
    def __init__(self, root):
        self.root = root
        # Judul Window sesuai permintaan: KCI_restart _qrscan
        self.root.title("KCI_restart _qrscan")
        
        # Jendela Ringkas & Kompak (Tidak Fullscreen, agar bisa sandingan dengan KCI_GATE)
        self.root.geometry("560x570+30+30")
        self.root.minsize(540, 540)
        self.root.configure(bg=WIN_BG)

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

        self.start_clock_timer()
        self.start_usb_hotplug_monitor()
        self.start_scheduler_engine()

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
    # DESAIN WINFORMS KOMPAK (GATE RELAY & GATE INFO DIHAPUS)
    # ==========================================
    def setup_ui(self):
        # CONTAINER 2 KOLOM
        main_frame = tk.Frame(self.root, bg=WIN_BG)
        main_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # ----------------------------------------------------
        # KOLOM KIRI (~46% WIDTH): STATUS DEVICE & KONTROL MANUAL
        # ----------------------------------------------------
        col_left = tk.Frame(main_frame, bg=WIN_BG, width=240)
        col_left.pack(side="left", fill="both", padx=(0, 4))
        col_left.pack_propagate(False)

        # GROUPBOX STATUS
        grp_status = tk.LabelFrame(col_left, text="STATUS", font=FONT_BOLD, bg=WIN_BG, fg="#000000", bd=2, relief="groove")
        grp_status.pack(fill="x", pady=(0, 4))

        # 1. SCANNER 1 (GATE IN)
        tk.Label(grp_status, text="SCANNER 1 (GATE IN)", font=FONT_TITLE, bg=BAR_BLACK, fg="#ffffff", anchor="w", padx=3).pack(fill="x", pady=(2, 0))
        self.lbl_stat_sc1 = tk.Label(grp_status, text="Connected [D7 Normal]", font=FONT_BOLD, bg=STATUS_GREEN, fg="#000000", bd=1, relief="solid", anchor="w", padx=3)
        self.lbl_stat_sc1.pack(fill="x", pady=(0, 2))

        # 2. SCANNER 2 (GATE OUT)
        tk.Label(grp_status, text="SCANNER 2 (GATE OUT)", font=FONT_TITLE, bg=BAR_BLACK, fg="#ffffff", anchor="w", padx=3).pack(fill="x", pady=(2, 0))
        self.lbl_stat_sc2 = tk.Label(grp_status, text="Connected [D8 Normal]", font=FONT_BOLD, bg=STATUS_GREEN, fg="#000000", bd=1, relief="solid", anchor="w", padx=3)
        self.lbl_stat_sc2.pack(fill="x", pady=(0, 2))

        # 3. CONTROLLER & WATCHDOG
        tk.Label(grp_status, text="CONTROLLER & WATCHDOG", font=FONT_TITLE, bg=BAR_BLACK, fg="#ffffff", anchor="w", padx=3).pack(fill="x", pady=(2, 0))
        self.lbl_stat_wdt = tk.Label(grp_status, text="Mega 2560 [WDT 8s Active]", font=FONT_BOLD, bg=STATUS_GREEN, fg="#000000", bd=1, relief="solid", anchor="w", padx=3)
        self.lbl_stat_wdt.pack(fill="x", pady=(0, 2))

        # 4. PORT USB COM
        tk.Label(grp_status, text="USB SERIAL PORT", font=FONT_TITLE, bg=BAR_BLACK, fg="#ffffff", anchor="w", padx=3).pack(fill="x", pady=(2, 0))
        self.lbl_stat_port = tk.Label(grp_status, text="Connected [COM3 @ 9600]", font=FONT_BOLD, bg=STATUS_GREEN, fg="#000000", bd=1, relief="solid", anchor="w", padx=3)
        self.lbl_stat_port.pack(fill="x", pady=(0, 2))

        # Pilihan Port USB & Connect
        f_port = tk.Frame(grp_status, bg=WIN_BG, padx=2, pady=2)
        f_port.pack(fill="x")
        self.port_combobox = ttk.Combobox(f_port, width=17, font=FONT_MAIN, state="readonly")
        self.port_combobox.pack(side="left", fill="x", expand=True)

        self.btn_connect = tk.Button(f_port, text="Connect", font=FONT_BOLD, bg=WIN_BTN, relief="raised", bd=2, command=self.toggle_connection)
        self.btn_connect.pack(side="right", padx=(2, 0))

        row_chk = tk.Frame(grp_status, bg=WIN_BG, padx=2)
        row_chk.pack(fill="x")
        self.var_autoconnect = tk.BooleanVar(value=True)
        chk_auto = tk.Checkbutton(row_chk, text="Auto-Connect USB", variable=self.var_autoconnect, font=FONT_MAIN, bg=WIN_BG, activebackground=WIN_BG, command=self.save_config)
        chk_auto.pack(side="left")
        self.baud_combobox = ttk.Combobox(row_chk, values=["9600", "19200", "115200"], width=6, font=FONT_MAIN, state="readonly")
        self.baud_combobox.set("9600")

        # GROUPBOX RESTART CONTROL (WinForms Raised Buttons)
        grp_ctrl = tk.LabelFrame(col_left, text="MANUAL RESTART", font=FONT_BOLD, bg=WIN_BG, fg="#000000", bd=2, relief="groove")
        grp_ctrl.pack(fill="both", expand=True, pady=(2, 0))

        # Durasi
        dur_f = tk.Frame(grp_ctrl, bg=WIN_BG)
        dur_f.pack(fill="x", padx=4, pady=2)
        tk.Label(dur_f, text="Jeda Arus Mati:", font=FONT_MAIN, bg=WIN_BG).pack(side="left")
        self.spin_duration = ttk.Spinbox(dur_f, from_=2, to=15, width=3, font=FONT_MAIN)
        self.spin_duration.set(4)
        self.spin_duration.pack(side="left", padx=4)
        tk.Label(dur_f, text="detik", font=FONT_MAIN, bg=WIN_BG).pack(side="left")

        # Tombol Restart Scanner 1
        self.btn_restart_ch1 = tk.Button(
            grp_ctrl,
            text="Restart Scanner 1 (IN)",
            font=FONT_BOLD,
            bg=WIN_BTN,
            relief="raised",
            bd=2,
            pady=3,
            command=lambda: self.manual_restart(1)
        )
        self.btn_restart_ch1.pack(fill="x", padx=4, pady=2)

        # Tombol Restart Scanner 2
        self.btn_restart_ch2 = tk.Button(
            grp_ctrl,
            text="Restart Scanner 2 (OUT)",
            font=FONT_BOLD,
            bg=WIN_BTN,
            relief="raised",
            bd=2,
            pady=3,
            command=lambda: self.manual_restart(2)
        )
        self.btn_restart_ch2.pack(fill="x", padx=4, pady=2)

        # Tombol Restart Kedua Scanner (Staggered)
        self.btn_restart_all = tk.Button(
            grp_ctrl,
            text="Restart Keduanya (Staggered)",
            font=FONT_BOLD,
            bg=WIN_BTN,
            relief="raised",
            bd=2,
            pady=4,
            command=lambda: self.manual_restart("ALL")
        )
        self.btn_restart_all.pack(fill="x", padx=4, pady=(2, 4))

        # Cut / Normal Daya Darurat
        row_pwr = tk.Frame(grp_ctrl, bg=WIN_BG)
        row_pwr.pack(fill="x", padx=4, pady=2)
        tk.Button(row_pwr, text="Cut 1", font=FONT_MAIN, bg=WIN_BTN, relief="raised", bd=1, command=lambda: self.send_serial_command("POWER:1:OFF")).pack(side="left", fill="x", expand=True, padx=(0, 1))
        tk.Button(row_pwr, text="On 1", font=FONT_MAIN, bg=WIN_BTN, relief="raised", bd=1, command=lambda: self.send_serial_command("POWER:1:ON")).pack(side="left", fill="x", expand=True, padx=(1, 1))
        tk.Button(row_pwr, text="Cut 2", font=FONT_MAIN, bg=WIN_BTN, relief="raised", bd=1, command=lambda: self.send_serial_command("POWER:2:OFF")).pack(side="left", fill="x", expand=True, padx=(1, 1))
        tk.Button(row_pwr, text="On 2", font=FONT_MAIN, bg=WIN_BTN, relief="raised", bd=1, command=lambda: self.send_serial_command("POWER:2:ON")).pack(side="left", fill="x", expand=True, padx=(1, 0))

        # ----------------------------------------------------
        # KOLOM KANAN (~54% WIDTH): SCHEDULER & TERMINAL LOG
        # (GATE INFO SUDAH DIHAPUS SEHINGGA RUANG LOG LEBIH LUAS)
        # ----------------------------------------------------
        col_right = tk.Frame(main_frame, bg=WIN_BG)
        col_right.pack(side="right", fill="both", expand=True)

        # GROUPBOX SCHEDULER AUTO (DITARUH DI PALING ATAS KANAN)
        grp_sched = tk.LabelFrame(col_right, text="SCHEDULER AUTO", font=FONT_BOLD, bg=WIN_BG, fg="#000000", bd=2, relief="groove")
        grp_sched.pack(fill="x", pady=(0, 4))

        s_top = tk.Frame(grp_sched, bg=WIN_BG, padx=4, pady=2)
        s_top.pack(fill="x")
        self.var_sched_enabled = tk.BooleanVar(value=False)
        self.chk_sched = tk.Checkbutton(s_top, text="Enable", variable=self.var_sched_enabled, font=FONT_BOLD, bg=WIN_BG, activebackground=WIN_BG, command=self.on_scheduler_toggle)
        self.chk_sched.pack(side="left")

        self.combo_sched_target = ttk.Combobox(s_top, values=["ALL", "Scanner 1", "Scanner 2"], width=9, font=FONT_MAIN, state="readonly")
        self.combo_sched_target.set("ALL")
        self.combo_sched_target.pack(side="left", padx=4)

        tk.Label(s_top, text="Jam:", font=FONT_MAIN, bg=WIN_BG).pack(side="left")
        self.combo_hour = ttk.Combobox(s_top, values=[f"{i:02d}" for i in range(24)], width=3, font=FONT_MAIN, state="readonly")
        self.combo_hour.set("02")
        self.combo_hour.pack(side="left", padx=1)
        tk.Label(s_top, text=":", font=FONT_BOLD, bg=WIN_BG).pack(side="left")
        self.combo_min = ttk.Combobox(s_top, values=[f"{i:02d}" for i in range(60)], width=3, font=FONT_MAIN, state="readonly")
        self.combo_min.set("00")
        self.combo_min.pack(side="left", padx=1)

        # Tabs WinForms Style
        self.notebook = ttk.Notebook(grp_sched)
        self.notebook.pack(fill="x", padx=4, pady=2)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.save_config())

        # Tab 1: Daily
        self.tab_daily = tk.Frame(self.notebook, bg=WIN_BG, padx=4, pady=4)
        self.notebook.add(self.tab_daily, text="Daily")
        tk.Label(self.tab_daily, text="Restart otomatis tiap hari jam 02:00 WIB (Stasiun Tutup).", font=FONT_MAIN, bg=WIN_BG).pack(anchor="w")

        # Tab 2: Weekly
        self.tab_weekly = tk.Frame(self.notebook, bg=WIN_BG, padx=4, pady=4)
        self.notebook.add(self.tab_weekly, text="Weekly")
        wf = tk.Frame(self.tab_weekly, bg=WIN_BG)
        wf.pack(fill="x")
        for day in HARI_INDONESIA:
            var = tk.BooleanVar(value=True)
            self.day_check_vars[day] = var
            chk = tk.Checkbutton(wf, text=day[:3], variable=var, font=FONT_MAIN, bg=WIN_BG, activebackground=WIN_BG, command=self.save_config)
            chk.pack(side="left", padx=1)

        # Tab 3: Monthly
        self.tab_monthly = tk.Frame(self.notebook, bg=WIN_BG, padx=4, pady=4)
        self.notebook.add(self.tab_monthly, text="Monthly")
        mf = tk.Frame(self.tab_monthly, bg=WIN_BG)
        mf.pack(fill="x")
        tk.Label(mf, text="Tiap Tgl:", font=FONT_MAIN, bg=WIN_BG).pack(side="left")
        self.spin_month_date = ttk.Spinbox(mf, from_=1, to=31, width=3, font=FONT_MAIN)
        self.spin_month_date.set(1)
        self.spin_month_date.pack(side="left", padx=2)

        # Tab 4: Specific Date
        self.tab_specific = tk.Frame(self.notebook, bg=WIN_BG, padx=4, pady=4)
        self.notebook.add(self.tab_specific, text="Specific")
        sf = tk.Frame(self.tab_specific, bg=WIN_BG)
        sf.pack(fill="x")
        self.spin_spec_day = ttk.Spinbox(sf, from_=1, to=31, width=3, font=FONT_MAIN)
        self.spin_spec_day.set(datetime.datetime.now().day)
        self.spin_spec_day.pack(side="left", padx=1)
        self.combo_spec_month = ttk.Combobox(sf, values=BULAN_INDONESIA, width=9, font=FONT_MAIN, state="readonly")
        self.combo_spec_month.current(datetime.datetime.now().month - 1)
        self.combo_spec_month.pack(side="left", padx=1)
        self.spin_spec_year = ttk.Spinbox(sf, from_=2025, to=2035, width=5, font=FONT_MAIN)
        self.spin_spec_year.set(datetime.datetime.now().year)
        self.spin_spec_year.pack(side="left", padx=1)

        # Tab 5: Interval
        self.tab_interval = tk.Frame(self.notebook, bg=WIN_BG, padx=4, pady=4)
        self.notebook.add(self.tab_interval, text="Interval")
        inf = tk.Frame(self.tab_interval, bg=WIN_BG)
        inf.pack(fill="x")
        tk.Label(inf, text="Ulangi tiap:", font=FONT_MAIN, bg=WIN_BG).pack(side="left")
        self.spin_interval = ttk.Spinbox(inf, from_=5, to=2880, width=5, font=FONT_MAIN)
        self.spin_interval.set(360)
        self.spin_interval.pack(side="left", padx=2)
        tk.Label(inf, text="menit", font=FONT_MAIN, bg=WIN_BG).pack(side="left")

        # Label Hitung Mundur Sched
        self.lbl_sched_status = tk.Label(grp_sched, text="Scheduler: Disabled", font=FONT_MAIN, fg="#444444", bg=WIN_BG)
        self.lbl_sched_status.pack(anchor="w", padx=6, pady=(1, 3))

        # TERMINAL LOG MONITOR (LEBIH LUAS & LAPANG KARENA GATE INFO DIHAPUS)
        grp_log = tk.Frame(col_right, bg=WIN_BG)
        grp_log.pack(fill="both", expand=True)

        self.txt_log = tk.Text(grp_log, bg=TERM_BG, fg=TERM_FG, font=FONT_TERM, relief="solid", bd=1, wrap="none")
        self.txt_log.pack(fill="both", expand=True)

        # Bottom Bar: Jam, Counter & Tombol Clear Log
        b_bar = tk.Frame(col_right, bg=WIN_BG, pady=2)
        b_bar.pack(fill="x")
        
        self.lbl_clock_time = tk.Label(b_bar, text="00:00:00 WIB", font=FONT_MAIN, bg=WIN_BG)
        self.lbl_clock_time.pack(side="left")

        self.lbl_counter = tk.Label(b_bar, text="Count: 0x", font=FONT_MAIN, bg=WIN_BG)
        self.lbl_counter.pack(side="left", padx=8)

        btn_clear = tk.Button(b_bar, text="Clear Log", font=FONT_MAIN, bg=WIN_BTN, relief="raised", bd=2, padx=8, command=self.clear_log)
        btn_clear.pack(side="right")

    def apply_config_to_ui(self):
        self.baud_combobox.set(str(self.config.get("baud_rate", 9600)))
        self.spin_duration.set(str(self.config.get("restart_duration_sec", 4)))
        self.var_autoconnect.set(bool(self.config.get("auto_connect_usb", True)))
        self.var_sched_enabled.set(bool(self.config.get("scheduler_enabled", False)))

        raw_target = self.config.get("sched_target", "ALL")
        if "1" in raw_target:
            self.combo_sched_target.set("Scanner 1")
        elif "2" in raw_target:
            self.combo_sched_target.set("Scanner 2")
        else:
            self.combo_sched_target.set("ALL")

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
        now = datetime.datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M:%S") + f".{int(now.microsecond / 1000):03d}"
        line = f"{ts} => {message}"

        def _ui():
            self.txt_log.insert("end", line + "\n")
            self.txt_log.see("end")
        self.root.after(0, _ui)

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def clear_log(self):
        self.txt_log.delete("1.0", "end")

    # ==========================================
    # CLOCK
    # ==========================================
    def start_clock_timer(self):
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
        self.log(f"USB Ports Changed: {len(devices)} available")

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
        self.log("USB Cable Disconnected!")
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
                messagebox.showwarning("Warning", "Pilih Port USB terlebih dahulu.")
            return False

        if port == SIMULATION_PORT:
            self.is_simulation = True
            self.btn_connect.config(text="Disconnect")
            self.lbl_stat_port.config(text="Connected [SIMULATION]", bg=STATUS_GREEN)
            self.port_combobox.config(state="disabled")
            self.log("Connected to Virtual Arduino Mega 2560 Simulator.")
            self.save_config()
            return True

        baud = int(self.baud_combobox.get() or 9600)
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            time.sleep(2)
            self.is_simulation = False
            self.btn_connect.config(text="Disconnect")
            self.lbl_stat_port.config(text=f"Connected [{port} @ {baud}]", bg=STATUS_GREEN)
            self.port_combobox.config(state="disabled")
            self.save_config()
            self.log(f"Connected to Arduino Mega at {port} successfully.")
            threading.Thread(target=self.serial_reader_worker, daemon=True).start()
            self.send_serial_command("STATUS")
            return True
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to open {port}:\n{e}")
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

        self.btn_connect.config(text="Connect")
        self.lbl_stat_port.config(text="Disconnected / Socket Error", bg=STATUS_RED)
        self.port_combobox.config(state="readonly")
        self.log("USB Connection Closed.")

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
        lbl = self.lbl_stat_sc1 if channel == 1 else self.lbl_stat_sc2
        pin = "D7" if channel == 1 else "D8"

        if state == "ON":
            lbl.config(text=f"Connected [{pin} Normal]", bg=STATUS_GREEN)
        elif state == "RESTARTING":
            lbl.config(text=f"Restarting [{pin} Cut Power]", bg=STATUS_AMBER)
        elif state == "OFF":
            lbl.config(text=f"Power OFF [{pin} Cut Total]", bg=STATUS_RED)

    def send_serial_command(self, cmd):
        if self.is_simulation:
            self.log(f"Send Serial => {cmd}")
            self.simulate_hardware(cmd)
            return True

        if not (self.ser and self.ser.is_open):
            self.log("Command Aborted: USB Disconnected.")
            return False

        try:
            self.ser.write((cmd + "\n").encode('utf-8'))
            self.ser.flush()
            self.log(f"Send Serial => {cmd}")
            return True
        except Exception as e:
            self.log(f"Error Send: {e}")
            return False

    def simulate_hardware(self, cmd):
        dur = int(self.spin_duration.get() or 4)

        if cmd.startswith("RESTART:ALL"):
            self.update_channel_badge(1, "RESTARTING")
            threading.Timer(1.5, lambda: self.update_channel_badge(2, "RESTARTING")).start()
            threading.Timer(dur + 2.0, lambda: (
                self.update_channel_badge(1, "ON"),
                self.update_channel_badge(2, "ON"),
                self.log("STATUS:STAGGERED_COMPLETE:ALL_ON => Both Scanners Ready.")
            )).start()

        elif cmd.startswith("RESTART:1"):
            self.update_channel_badge(1, "RESTARTING")
            threading.Timer(dur, lambda: (
                self.update_channel_badge(1, "ON"),
                self.log("STATUS:RESTART_COMPLETE:CH1 => Scanner 1 Ready.")
            )).start()

        elif cmd.startswith("RESTART:2"):
            self.update_channel_badge(2, "RESTARTING")
            threading.Timer(dur, lambda: (
                self.update_channel_badge(2, "ON"),
                self.log("STATUS:RESTART_COMPLETE:CH2 => Scanner 2 Ready.")
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
    # AKSI RESTART
    # ==========================================
    def check_ready(self):
        if self.is_simulation or (self.ser and self.ser.is_open):
            return True
        if self.connect(silent=True):
            return True
        messagebox.showinfo("KCI_restart _qrscan", "Harap klik tombol 'Connect' terlebih dahulu.")
        return False

    def manual_restart(self, channel):
        if not self.check_ready():
            return
        ch_name = f"Scanner {channel}" if channel != "ALL" else "Kedua Scanner"
        if messagebox.askyesno("KCI_restart _qrscan", f"Eksekusi reboot daya pada {ch_name}?"):
            self.trigger_restart(channel=channel, source="MANUAL")

    def trigger_restart(self, channel="ALL", source="MANUAL"):
        dur_sec = int(self.spin_duration.get() or 4)
        dur_ms = dur_sec * 1000

        def _exec():
            self.btn_restart_ch1.config(state="disabled")
            self.btn_restart_ch2.config(state="disabled")
            self.btn_restart_all.config(state="disabled")

            self.restart_count += 1
            self.lbl_counter.config(text=f"Count: {self.restart_count}x")

            if channel == "ALL":
                self.log(f"[{source}] Triggered Staggered Reboot (Duration: {dur_sec}s)...")
                self.send_serial_command(f"RESTART:ALL:{dur_ms}")
                time.sleep(dur_sec + 2.5)
            else:
                self.log(f"[{source}] Triggered Scanner {channel} Reboot (Duration: {dur_sec}s)...")
                self.send_serial_command(f"RESTART:{channel}:{dur_ms}")
                time.sleep(dur_sec + 0.8)

            if self.is_simulation or (self.ser and self.ser.is_open):
                self.btn_restart_ch1.config(state="normal")
                self.btn_restart_ch2.config(state="normal")
                self.btn_restart_all.config(state="normal")

        threading.Thread(target=_exec, daemon=True).start()

    # ==========================================
    # SCHEDULER ENGINE
    # ==========================================
    def on_scheduler_toggle(self):
        self.save_config()
        if self.var_sched_enabled.get():
            if self.notebook.index(self.notebook.select()) == 4:
                self.last_interval_trigger = time.time()
            self.log("Scheduler Engine ENABLED.")
        else:
            self.log("Scheduler Engine DISABLED.")
            self.lbl_sched_status.config(text="Scheduler: Disabled")

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

                        if tab_idx == 0: # Daily
                            th, tm = self.get_target_hour_min()
                            if now.hour == th and now.minute == tm and now.minute != last_fired_minute:
                                last_fired_minute = now.minute
                                self.log(f"[Scheduler] Daily target reached ({th:02d}:{tm:02d} WIB). Triggering {target_ch}")
                                self.trigger_restart(channel=target_ch, source="AUTO-DAILY")

                            target_dt = now.replace(hour=th, minute=tm, second=0, microsecond=0)
                            if target_dt <= now:
                                target_dt += datetime.timedelta(days=1)
                            diff = target_dt - now
                            h, rem = divmod(int(diff.total_seconds()), 3600)
                            m, s = divmod(rem, 60)
                            self.root.after(0, lambda: self.lbl_sched_status.config(
                                text=f"Daily: {th:02d}:{tm:02d} WIB (in ~{h}h {m}m {s}s)"
                            ))

                        elif tab_idx == 4: # Interval
                            intv_min = int(self.spin_interval.get() or 360)
                            intv_sec = intv_min * 60
                            elapsed = time.time() - self.last_interval_trigger

                            if elapsed >= intv_sec:
                                self.last_interval_trigger = time.time()
                                self.log(f"[Scheduler] Interval {intv_min}m reached. Rebooting...")
                                self.trigger_restart(channel=target_ch, source="AUTO-INTERVAL")

                            rem = max(0, int(intv_sec - elapsed))
                            m, s = divmod(rem, 60)
                            h, m = divmod(m, 60)
                            self.root.after(0, lambda: self.lbl_sched_status.config(
                                text=f"Interval ({intv_min}m): Countdown {h:02d}:{m:02d}:{s:02d}"
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
    app = KciGateRestarterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
