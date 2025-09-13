# gui_app_manager.py
import customtkinter as ctk
from tkinter import filedialog, messagebox
from core_utils import carregar_config_apps, log_interface, expandir_caminho
import core_utils # Importando o módulo para ter acesso às funções de salvar

class AppManagerWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Gerenciador de Apps e Sites")
        self.geometry("700x500")
        self.transient(master) # Mantém esta janela na frente da principal
        self.grab_set() # Foca a interação nesta janela

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Aplicativos e Sites Configurados")
        self.scrollable_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        self.add_app_button = ctk.CTkButton(self, text="Adicionar Novo App", command=self.open_add_app_dialog)
        self.add_app_button.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        self.close_button = ctk.CTkButton(self, text="Fechar", command=self.destroy)
        self.close_button.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.populate_app_list()

    def populate_app_list(self):
        # Limpa a lista atual antes de recarregar
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        config = carregar_config_apps()
        
        # Adiciona Apps Locais
        apps = config.get("apps_locais", {})
        row_counter = 0
        for apelido, detalhes in apps.items():
            app_frame = ctk.CTkFrame(self.scrollable_frame)
            app_frame.grid(row=row_counter, column=0, padx=5, pady=5, sticky="ew")
            app_frame.grid_columnconfigure(0, weight=1)

            label_apelido = ctk.CTkLabel(app_frame, text=f"{apelido}", font=ctk.CTkFont(weight="bold"))
            label_apelido.grid(row=0, column=0, padx=10, pady=2, sticky="w")

            caminho_str = detalhes.get('caminho', 'Caminho não definido')
            label_caminho = ctk.CTkLabel(app_frame, text=f"Caminho: {caminho_str}", text_color="gray")
            label_caminho.grid(row=1, column=0, padx=10, pady=2, sticky="w")
            
            delete_button = ctk.CTkButton(
                app_frame, text="Excluir", fg_color="red", hover_color="#C00000",
                command=lambda ap=apelido: self.delete_entry("app", ap)
            )
            delete_button.grid(row=0, rowspan=2, column=1, padx=10, pady=5)
            row_counter += 1

    def delete_entry(self, entry_type, apelido):
        if not messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir '{apelido}'?"):
            return

        config = carregar_config_apps()
        if entry_type == "app":
            if apelido in config["apps_locais"]:
                del config["apps_locais"][apelido]
                core_utils.write_json_file(core_utils.APPS_JSON, config)
                log_interface(f"[MANAGER] App '{apelido}' excluído com sucesso.", "success")
                self.populate_app_list() # Atualiza a lista na tela
            else:
                log_interface(f"[MANAGER] Erro: App '{apelido}' não encontrado para exclusão.", "error")

    def open_add_app_dialog(self):
        # Abre um novo Toplevel para adicionar um app
        dialog = AddAppDialog(self)
        self.wait_window(dialog) # Pausa a janela manager até o dialog ser fechado
        self.populate_app_list() # Atualiza a lista quando o dialog fechar


class AddAppDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Adicionar Novo Aplicativo")
        self.geometry("500x250")
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(1, weight=1)

        # Apelido
        ctk.CTkLabel(self, text="Apelido:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.apelido_entry = ctk.CTkEntry(self, placeholder_text="Ex: jogo do peixinho")
        self.apelido_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=10, sticky="ew")

        # Caminho
        ctk.CTkLabel(self, text="Caminho:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.caminho_entry = ctk.CTkEntry(self)
        self.caminho_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(self, text="Procurar...", command=self.browse_file).grid(row=1, column=2, padx=10, pady=10)

        # Executável
        ctk.CTkLabel(self, text="Executável:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.executavel_entry = ctk.CTkEntry(self, placeholder_text="Ex: jogo.exe")
        self.executavel_entry.grid(row=2, column=1, columnspan=2, padx=10, pady=10, sticky="ew")

        # Botões
        ctk.CTkButton(self, text="Salvar", command=self.save_app).grid(row=3, column=1, padx=10, pady=20)
        ctk.CTkButton(self, text="Cancelar", command=self.destroy).grid(row=3, column=2, padx=10, pady=20)

    def browse_file(self):
        filepath = filedialog.askopenfilename(
            title="Selecione o executável do aplicativo",
            filetypes=(("Executáveis", "*.exe"), ("Todos os arquivos", "*.*"))
        )
        if filepath:
            self.caminho_entry.delete(0, 'end')
            self.caminho_entry.insert(0, filepath)
            # Tenta preencher o nome do executável automaticamente
            executavel = expandir_caminho(filepath).name
            self.executavel_entry.delete(0, 'end')
            self.executavel_entry.insert(0, executavel)

    def save_app(self):
        apelido = self.apelido_entry.get().strip().lower()
        caminho = self.caminho_entry.get().strip()
        executavel = self.executavel_entry.get().strip()

        if not all([apelido, caminho, executavel]):
            messagebox.showerror("Erro", "Todos os campos devem ser preenchidos.")
            return

        config = carregar_config_apps()
        if apelido in config["apps_locais"]:
            messagebox.showerror("Erro", f"O apelido '{apelido}' já existe.")
            return

        config["apps_locais"][apelido] = {
            "caminho": caminho,
            "executavel": executavel
        }

        core_utils.write_json_file(core_utils.APPS_JSON, config)
        log_interface(f"[MANAGER] App '{apelido}' adicionado com sucesso!", "success")
        self.destroy()