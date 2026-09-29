# Ws.py - Wat Store / Wat OS 1.3
import os, sys, threading, urllib.request, webbrowser
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
import webview

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
APPS_DIR=os.path.join(BASE_DIR,"Apps")
SYSTEM_DIR=os.path.join(BASE_DIR,"System")
SIGNAL_FILE=os.path.join(SYSTEM_DIR,"apps_changed.signal")
STORE_URL="https://ws4862.github.io/ws"
os.makedirs(APPS_DIR,exist_ok=True); os.makedirs(SYSTEM_DIR,exist_ok=True)

BG=(.015,.02,.04,1); CYAN=(0,.85,1,1); WHITE=(.93,.97,1,1); GRAY=(.48,.58,.68,1)

class InstallScreen(BoxLayout):
    def __init__(self,**kw):
        super().__init__(orientation="vertical",padding=dp(50),spacing=dp(20),**kw)
        with self.canvas.before:
            Color(*BG); self.bg=Rectangle(pos=self.pos,size=self.size)
        self.bind(pos=self.sync,size=self.sync)
        self.title=Label(text="WAT OS",font_size=dp(34),bold=True,color=CYAN,size_hint_y=None,height=dp(60))
        self.status=Label(text="INSTALANDO",font_size=dp(28),bold=True,color=WHITE)
        self.bar=ProgressBar(max=1,value=0,size_hint_y=None,height=dp(10))
        self.percent=Label(text="0%",font_size=dp(18),color=GRAY,size_hint_y=None,height=dp(40))
        self.info=Label(text="Preparando...",font_size=dp(15),color=GRAY)
        for x in (self.title,self.status,self.bar,self.percent,self.info): self.add_widget(x)
    def sync(self,*a): self.bg.pos=self.pos; self.bg.size=self.size

class API:
    def __init__(self,app): self.app=app
    def instalar(self,url):
        if not url: return False
        threading.Thread(target=self.download,args=(url,),daemon=True).start(); return True
    def download(self,url):
        try:
            Clock.schedule_once(lambda dt:self.app.show_install())
            name=os.path.basename(url.split("?",1)[0]) or "app.wata"
            if not name.lower().endswith(".wata"): name+=".wata"
            dest=os.path.join(APPS_DIR,name)
            req=urllib.request.Request(url,headers={"User-Agent":"WatOS-Ws/1.3"})
            with urllib.request.urlopen(req,timeout=60) as r:
                total=int(r.headers.get("Content-Length") or 0); done=0
                tmp=dest+".part"
                with open(tmp,"wb") as f:
                    while True:
                        chunk=r.read(65536)
                        if not chunk: break
                        f.write(chunk); done+=len(chunk)
                        if total: Clock.schedule_once(lambda dt,p=done/total:self.app.progress(p))
                os.replace(tmp,dest)
            with open(SIGNAL_FILE,"w",encoding="utf-8") as f: f.write(str(os.path.getmtime(dest)))
            Clock.schedule_once(lambda dt:self.app.done(name))
        except Exception as e:
            Clock.schedule_once(lambda dt,e=str(e):self.app.error(e))

class WsApp(App):
    def build(self):
        Window.clearcolor=BG; self.install=InstallScreen(); self.api=API(self); self.web=None
        Clock.schedule_once(self.open_store,.3); return self.install
    def open_store(self,*a):
        def run():
            self.web=webview.create_window("Ws — Wat Store",STORE_URL,width=1100,height=750,js_api=self.api)
            webview.start()
        threading.Thread(target=run,daemon=True).start()
    def show_install(self,*a):
        self.root.clear_widgets(); self.root.add_widget(self.install)
    def progress(self,p):
        self.install.bar.value=p; self.install.percent.text=f"{int(p*100)}%"
        self.install.info.text="Baixando aplicativo..."
    def done(self,name):
        self.install.bar.value=1; self.install.percent.text="100%"
        self.install.status.text="INSTALAÇÃO CONCLUÍDA"; self.install.info.text=name+" foi instalado."
        Clock.schedule_once(lambda dt:self.reopen(),1.5)
    def error(self,e):
        self.install.status.text="ERRO"; self.install.info.text=str(e)
    def reopen(self,*a):
        if self.web:
            try:self.web.show()
            except Exception: pass

if __name__=="__main__": WsApp().run()
