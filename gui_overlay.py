# gui_overlay.py
import customtkinter as ctk
import itertools
from PIL import Image, ImageTk

class OverlayWindow(ctk.CTkToplevel):
    def __init__(self, master, gif_frames, close_callback):
        super().__init__(master)
        self.gif_frames = gif_frames
        self.close_callback = close_callback
        self.current_gif_name = None
        self.gif_iter = None
        self.gif_animating = False
        self._keep_top_job = None # Variável para controlar o loop "teimoso"

        self.overrideredirect(True)
        self.geometry("150x150+10+10")
        self.wm_attributes("-topmost", True)
        self.wm_attributes("-transparentcolor", "black")
        self.configure(fg_color="black")

        self.gif_label = ctk.CTkLabel(self, text="", bg_color="black")
        self.gif_label.pack(expand=True, fill="both")
        
        self.close_button = ctk.CTkButton(
            self, text="X", width=20, height=20, 
            fg_color="red", hover_color="#C00000", text_color="white",
            command=self.close_callback
        )
        self.close_button.place(x=125, y=5)

        self.withdraw()

    def _keep_on_top(self):
        """Função "teimosa" que reafirma que a janela deve ficar no topo."""
        if self.winfo_viewable(): # Se a janela estiver visível
            self.lift() # Traz a janela para frente
            self.wm_attributes("-topmost", True)
            self._keep_top_job = self.after(500, self._keep_on_top) # Repete a cada 500ms

    def set_estado_emocao(self, estado):
        if estado not in self.gif_frames or self.current_gif_name == estado:
            return
        
        self.current_gif_name = estado
        self.gif_iter = itertools.cycle(self.gif_frames[estado])
        
        self.show()
        
        if not self.gif_animating:
            self.animate_gif()

    def animate_gif(self):
        self.gif_animating = True
        if self.gif_iter:
            try:
                frame = next(self.gif_iter)
                self.gif_label.configure(image=frame)
                self.after(100, self.animate_gif)
            except Exception:
                self.gif_animating = False
        else:
            self.gif_animating = False

    def show(self):
        self.deiconify()
        # Inicia o loop para se manter no topo
        if self._keep_top_job is None:
            self._keep_on_top()

    def hide(self):
        # Para o loop de se manter no topo
        if self._keep_top_job is not None:
            self.after_cancel(self._keep_top_job)
            self._keep_top_job = None
        self.withdraw()