# core_utils.py
import json
import os
import queue
from typing import Any, Dict
from pathlib import Path

CONFIG_DIR = Path(__file__).parent
APPS_JSON = CONFIG_DIR / 'apps.json'
STATUS_JSON = CONFIG_DIR / 'status.json'
COMANDO_JSON = CONFIG_DIR / 'comando.json'
CONFIG_JSON = CONFIG_DIR / 'config.json'
log_queue: "queue.Queue[dict]" = queue.Queue()

def log_interface(message: str, tag: str="info"):
    try:
        log_queue.put({"message": message, "tag": tag})
    except Exception:
        print(f"{tag.upper()}: {message}")

def read_json_file(path: Path, default: Any):
    if not path.exists():
        write_json_file(path, default)
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content: return default
            return json.loads(content)
    except Exception as e:
        log_interface(f"[UTILS] Erro ao ler {path.name}: {e}", "error")
        return default

def write_json_file(path: Path, data: Any):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_interface(f"[UTILS] Erro ao gravar {path.name}: {e}", "error")

def expandir_caminho(caminho_str: str) -> Path:
    return Path(os.path.expandvars(caminho_str))

def carregar_config_apps() -> Dict:
    return read_json_file(APPS_JSON, {"_comment": "...", "apps_locais": {}, "sites_conhecidos": {}})

def carregar_config_geral() -> Dict:
    return read_json_file(CONFIG_JSON, {"confirmar_comando_voz": True})

def carregar_status() -> Dict:
    return read_json_file(STATUS_JSON, {"estado": "padrao", "processo_ativo": None})

def update_status(estado: str = "padrao", processo_ativo: str = None):
    write_json_file(STATUS_JSON, {"estado": estado, "processo_ativo": processo_ativo})

def adicionar_sinonimo(apelido_app: str, novo_sinonimo: str):
    """Adiciona um novo sinônimo a um app existente no apps.json."""
    if not apelido_app or not novo_sinonimo:
        return
        
    config = carregar_config_apps()
    
    if apelido_app in config["apps_locais"]:
        if "sinonimos" not in config["apps_locais"][apelido_app]:
            config["apps_locais"][apelido_app]["sinonimos"] = []
        
        if novo_sinonimo.lower() not in config["apps_locais"][apelido_app]["sinonimos"]:
            config["apps_locais"][apelido_app]["sinonimos"].append(novo_sinonimo.lower())
            write_json_file(APPS_JSON, config)
            log_interface(f"Aprendi que '{novo_sinonimo}' é um apelido para '{apelido_app}'!", "success")
        else:
            log_interface(f"Eu já sabia que '{novo_sinonimo}' era um apelido para '{apelido_app}'.", "info")
    else:
        log_interface(f"Erro de aprendizado: não encontrei o app '{apelido_app}' para adicionar o sinônimo.", "error")