# Wat OS 1.3.1
# Interface principal do Wat OS
# Ubuntu Server + Kivy
#
# Recursos:
# - Boot splash
# - Primeiro acesso / criação de senha
# - Tela de bloqueio
# - Home futurista
# - Descoberta automática de apps .wata
# - Comunicação com Ws.py por arquivo de sinal
# - Menu Energia no canto superior direito
# - Desligar / Reiniciar / Bloquear
#
# O botão de energia usa systemctl, portanto o Ubuntu continua sendo
# a base do sistema enquanto o Wat OS funciona como sua interface.

import os
import sys
import time
import json
import hashlib
import secrets
import subprocess
import webbrowser
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line


# ---------------------------------------------------------
# CAMINHOS
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
APPS_DIR = BASE_DIR / "Apps"
DATA_DIR = BASE_DIR / "Data"
SYSTEM_DIR = BASE_DIR / "System"
LOGS_DIR = BASE_DIR / "Logs"

CONFIG_FILE = DATA_DIR / "config.json"
SIGNAL_FILE = SYSTEM_DIR / "apps_changed.signal"

APPS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# VISUAL
# ---------------------------------------------------------

BG = (0.015, 0.025, 0.045, 1)
PANEL = (0.035, 0.055, 0.085, 1)
PANEL2 = (0.055, 0.080, 0.120, 1)
CYAN = (0.10, 0.85, 1, 1)
WHITE = (0.90, 0.96, 1, 1)
MUTED = (0.45, 0.60, 0.70, 1)
RED = (1, 0.20, 0.25, 1)
GREEN = (0.20, 1, 0.55, 1)


def rounded_bg(widget, color=PANEL, radius=18):
    with widget.canvas.before:
        Color(*color)
        widget._rounded = RoundedRectangle(
            pos=widget.pos,
            size=widget.size,
            radius=[dp(radius)]
        )
    widget.bind(
        pos=lambda *_: setattr(widget._rounded, "pos", widget.pos),
        size=lambda *_: setattr(widget._rounded, "size", widget.size)
    )


class FuturisticButton(Button):
    def __init__(self, accent=CYAN, **kwargs):
        super().__init__(**kwargs)
        self.accent = accent
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = WHITE
        self.font_size = dp(16)
        self.bold = True
        self.bind(pos=self._draw, size=self._draw, state=self._draw)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*PANEL2 if self.state == "normal" else self.accent)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            Color(*self.accent)
            Line(
                rounded_rectangle=(
                    self.x, self.y, self.width, self.height, dp(14)
                ),
                width=1.1
            )


# ---------------------------------------------------------
# SEGURANÇA / CONFIGURAÇÃO
# ---------------------------------------------------------

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        180_000
    )

    return salt.hex(), digest.hex()


def verify_password(password, salt_hex, hash_hex):
    try:
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            180_000
        )
        return secrets.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


def load_config():
    if not CONFIG_FILE.exists():
        return None

    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_config(config):
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


# ---------------------------------------------------------
# APP INFO
# ---------------------------------------------------------

def parse_wata(path):
    info = {
        "name": path.stem,
        "version": "",
        "base": "",
        "ico": "",
        "creator": ""
    }

    try:
        import zipfile

        with zipfile.ZipFile(path, "r") as z:
            if "config.txt" not in z.namelist():
                return info

            text = z.read("config.txt").decode("utf-8", errors="replace")

            import re

            for key in ("name", "version", "base", "ico", "creator"):
                match = re.search(
                    rf"<{key}>(.*?)</{key}>",
                    text,
                    re.IGNORECASE | re.DOTALL
                )
                if match:
                    info[key] = match.group(1).strip()

    except Exception:
        pass

    return info


# ---------------------------------------------------------
# TELAS
# ---------------------------------------------------------

class BackgroundLayout(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*BG)
            self.bg = Rectangle(pos=self.pos, size=self.size)

        self.bind(
            pos=lambda *_: setattr(self.bg, "pos", self.pos),
            size=lambda *_: setattr(self.bg, "size", self.size)
        )


class BootScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BackgroundLayout()

        title = Label(
            text="[b]WAT OS[/b]",
            markup=True,
            font_size=dp(42),
            color=CYAN,
            size_hint=(1, None),
            height=dp(65),
            pos_hint={"center_x": 0.5, "center_y": 0.57}
        )

        subtitle = Label(
            text="INITIALIZING SYSTEM...",
            font_size=dp(13),
            color=MUTED,
            size_hint=(1, None),
            height=dp(35),
            pos_hint={"center_x": 0.5, "center_y": 0.49}
        )

        bar = ProgressBar(
            max=100,
            value=0,
            size_hint=(None, None),
            size=(dp(300), dp(8)),
            pos_hint={"center_x": 0.5, "center_y": 0.42}
        )

        root.add_widget(title)
        root.add_widget(subtitle)
        root.add_widget(bar)
        self.add_widget(root)

        self.progress = 0
        Clock.schedule_interval(self.animate, 0.025)

    def animate(self, dt):
        self.progress += 2
        for child in self.children:
            if isinstance(child, BackgroundLayout):
                for widget in child.children:
                    if isinstance(widget, ProgressBar):
                        widget.value = self.progress

        if self.progress >= 100:
            Clock.unschedule(self.animate)
            Clock.schedule_once(
                lambda *_: App.get_running_app().continue_boot(),
                0.25
            )


class SetupScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BackgroundLayout()

        panel = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(25),
            size_hint=(0.88, 0.72),
            pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        rounded_bg(panel)

        title = Label(
            text="[b]CONFIGURAÇÃO INICIAL[/b]",
            markup=True,
            color=CYAN,
            font_size=dp(24),
            size_hint_y=None,
            height=dp(50)
        )

        user = TextInput(
            hint_text="Nome de usuário",
            multiline=False,
            size_hint_y=None,
            height=dp(48)
        )

        password = TextInput(
            hint_text="Senha",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(48)
        )

        confirm = TextInput(
            hint_text="Confirmar senha",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(48)
        )

        status = Label(
            text="",
            color=RED,
            size_hint_y=None,
            height=dp(35)
        )

        btn = FuturisticButton(
            text="CRIAR SISTEMA",
            size_hint_y=None,
            height=dp(52)
        )

        def create(_):
            username = user.text.strip()
            pw = password.text
            pw2 = confirm.text

            if not username or not pw:
                status.text = "Preencha usuário e senha."
                return

            if pw != pw2:
                status.text = "As senhas não coincidem."
                return

            salt, digest = hash_password(pw)

            save_config({
                "username": username,
                "salt": salt,
                "password_hash": digest,
                "first_run_complete": True
            })

            App.get_running_app().show_lock()

        btn.bind(on_release=create)

        panel.add_widget(title)
        panel.add_widget(user)
        panel.add_widget(password)
        panel.add_widget(confirm)
        panel.add_widget(status)
        panel.add_widget(btn)

        root.add_widget(panel)
        self.add_widget(root)


class LockScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BackgroundLayout()

        box = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(25),
            size_hint=(0.82, 0.48),
            pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        rounded_bg(box)

        self.clock_label = Label(
            text="",
            color=CYAN,
            font_size=dp(30),
            size_hint_y=None,
            height=dp(55)
        )

        self.user_label = Label(
            text="",
            color=WHITE,
            font_size=dp(17),
            size_hint_y=None,
            height=dp(40)
        )

        password = TextInput(
            hint_text="Senha",
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(48)
        )

        status = Label(
            text="",
            color=RED,
            size_hint_y=None,
            height=dp(30)
        )

        btn = FuturisticButton(
            text="DESBLOQUEAR",
            size_hint_y=None,
            height=dp(50)
        )

        def unlock(_):
            config = load_config()

            if config and verify_password(
                password.text,
                config.get("salt", ""),
                config.get("password_hash", "")
            ):
                password.text = ""
                status.text = ""
                App.get_running_app().show_home()
            else:
                status.text = "Senha incorreta."

        btn.bind(on_release=unlock)

        box.add_widget(self.clock_label)
        box.add_widget(self.user_label)
        box.add_widget(password)
        box.add_widget(status)
        box.add_widget(btn)

        root.add_widget(box)
        self.add_widget(root)

        Clock.schedule_interval(self.update_clock, 1)

    def update_clock(self, *_):
        self.clock_label.text = time.strftime("%H:%M:%S")
        config = load_config()
        if config:
            self.user_label.text = config.get("username", "Usuário")


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.root_layout = BackgroundLayout()

        # Top bar
        top = BoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(62),
            padding=[dp(12), dp(8)],
            spacing=dp(10)
        )

        title = Label(
            text="[b]WAT OS[/b]",
            markup=True,
            color=CYAN,
            font_size=dp(22),
            halign="left",
            valign="middle"
        )
        title.bind(size=lambda *_: setattr(title, "text_size", title.size))

        self.clock = Label(
            text="",
            color=MUTED,
            font_size=dp(15),
            size_hint_x=None,
            width=dp(80)
        )

        power = FuturisticButton(
            text="⚡",
            accent=RED,
            size_hint_x=None,
            width=dp(54)
        )
        power.bind(on_release=lambda *_: self.show_power_menu())

        top.add_widget(title)
        top.add_widget(Label())
        top.add_widget(self.clock)
        top.add_widget(power)

        self.root_layout.add_widget(top)

        # Área de apps
        self.apps_grid = GridLayout(
            cols=2,
            spacing=dp(14),
            padding=dp(18),
            size_hint=(1, 1)
        )

        self.root_layout.add_widget(self.apps_grid)
        self.add_widget(self.root_layout)

        Clock.schedule_interval(self.update_clock, 1)
        Clock.schedule_interval(self.check_apps_signal, 1)

    def update_clock(self, *_):
        self.clock.text = time.strftime("%H:%M")

    def on_pre_enter(self, *_):
        self.refresh_apps()

    def check_apps_signal(self, *_):
        if SIGNAL_FILE.exists():
            try:
                SIGNAL_FILE.unlink()
            except Exception:
                pass

            self.refresh_apps()

    def refresh_apps(self):
        self.apps_grid.clear_widgets()

        factory = [
            ("🛍  WS", "Apps/Ws.py"),
            ("🔄  UPDATE", "Apps/up.py"),
        ]

        for name, target in factory:
            self.add_app_button(name, target, factory=True)

        wata_files = sorted(APPS_DIR.glob("*.wata"))

        for path in wata_files:
            info = parse_wata(path)
            name = info.get("name") or path.stem
            version = info.get("version", "")
            label = name

            if version:
                label += f"\n{version}"

            self.add_app_button(
                label,
                str(path),
                factory=False
            )

    def add_app_button(self, name, target, factory=False):
        button = FuturisticButton(
            text=name,
            accent=CYAN if factory else GREEN,
            size_hint_y=None,
            height=dp(100)
        )

        button.bind(
            on_release=lambda *_: self.launch_app(target)
        )

        self.apps_grid.add_widget(button)

    def launch_app(self, target):
        target_path = Path(target)

        if not target_path.is_absolute():
            target_path = BASE_DIR / target_path

        if not target_path.exists():
            self.show_message(
                "APP NÃO ENCONTRADO",
                f"Não foi possível encontrar:\n{target_path}"
            )
            return

        try:
            if target_path.suffix.lower() == ".py":
                subprocess.Popen(
                    [
                        sys.executable,
                        str(target_path)
                    ],
                    cwd=str(target_path.parent)
                )

            elif target_path.suffix.lower() == ".wata":
                import zipfile
                import tempfile

                temp_dir = Path(
                    tempfile.mkdtemp(prefix="watos_app_")
                )

                with zipfile.ZipFile(target_path, "r") as z:
                    z.extractall(temp_dir)

                info_file = temp_dir / "config.txt"

                if not info_file.exists():
                    self.show_message(
                        "APP INVÁLIDO",
                        "O arquivo .wata não possui config.txt."
                    )
                    return

                info_text = info_file.read_text(
                    encoding="utf-8",
                    errors="replace"
                )

                import re

                match = re.search(
                    r"<base>(.*?)</base>",
                    info_text,
                    re.IGNORECASE | re.DOTALL
                )

                if not match:
                    self.show_message(
                        "APP INVÁLIDO",
                        "Não foi encontrado <base> no config.txt."
                    )
                    return

                base_name = match.group(1).strip()
                base_file = temp_dir / base_name

                if not base_file.exists():
                    self.show_message(
                        "APP INVÁLIDO",
                        f"Arquivo base não encontrado:\n{base_name}"
                    )
                    return

                if base_file.suffix.lower() in (
                    ".html", ".htm"
                ):
                    webbrowser.open(base_file.as_uri())

                elif base_file.suffix.lower() == ".py":
                    subprocess.Popen(
                        [sys.executable, str(base_file)],
                        cwd=str(temp_dir)
                    )

                else:
                    webbrowser.open(base_file.as_uri())

        except Exception as e:
            self.show_message(
                "ERRO AO ABRIR APP",
                str(e)
            )

    # -----------------------------------------------------
    # MENU DE ENERGIA
    # -----------------------------------------------------

    def show_power_menu(self):
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(18)
        )

        title = Label(
            text="[b]⚡ ENERGIA[/b]",
            markup=True,
            color=CYAN,
            font_size=dp(21),
            size_hint_y=None,
            height=dp(45)
        )

        btn_lock = FuturisticButton(
            text="🔒  Bloquear",
            accent=CYAN,
            size_hint_y=None,
            height=dp(50)
        )

        btn_restart = FuturisticButton(
            text="🔄  Reiniciar",
            accent=CYAN,
            size_hint_y=None,
            height=dp(50)
        )

        btn_poweroff = FuturisticButton(
            text="🔴  Desligar",
            accent=RED,
            size_hint_y=None,
            height=dp(50)
        )

        btn_cancel = FuturisticButton(
            text="Cancelar",
            accent=MUTED,
            size_hint_y=None,
            height=dp(45)
        )

        content.add_widget(title)
        content.add_widget(btn_lock)
        content.add_widget(btn_restart)
        content.add_widget(btn_poweroff)
        content.add_widget(btn_cancel)

        popup = Popup(
            title="",
            content=content,
            size_hint=(0.82, None),
            height=dp(340),
            separator_height=0,
            background_color=PANEL
        )

        btn_cancel.bind(on_release=popup.dismiss)

        def lock(_):
            popup.dismiss()
            App.get_running_app().show_lock()

        btn_lock.bind(on_release=lock)

        def restart(_):
            popup.dismiss()
            self.confirm_power(
                "REINICIAR O COMPUTADOR?",
                ["systemctl", "reboot"]
            )

        btn_restart.bind(on_release=restart)

        def poweroff(_):
            popup.dismiss()
            self.confirm_power(
                "DESLIGAR O COMPUTADOR?",
                ["systemctl", "poweroff"]
            )

        btn_poweroff.bind(on_release=poweroff)

        popup.open()

    def confirm_power(self, message, command):
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(18)
        )

        label = Label(
            text=message,
            color=WHITE,
            font_size=dp(18)
        )

        buttons = BoxLayout(
            spacing=dp(10),
            size_hint_y=None,
            height=dp(52)
        )

        cancel = FuturisticButton(
            text="Cancelar",
            accent=MUTED
        )

        confirm = FuturisticButton(
            text="CONFIRMAR",
            accent=RED
        )

        buttons.add_widget(cancel)
        buttons.add_widget(confirm)

        content.add_widget(label)
        content.add_widget(buttons)

        popup = Popup(
            title="",
            content=content,
            size_hint=(0.84, None),
            height=dp(190),
            separator_height=0,
            background_color=PANEL
        )

        cancel.bind(on_release=popup.dismiss)

        def execute(_):
            popup.dismiss()
            try:
                subprocess.Popen(command)
            except Exception as e:
                self.show_message(
                    "ERRO DE ENERGIA",
                    f"Não foi possível executar:\n{e}"
                )

        confirm.bind(on_release=execute)
        popup.open()

    def show_message(self, title, message):
        content = BoxLayout(
            orientation="vertical",
            padding=dp(18),
            spacing=dp(12)
        )

        label = Label(
            text=message,
            color=WHITE
        )

        close = FuturisticButton(
            text="OK",
            size_hint_y=None,
            height=dp(48)
        )

        content.add_widget(label)
        content.add_widget(close)

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.85, 0.45)
        )

        close.bind(on_release=popup.dismiss)
        popup.open()


# ---------------------------------------------------------
# APP PRINCIPAL
# ---------------------------------------------------------

class WatOS(App):
    title = "Wat OS"

    def build(self):
        Window.clearcolor = BG

        self.sm = ScreenManager()

        self.sm.add_widget(
            BootScreen(name="boot")
        )
        self.sm.add_widget(
            SetupScreen(name="setup")
        )
        self.sm.add_widget(
            LockScreen(name="lock")
        )
        self.sm.add_widget(
            HomeScreen(name="home")
        )

        self.sm.current = "boot"

        return self.sm

    def continue_boot(self):
        config = load_config()

        if not config or not config.get("first_run_complete"):
            self.sm.current = "setup"
        else:
            self.show_lock()

    def show_lock(self):
        self.sm.current = "lock"

    def show_home(self):
        self.sm.current = "home"


if __name__ == "__main__":
    WatOS().run()
