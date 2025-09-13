# core_desktop.py
import subprocess
import webbrowser
import os
import string
import time
from pathlib import Path

from thefuzz import fuzz
import pygetwindow as gw
import keyboard
import pyautogui

from core_utils import log_interface, carregar_config_apps, expandir_caminho

def abrir_app_desktop(nome_app: str):
    dados = carregar_config_apps()
    app_info = dados.get("apps_locais", {}).get(nome_app.lower())
    
    if not app_info or not app_info.get("caminho"):
        log_interface(f"[DESKTOP] App '{nome_app}' ou seu caminho não encontrado.", "warning")
        return
    
    caminho_path = expandir_caminho(app_info["caminho"])

    if not caminho_path.exists():
        log_interface(f"[DESKTOP] Caminho para '{nome_app}' não existe: {caminho_path}", "error")
        return
        
    try:
        if os.name == 'nt':
            os.startfile(caminho_path)
        else:
            subprocess.Popen([str(caminho_path)])
        log_interface(f"[DESKTOP] Abrindo launcher de: {nome_app}", "desktop")

        if "launcher_steps" in app_info:
            log_interface(f"[DESKTOP] Executando automação de launcher para {nome_app}...", "info")
            for step in app_info["launcher_steps"]:
                
                action_name = step.get("action")

                if action_name == "wait_for_button_state_change":
                    timeout = step.get("delay", 120)
                    image_ready_file = step.get("image_ready")
                    image_gray_file = step.get("image_gray")
                    
                    if not os.path.exists(image_ready_file) or not os.path.exists(image_gray_file):
                        log_interface(f"[DESKTOP] ERRO: Imagem para automação não encontrada. Verifique '{image_ready_file}' e '{image_gray_file}'.", "error")
                        return

                    confidence_level = 0.95
                    log_interface(f"[DESKTOP] Aguardando o botão ficar ativo por até {timeout}s...", "info")
                    
                    start_time = time.time()
                    clicked = False
                    
                    while time.time() - start_time < timeout:
                        try:
                            ready_location = pyautogui.locateCenterOnScreen(image_ready_file, confidence=confidence_level)
                            if ready_location:
                                log_interface("[DESKTOP] Botão 'Start' está pronto! Clicando...", "success")
                                pyautogui.click(ready_location)
                                clicked = True
                                break

                            gray_location = pyautogui.locateCenterOnScreen(image_gray_file, confidence=confidence_level)
                            if gray_location:
                                log_interface("[DESKTOP] Launcher ainda está carregando (botão cinza visível)...", "info")
                        
                        except pyautogui.PyAutoGUIException:
                            pass
                        except Exception as e:
                            log_interface(f"[DESKTOP] Erro inesperado na busca de imagem: {e}", "warning")
                            
                        time.sleep(2)

                    if not clicked:
                        log_interface(f"[DESKTOP] ERRO: O botão 'Start' não ficou ativo após {timeout}s.", "error")
                
                elif action_name == "click_on_image":
                    image_to_click = step.get("image_to_click")
                    timeout = step.get("delay", 60)
                    confidence = step.get("confidence", 0.95)
                    
                    if not os.path.exists(image_to_click):
                        log_interface(f"[DESKTOP] ERRO: Imagem para automação não encontrada. Verifique '{image_to_click}'.", "error")
                        return
                    
                    start_time = time.time()
                    clicked = False
                    
                    log_interface(f"[DESKTOP] Tentando clicar na imagem '{image_to_click}'...", "info")
                    
                    while time.time() - start_time < timeout:
                        try:
                            location = pyautogui.locateCenterOnScreen(image_to_click, confidence=confidence)
                            if location:
                                # **Nova lógica para mover e clicar**
                                log_interface(f"[DESKTOP] Imagem '{image_to_click}' encontrada. Movendo o mouse e clicando...", "info")
                                pyautogui.moveTo(location)
                                pyautogui.click()
                                log_interface(f"[DESKTOP] Clique executado.", "success")
                                clicked = True
                                break
                        except pyautogui.PyAutoGUIException:
                            pass
                        
                        time.sleep(1)

                    if not clicked:
                        log_interface(f"[DESKTOP] ERRO: Não foi possível clicar no botão '{image_to_click}' após {timeout}s.", "error")

                else:
                    action_found = step.get("action", "Nenhuma")
                    log_interface(f"[DESKTOP] ERRO: Ação de launcher '{action_found}' no apps.json não é reconhecida.", "error")

    except Exception as e:
        log_interface(f"[DESKTOP] Erro ao abrir app '{nome_app}': {e}", "error")

def fechar_app(nome_app: str):
    dados = carregar_config_apps()
    app_info = dados.get("apps_locais", {}).get(nome_app.lower())
    
    if not app_info:
        log_interface(f"[DESKTOP] Não encontrei informações para fechar '{nome_app}'.", "error")
        return

    try:
        game_windows = gw.getWindowsWithTitle(nome_app)
        if not game_windows:
            log_interface(f"[DESKTOP] Não encontrei uma janela aberta para '{nome_app}'. Tentando fechar pelo executável...", "warning")
            executavel = app_info.get("executavel")
            if executavel:
                subprocess.run(["taskkill", "/F", "/IM", executavel], check=True, capture_output=True)
                log_interface(f"[DESKTOP] Processo '{executavel}' fechado com sucesso.", "desktop")
            return

        window_to_close = game_windows[0]
        window_to_close.activate()
        keyboard.press_and_release('alt+f4')
        log_interface(f"[DESKTOP] Comando para fechar '{nome_app}' enviado.", "desktop")

    except Exception as e:
        log_interface(f"[DESKTOP] Não foi possível fechar '{nome_app}': {e}", "error")

def abrir_site_known(nome_site: str):
    dados = carregar_config_apps()
    url = dados.get("sites_conhecidos", {}).get(nome_site.lower())
    if not url:
        log_interface(f"[DESKTOP] Site '{nome_site}' não encontrado.", "warning")
        return
    try:
        webbrowser.open(url)
        log_interface(f"[DESKTOP] Abrindo site: {url}", "desktop")
    except Exception as e:
        log_interface(f"[DESKTOP] Erro ao abrir site '{nome_site}': {e}", "error")

def extrair_palavra_chave(comando: str) -> str:
    comando_limpo = comando.translate(str.maketrans('', '', string.punctuation))
    palavras = comando_limpo.lower().split()
    palavras_ignoradas = [
        "abrir", "abra", "iniciar", "inicia", "executar", "execute", "jogar", "joga", "rodar", "rode",
        "fechar", "fecha", "encerrar", "encerra", "terminar", "termina", "matar", "mata",
        "app", "aplicativo", "programa", "jogo", "site", "favor", "por favor", "pode",
        "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "no", "na"
    ]
    palavras_chave = [p for p in palavras if p not in palavras_ignoradas]
    return " ".join(palavras_chave) if palavras_chave else ""

def interpretar_comando_desktop(comando: str):
    comando_lower = comando.lower()
    dados = carregar_config_apps()
    palavras_abrir = ["abrir", "iniciar", "executar", "jogar", "rodar", "abra", "inicia", "execute", "joga", "rode"]
    palavras_fechar = ["fechar", "encerrar", "terminar", "matar", "fecha", "encerra", "termina", "mata"]

    termo_alvo = extrair_palavra_chave(comando)
    if not termo_alvo:
        return None

    best_match_score = 0
    best_match_app = None
    best_match_type = None

    for apelido, detalhes in dados.get("apps_locais", {}).items():
        nomes_possiveis = [apelido] + detalhes.get("sinonimos", [])
        for nome in nomes_possiveis:
            score = fuzz.token_set_ratio(termo_alvo, nome)
            if score > best_match_score:
                best_match_score = score
                best_match_app = apelido
                best_match_type = "app"

    if any(palavra in comando_lower for palavra in palavras_abrir):
        for apelido in dados.get("sites_conhecidos", {}).keys():
            score = fuzz.token_set_ratio(termo_alvo, apelido)
            if score > best_match_score:
                best_match_score = score
                best_match_app = apelido
                best_match_type = "site"

    if best_match_score > 75:
        if any(palavra in comando_lower for palavra in palavras_fechar) and best_match_type == "app":
            return {"funcao": "fechar_app", "parametros": {"nome": best_match_app}}
        
        if any(palavra in comando_lower for palavra in palavras_abrir):
            if best_match_type == "app":
                return {"funcao": "abrir_app", "parametros": {"nome": best_match_app}}
            elif best_match_type == "site":
                return {"funcao": "abrir_site", "parametros": {"nome": best_match_app}}
    
    return None