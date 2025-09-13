# gui_learning_dialog.py
import customtkinter as ctk
from core_utils import carregar_config_apps

class LearningDialog(ctk.CTkToplevel):
    def __init__(self, master, unknown_word, callback):
        super().__init__(master)
        self.title("Aprender Novo Comando")
        self.callback = callback
        self.unknown_word = unknown_word
        self.selection = None

        self.geometry("500x400")
        self.transient(master)
        self.grab_set()

        self.label = ctk.CTkLabel(self, text=f"Não sei o que é '{unknown_word}'.\nA qual dos itens abaixo você se refere?", font=("Helvetica", 14))
        self.label.pack(pady=10)

        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.pack(pady=10, padx=10, fill="both", expand=True)

        config = carregar_config_apps()
        apps = config.get("apps_locais", {})
        
        for apelido in sorted(apps.keys()):
            btn = ctk.CTkButton(self.scrollable_frame, text=apelido, command=lambda ap=apelido: self.on_select(ap))
            btn.pack(pady=5, padx=10, fill="x")

        self.cancel_button = ctk.CTkButton(self, text="Cancelar", command=self.on_cancel)
        self.cancel_button.pack(pady=10)

    def on_select(self, apelido_selecionado):
        self.selection = apelido_selecionado
        self.grab_release()
        self.destroy()
        # Chama a função de callback com a palavra nova e o app selecionado
        self.callback(self.unknown_word, self.selection)

    def on_cancel(self):
        self.selection = None
        self.grab_release()
        self.destroy()