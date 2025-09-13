# core_vigia.py
import threading
import time
from typing import Callable, Optional
import cv2

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None

class VigiaManager:
    """
    Vigia (YOLO + webcam) em thread separada.
    - schedule_cmd: callable(token: str) -> None
        usado para enviar comandos especiais ao loop assíncrono (ex.: "__VIGIA_PAUSE__", "__VIGIA_RESUME__")
    - model_path: caminho para o yolov8 .pt
    - min_no_person_frames: quantos frames consecutivos sem pessoa disparam PAUSE
    - min_person_frames: quantos frames consecutivos com pessoa disparam RESUME
    """
    TOKEN_PAUSE = "__VIGIA_PAUSE__"
    TOKEN_RESUME = "__VIGIA_RESUME__"

    def __init__(self,
                 schedule_cmd: Callable[[str], None],
                 model_path: str = "yolov8n.pt",
                 camera_index: int = 0,
                 min_no_person_frames: int = 12,
                 min_person_frames: int = 6,
                 log_fn: Optional[Callable[[str, str], None]] = None):
        self.schedule_cmd = schedule_cmd
        self.model_path = model_path
        self.camera_index = camera_index
        self.min_no_person_frames = min_no_person_frames
        self.min_person_frames = min_person_frames
        self.log_fn = log_fn or (lambda msg, tag="info": print(f"{tag.upper()}: {msg}"))

        self._thread = None
        self._stop_event = threading.Event()
        self._running = False

        self._cap = None
        self._model = None

    def _log(self, message: str, tag: str = "vigia"):
        try:
            self.log_fn(message, tag)
        except Exception:
            print(f"{tag}: {message}")

    def start(self):
        if self._running:
            self._log("Vigia já está a correr.", "warning")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="VigiaThread")
        self._thread.start()
        self._running = True
        self._log("Vigia iniciado.", "vigia")

    def stop(self):
        if not self._running:
            self._log("Vigia já parado.", "warning")
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._running = False
        self._release_resources()
        self._log("Vigia parado.", "vigia")

    def toggle(self):
        if self._running:
            self.stop()
        else:
            self.start()

    def is_running(self) -> bool:
        return self._running

    def _load_model(self):
        if YOLO is None:
            raise RuntimeError("ultralytics YOLO não disponível (instale ultralytics).")
        try:
            self._model = YOLO(self.model_path)
            self._log("Modelo YOLO carregado.", "vigia")
        except Exception as e:
            self._model = None
            self._log(f"Falha ao carregar modelo YOLO: {e}", "error")
            raise

    def _open_camera(self):
        try:
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)
        except Exception:
            cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Não foi possível abrir a câmera index={self.camera_index}")
        # configurações opcionais
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return cap

    def _release_resources(self):
        try:
            if self._cap and self._cap.isOpened():
                self._cap.release()
                self._cap = None
                self._log("Câmera libertada.", "vigia")
        except Exception:
            pass

    def _run(self):
        try:
            self._load_model()
        except Exception as e:
            self._log(f"Vigia abortado: {e}", "error")
            self._running = False
            return

        try:
            self._cap = self._open_camera()
        except Exception as e:
            self._log(f"Vigia abortado: {e}", "error")
            self._running = False
            return

        no_person_counter = 0
        person_counter = 0
        video_paused_by_vigia = False

        # loop principal
        while not self._stop_event.is_set():
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            # inferência (rápida): usa model(frame) -> results
            try:
                results = self._model(frame, verbose=False)
            except Exception as e:
                # Em caso de erro de inferência, apenas log e continue
                self._log(f"Erro de inferência YOLO: {e}", "error")
                time.sleep(0.15)
                continue

            # verificar se existe 'person' nas detecções
            person_detected = False
            try:
                for r in results:
                    # r.boxes.cls é array de classes. model.names mapping existe.
                    if hasattr(r, "boxes") and hasattr(r.boxes, "cls"):
                        for cls_idx in r.boxes.cls:
                            idx = int(cls_idx)
                            name = self._model.names.get(idx) if hasattr(self._model, "names") else None
                            if name and name.lower() == "person":
                                person_detected = True
                                break
                    if person_detected:
                        break
            except Exception:
                # se formato inesperado, considerar como não detectado
                person_detected = False

            if person_detected:
                person_counter += 1
                no_person_counter = 0
            else:
                no_person_counter += 1
                person_counter = 0

            # Debounce: se muitos frames seguidos sem pessoa => PAUSE
            if no_person_counter >= self.min_no_person_frames and not video_paused_by_vigia:
                # enviar token de pause
                try:
                    self.schedule_cmd(self.TOKEN_PAUSE)
                    video_paused_by_vigia = True
                    self._log("Nenhuma pessoa detectada — solicitada PAUSA.", "vigia")
                except Exception as e:
                    self._log(f"Erro ao agendar PAUSA do vigia: {e}", "error")

            # Debounce: se pessoa detectada por vários frames e vídeo estava pausado pelo vigia => RESUME
            if person_counter >= self.min_person_frames and video_paused_by_vigia:
                try:
                    self.schedule_cmd(self.TOKEN_RESUME)
                    video_paused_by_vigia = False
                    self._log("Pessoa detectada — solicitada RETOMADA.", "vigia")
                except Exception as e:
                    self._log(f"Erro ao agendar RESUME do vigia: {e}", "error")

            # sleeping leve para não saturar CPU
            time.sleep(0.05)

        # fim do loop
        self._release_resources()
        self._log("Loop do Vigia terminado.", "vigia")
        self._running = False
