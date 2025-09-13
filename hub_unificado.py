# hub_unificado.py
import os
import threading
import asyncio
import queue
import keyboard
import subprocess
import webbrowser
import customtkinter as ctk
from customtkinter import CTkImage
import tkinter as tk
from tkinter import scrolledtext, messagebox
from PIL import Image, ImageTk
import itertools

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from core_utils import log_queue, log_interface, carregar_status, update_status, adicionar_sinonimo
from core_desktop import abrir_app_desktop, abrir_site_known, interpretar_comando_desktop, fechar_app, extrair_palavra_chave
from core_web import pesquisar_youtube, pesquisar_google, tocar_video_youtube, abrir_link_web, pausar_video, retomar_video
from core_voice import VoiceCore
from core_vigia import VigiaManager
from gui_app_manager import AppManagerWindow
from gui_overlay import OverlayWindow
from gui_learning_dialog import LearningDialog
from core_monitor import PCMonitor


async_command_queue = asyncio.Queue()
voice_forward_queue = queue.Queue()
ui_voice_queue = queue.Queue()


class AssistenteMestreGUI(ctk.CTk):
    def __init__(self, loop, voice_core, vigia_manager: VigiaManager):
        super().__init__()
        self.loop = loop
        self.voice_core = voice_core
        self.vigia_manager = vigia_manager
        self.monitor = None
        self.title("Assistente Mestre (Vigia + Voz)")
        self.geometry("860x650")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.command_history = []
        self.history_index = -1
        self.app_manager_window = None
        self.dialog = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(10, 0))
        status_frame.grid_columnconfigure(0, weight=1)
        status = carregar_status()
        self.status_label = ctk.CTkLabel(status_frame, text=f"Estado: {status.get('estado')} | Processo: {status.get('processo_ativo')}", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(self, state='disabled', wrap=tk.WORD, bg="#2b2b2b", fg="#d3d3d3", font=("Helvetica", 10))
        self.log_area.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)

        command_frame = ctk.CTkFrame(self)
        command_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        command_frame.grid_columnconfigure(0, weight=1)
        
        self.command_entry = ctk.CTkEntry(command_frame, placeholder_text="Use: yt, web, pc, tocar, abrir...", font=("Helvetica", 11))
        self.command_entry.grid(row=0, column=0, sticky="ew", padx=(10,5), pady=10)
        self.command_entry.bind("<Return>", self.send_command)
        self.command_entry.bind("<Up>", self.navigate_history_up)
        self.command_entry.bind("<Down>", self.navigate_history_down)

        self.send_button = ctk.CTkButton(command_frame, text="Enviar", width=100, command=self.send_command)
        self.send_button.grid(row=0, column=1, padx=5, pady=10)

        self.mic_button = ctk.CTkButton(command_frame, text="Mic", width=80, command=lambda: self.voice_core.start_listening("desktop"))
        self.mic_button.grid(row=0, column=2, padx=(5,10), pady=10)

        bottom_buttons_frame = ctk.CTkFrame(self)
        bottom_buttons_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=10, pady=5)
        bottom_buttons_frame.grid_columnconfigure((0, 1), weight=1)

        self.vigia_button = ctk.CTkButton(bottom_buttons_frame, text="Vigia: OFF", command=self.toggle_vigia)
        self.vigia_button.grid(row=0, column=0, padx=(0,5), pady=5, sticky="ew")
        
        self.manager_button = ctk.CTkButton(bottom_buttons_frame, text="Gerenciar Apps", command=self.open_app_manager_window)
        self.manager_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.gif_frames = {}
        self.carregar_gif("feliz", "feliz.gif")
        self.carregar_gif("chorando", "chorando.gif")
        self.carregar_gif("raiva", "raiva.gif")
        self.carregar_gif("confuso", "confuso.gif")
        
        self.overlay = OverlayWindow(self, self.gif_frames, close_callback=self.close_current_game_from_overlay)

        self.after(120, self.drain_log_queue)
        self.after(150, self.drain_voice_ui_queue)

    def close_current_game_from_overlay(self):
        if self.monitor and self.monitor.active_game_name:
            game_name = self.monitor.active_game_name
            log_interface(f"Recebido comando para fechar '{game_name}' pelo overlay.", "info")
            comando_completo = f"pc, fechar {game_name}"
            self.loop.call_soon_threadsafe(lambda c=comando_completo: asyncio.create_task(async_command_queue.put(c)))
        else:
            log_interface("Botão de fechar do overlay clicado, mas nenhum jogo ativo detectado.", "warning")

    def trigger_learning_flow(self, comando_original):
        palavra_desconhecida = extrair_palavra_chave(comando_original)
        if not palavra_desconhecida:
            log_interface(f"Não consegui entender o comando '{comando_original}'", "warning")
            return

        def on_learn_complete(palavra_nova, app_selecionado):
            if palavra_nova and app_selecionado:
                adicionar_sinonimo(app_selecionado, palavra_nova)
                comando_reformulado = f"pc, {comando_original}"
                self.loop.call_soon_threadsafe(lambda c=comando_reformulado: asyncio.create_task(async_command_queue.put(c)))
        
        self.dialog = LearningDialog(self, palavra_desconhecida, on_learn_complete)

    def show_happy_overlay(self):
        self.overlay.set_estado_emocao("feliz")
    
    def hide_overlay(self):
        self.overlay.hide()

    def set_estado_emocao(self, estado):
        self.overlay.set_estado_emocao(estado)

    def open_app_manager_window(self):
        if self.app_manager_window is None or not self.app_manager_window.winfo_exists():
            self.app_manager_window = AppManagerWindow(self)
        else:
            self.app_manager_window.focus()

    def carregar_gif(self, nome, arquivo):
        try:
            gif = Image.open(arquivo)
            frames = []
            for i in range(gif.n_frames):
                gif.seek(i)
                frame_resized = gif.copy().convert("RGBA").resize((128, 128), Image.Resampling.LANCZOS)
                frames.append(ImageTk.PhotoImage(frame_resized))
            self.gif_frames[nome] = frames
        except Exception as e:
            log_interface(f"Erro ao carregar GIF '{arquivo}': {e}", "error")

    def toggle_vigia(self, *args):
        is_running = self.vigia_manager.is_running()
        if is_running:
            self.vigia_manager.stop()
            self.vigia_button.configure(text="Vigia: OFF")
        else:
            self.vigia_manager.start()
            self.vigia_button.configure(text="Vigia: ON")
        log_interface(f"[VIGIA] Vigia {'desativado' if is_running else 'ativado'} via GUI.", "vigia")

    def send_command(self, event=None):
        command = self.command_entry.get().strip()
        if command:
            self.log_message(f"> {command}", "user")
            self.loop.call_soon_threadsafe(lambda c=command: asyncio.create_task(async_command_queue.put(c)))
            self.command_history.append(command)
            self.history_index = len(self.command_history)
            self.command_entry.delete(0, tk.END)

    def navigate_history_up(self, event=None):
        if self.history_index > 0:
            self.history_index -= 1
            cmd = self.command_history[self.history_index]
            self.command_entry.delete(0, tk.END)
            self.command_entry.insert(0, cmd)
        return "break"

    def navigate_history_down(self, event=None):
        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            cmd = self.command_history[self.history_index]
            self.command_entry.delete(0, tk.END)
            self.command_entry.insert(0, cmd)
        else:
            self.history_index = len(self.command_history)
            self.command_entry.delete(0, tk.END)
        return "break"

    def log_message(self, message: str, tag: str = "info"):
        colors = {"info": "#87CEEB", "success": "#90EE90", "warning": "#FFD700", "error": "#F08080", "user": "#FFFFFF", "web": "#D8BFD8", "desktop": "#ADD8E6", "voz": "#FFDAB9", "vigia": "#E6E6FA", "manager": "#DAA520"}
        try:
            self.log_area.configure(state='normal')
            self.log_area.tag_config(tag, foreground=colors.get(tag, "white"))
            self.log_area.insert(tk.END, message + '\n', tag)
            self.log_area.configure(state='disabled')
            self.log_area.see(tk.END)
        except Exception as e:
            print(f"Erro no log: {e}")

    def drain_log_queue(self):
        try:
            while not log_queue.empty():
                entry = log_queue.get_nowait()
                self.log_message(entry.get("message", ""), entry.get("tag", "info"))
            status = carregar_status()
            self.status_label.configure(text=f"Estado: {status.get('estado')} | Processo: {status.get('processo_ativo')}")
        finally:
            self.after(120, self.drain_log_queue)

    def drain_voice_ui_queue(self):
        try:
            while not ui_voice_queue.empty():
                entry = ui_voice_queue.get_nowait()
                msg = entry.get('message', str(entry))
                self.log_message(f"[VOZ] {msg}", "voz")
                self.status_label.configure(text=f"Voz: {msg}")
        finally:
            self.after(150, self.drain_voice_ui_queue)

    def on_closing(self):
        if messagebox.askokcancel("Sair", "Tem certeza que quer encerrar o assistente?"):
            if self.monitor and self.monitor.is_running: 
                self.monitor.stop()
            update_status("padrao", None)
            try:
                if self.loop.is_running():
                    self.loop.call_soon_threadsafe(self.loop.stop)
            except Exception as e:
                print(f"Erro ao parar o loop: {e}")
            self.destroy()

async def bot_main(gui_instance: AssistenteMestreGUI):
    page = None
    context = None
    p = None
    try:
        from playwright.async_api import async_playwright
        p = await async_playwright().start()
        context = await p.chromium.launch_persistent_context(
            user_data_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "playwright_profile"),
            headless=False,
            args=['--disable-blink-features=AutomationControlled', '--start-maximized', '--disable-session-crashed-bubble']
        )
        if context.pages: page = context.pages[0]
        else: page = await context.new_page()
        await page.goto("https://www.google.com", timeout=60000)
        screen_size = await page.evaluate('() => ({width: window.screen.width, height: window.screen.height})')
        await page.set_viewport_size(screen_size)
        log_interface("[WEB] Navegador Chromium iniciado e pronto.", "web")
    except Exception as e:
        log_interface(f"[WEB] ERRO: Não foi possível iniciar o navegador: {e}", "error")

    log_interface("[SYSTEM] 🤖 Robô Mestre Pronto!", "success")
    
    while True:
        try:
            comando_completo = (await async_command_queue.get()).strip()
            if comando_completo is None: break
            
            comando_lower = comando_completo.lower()
            comandos_media = ["play", "pause", "pausar", "continuar", "retomar"]

            if comando_lower in comandos_media:
                if page: await pausar_video(page)
                async_command_queue.task_done()
                continue
            if comando_lower.startswith("__vigia"):
                if comando_lower == "__vigia_pause__":
                    if page: await pausar_video(page)
                elif comando_lower == "__vigia_resume__":
                    if page: await retomar_video(page)
                async_command_queue.task_done()
                continue
            
            if comando_lower.isdigit():
                numero = int(comando_lower)
                from core_web import ultimos_resultados_pesquisa
                if ultimos_resultados_pesquisa:
                    tipo = ultimos_resultados_pesquisa[0].get("tipo")
                    if tipo == "yt":
                        if page: await tocar_video_youtube(numero, page)
                    elif tipo == "web":
                        if page: await abrir_link_web(numero, page)
                else:
                    log_interface(f"Digite um número apenas após uma pesquisa.", "warning")
                async_command_queue.task_done()
                continue

            partes = comando_completo.split(',', 1)
            if len(partes) == 2:
                prefixo = partes[0].strip().lower()
                acao = partes[1].strip()

                if prefixo == "yt":
                    if page: await pesquisar_youtube(acao, page)
                elif prefixo == "web":
                    if page: await pesquisar_google(acao, page)
                elif prefixo == "pc":
                    ordem = interpretar_comando_desktop(acao)
                    if ordem:
                        if ordem["funcao"] == "fechar_app":
                            gui_instance.overlay.set_estado_emocao("chorando")
                            await asyncio.sleep(2)
                            fechar_app(ordem["parametros"]["nome"])
                            gui_instance.overlay.hide()
                        elif ordem["funcao"] == "abrir_app":
                            abrir_app_desktop(ordem["parametros"]["nome"])
                        elif ordem["funcao"] == "abrir_site":
                            abrir_site_known(ordem["parametros"]["nome"])
                    else:
                        log_interface(f"Não reconheci o comando '{acao}'. Abrindo assistente de aprendizado...", "warning")
                        gui_instance.loop.call_soon_threadsafe(gui_instance.trigger_learning_flow, acao)
                else:
                    log_interface(f"Prefixo '{prefixo}' desconhecido.", "error")
            else:
                log_interface(f"Comando ou formato inválido: '{comando_completo}'", "error")

            async_command_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            log_interface(f"[SYSTEM] Erro crítico no loop principal: {e}", "error")

    if context:
        try: await context.close()
        except: pass
    if p:
        try: await p.stop()
        except: pass

def voice_forwarder_thread(loop: asyncio.AbstractEventLoop, forward_queue: "queue.Queue"):
    while True:
        cmd = forward_queue.get()
        if cmd is None: break
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(async_command_queue.put(cmd), loop)

def main():
    voice_core = VoiceCore(forward_queue=voice_forward_queue, ui_queue=ui_voice_queue)
    voice_core.start()
    async_loop = asyncio.new_event_loop()

    def schedule_cmd_token_real(token_str: str):
        if async_loop.is_running():
            asyncio.run_coroutine_threadsafe(async_command_queue.put(token_str), async_loop)

    vigia_manager = VigiaManager(schedule_cmd=schedule_cmd_token_real, model_path="yolov8n.pt", log_fn=log_interface)
    
    forwarder_thread = threading.Thread(target=voice_forwarder_thread, args=(async_loop, voice_forward_queue), daemon=True)
    forwarder_thread.start()
    
    app = AssistenteMestreGUI(async_loop, voice_core, vigia_manager)
    
    monitor = PCMonitor(
        log_fn=log_interface, 
        on_game_focused=app.show_happy_overlay,
        on_game_unfocused=app.hide_overlay
    )
    app.monitor = monitor
    monitor.start()
    
    def run_async_bot():
        asyncio.set_event_loop(async_loop)
        try:
            async_loop.create_task(bot_main(app))
            async_loop.run_forever()
        finally:
            tasks = [t for t in asyncio.all_tasks(loop=async_loop) if t is not asyncio.current_task()]
            if tasks:
                for task in tasks: task.cancel()
                async_loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            async_loop.close()

    bot_thread = threading.Thread(target=run_async_bot, daemon=True)
    bot_thread.start()

    try:
        keyboard.add_hotkey("ctrl+alt+v", lambda: voice_core.start_listening("desktop"))
        keyboard.add_hotkey("ctrl+alt+b", app.toggle_vigia)
    except Exception as e:
        log_interface(f"[SYSTEM] Não foi possível registrar hotkeys globais: {e}", "warning")

    app.mainloop()

    if monitor.is_running: 
        monitor.stop()
    if vigia_manager.is_running(): 
        vigia_manager.stop()

    voice_forward_queue.put(None)
    if forwarder_thread.is_alive():
        forwarder_thread.join(timeout=1)
    
    voice_core.stop()
    update_status("padrao", None)
    
    if bot_thread.is_alive():
        bot_thread.join(timeout=2)

if __name__ == "__main__":
    main()