# core_monitor.py
import threading
import time
from typing import Callable
from core_utils import carregar_config_apps

try:
    import psutil
except ImportError:
    psutil = None

class PCMonitor:
    def __init__(self, log_fn: Callable, on_game_focused: Callable, on_game_unfocused: Callable):
        if not psutil:
            self.is_available = False
            return
        
        self.log_fn = log_fn
        self.on_game_focused = on_game_focused
        self.on_game_unfocused = on_game_unfocused
        
        self._thread = None
        self._stop_event = threading.Event()
        self.is_running = False
        self.game_is_active = False
        self.active_game_name = None
        self.is_available = True
        
        # <<< NOVA LÓGICA DE "PACIÊNCIA" >>>
        self.in_grace_period = False
        self.time_game_disappeared = 0
        self.GRACE_PERIOD_SECONDS = 10 # Vai esperar 10 segundos antes de esconder o overlay

        config = carregar_config_apps()
        self.game_executables = {details.get("executavel", "").lower(): apelido
                                 for apelido, details in config.get("apps_locais", {}).items() 
                                 if details.get("executavel")}

    def start(self):
        if not self.is_available or self.is_running: return
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="PCMonitorThread")
        self._thread.start()
        self.log_fn("Módulo de Monitoramento iniciado.", "info")

    def stop(self):
        if not self.is_available or not self.is_running: return
        self._stop_event.set()
        if self._thread: self._thread.join(timeout=2.0)
        self.is_running = False
        self.log_fn("Módulo de Monitoramento parado.", "info")

    def _run(self):
        while not self._stop_event.is_set():
            try:
                running_processes = {p.name().lower() for p in psutil.process_iter(['name'])}
                
                game_found = False
                found_game_name = None

                for game_exe, apelido in self.game_executables.items():
                    if game_exe in running_processes:
                        game_found = True
                        found_game_name = apelido
                        break

                # --- LÓGICA DE PACIÊNCIA IMPLEMENTADA ---
                if game_found:
                    # Se um jogo foi encontrado, cancela qualquer período de espera
                    self.in_grace_period = False
                    
                    if not self.game_is_active:
                        self.log_fn(f"[MONITOR] Jogo '{found_game_name}' detectado! Mostrando overlay.", "desktop")
                        self.active_game_name = found_game_name
                        self.on_game_focused()
                        self.game_is_active = True
                else: # Nenhum jogo foi encontrado
                    if self.game_is_active and not self.in_grace_period:
                        # O jogo acabou de desaparecer. Inicia o período de tolerância.
                        self.log_fn("[MONITOR] Jogo desapareceu. Iniciando período de tolerância de 10s...", "warning")
                        self.in_grace_period = True
                        self.time_game_disappeared = time.time()
                    
                    elif self.in_grace_period:
                        # Se já estamos no período de tolerância, verifica se o tempo esgotou
                        if time.time() - self.time_game_disappeared > self.GRACE_PERIOD_SECONDS:
                            self.log_fn("[MONITOR] Período de tolerância esgotado. Jogo realmente fechado. Escondendo overlay.", "desktop")
                            self.active_game_name = None
                            self.on_game_unfocused()
                            self.game_is_active = False
                            self.in_grace_period = False

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
            except Exception as e:
                self.log_fn(f"[MONITOR] Erro inesperado: {e}", "error")

            time.sleep(2) # Verifica a cada 2 segundos