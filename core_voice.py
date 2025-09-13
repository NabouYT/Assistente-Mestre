# core_voice.py
import threading
import queue
import time
import speech_recognition as sr
import pyttsx3

from core_utils import log_interface, carregar_config_geral


class VoiceManager:
    """
    Gerencia o reconhecimento de voz, a conversão de texto em fala e o fluxo de confirmação.
    """
    def __init__(self, command_queues: dict, ui_queue: queue.Queue):
        self.command_queues = command_queues
        self.ui_queue = ui_queue
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

        try:
            self.tts_engine = pyttsx3.init()
            voices = self.tts_engine.getProperty('voices')
            for voice in voices:
                if 'brazil' in voice.name.lower():
                    self.tts_engine.setProperty('voice', voice.id)
                    break
        except Exception as e:
            log_interface(f"Erro ao inicializar o motor de TTS: {e}", "error")
            self.tts_engine = None

        self.is_listening = False
        self.active_assistant = 'desktop'

        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)

    def speak(self, text):
        if self.tts_engine:
            try:
                self.ui_queue.put({"type": "log", "tag": "info", "message": f"Assistente: {text}"})
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception as e:
                log_interface(f"Erro durante a fala do TTS: {e}", "error")
        else:
            log_interface(f"Motor de TTS não disponível. Não foi possível falar: {text}", "voz")

    def start_listening_session(self, active_assistant: str):
        if self.is_listening:
            log_interface("Já estou a ouvir.", "voz")
            return

        self.active_assistant = active_assistant
        self.is_listening = True

        thread = threading.Thread(target=self._listening_flow, daemon=True)
        thread.start()

    def _listening_flow(self):
        """
        Executa o fluxo de escuta, com confirmação opcional baseada no config.json.
        """
        try:
            self.ui_queue.put({"type": "voice_status", "message": "Ouvindo..."})
            with self.microphone as source:
                try:
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                except sr.WaitTimeoutError:
                    self.ui_queue.put({"type": "voice_status", "message": "Não ouvi nada. Tente novamente."})
                    return

            self.ui_queue.put({"type": "voice_status", "message": "Processando..."})

            try:
                transcribed_text = self.recognizer.recognize_google(audio, language='pt-BR')
                self.ui_queue.put({"type": "voice_status", "message": f"Você disse: '{transcribed_text}'"})
            except sr.UnknownValueError:
                self.ui_queue.put({"type": "voice_status", "message": "Não entendi. Pode repetir?"})
                return
            except sr.RequestError as e:
                self.ui_queue.put({"type": "voice_status", "message": f"Erro de serviço; {e}"})
                return

            # Carrega a configuração para verificar se a confirmação é necessária
            config = carregar_config_geral()
            confirmacao_necessaria = config.get("confirmar_comando_voz", True)
            confirmado = False

            if confirmacao_necessaria:
                time.sleep(0.5)
                self.speak(f"Você disse: '{transcribed_text}'. Está correto?")
                self.ui_queue.put({"type": "voice_status", "message": "Aguardando confirmação (diga 'sim')..."})

                with self.microphone as source:
                    try:
                        audio_confirm = self.recognizer.listen(source, timeout=5, phrase_time_limit=3)
                        confirm_text = self.recognizer.recognize_google(audio_confirm, language='pt-BR').lower()
                        confirmation_words = ["ok", "sim", "correto", "isso", "confirmo", "exato"]
                        if any(word in confirm_text for word in confirmation_words):
                            confirmado = True
                    except (sr.WaitTimeoutError, sr.UnknownValueError):
                        self.ui_queue.put({"type": "voice_status", "message": "Confirmação não recebida. Comando cancelado."})
                        return
            else:
                # Se a confirmação não for necessária, assume como confirmado.
                confirmado = True

            if confirmado:
                self.ui_queue.put({"type": "voice_status", "message": f"Comando '{transcribed_text}' confirmado!"})
                if self.active_assistant in self.command_queues:
                    self.command_queues[self.active_assistant].put(transcribed_text)
                else:
                    log_interface(f"ERRO: Fila de comando para '{self.active_assistant}' não encontrada.", "error")
            else:
                self.ui_queue.put({"type": "voice_status", "message": "Comando cancelado."})

        finally:
            self.is_listening = False


class VoiceCore:
    def __init__(self, forward_queue: "queue.Queue", ui_queue: "queue.Queue"):
        self.forward_queue = forward_queue
        self.ui_queue = ui_queue
        self.manager = VoiceManager(command_queues={}, ui_queue=self.ui_queue)
        self.manager.command_queues["desktop"] = self.forward_queue
        self.manager.command_queues["web"] = self.forward_queue
        self.running = False

    def start(self):
        if self.running:
            return
        self.running = True
        log_interface("[VOZ] VoiceCore iniciado.", "voz")

    def stop(self):
        self.running = False
        log_interface("[VOZ] VoiceCore parado.", "voz")

    def start_listening(self, assistant="desktop"):
        if not self.running:
            log_interface("[VOZ] VoiceCore não está ativo.", "voz")
            return
        self.manager.start_listening_session(active_assistant=assistant)