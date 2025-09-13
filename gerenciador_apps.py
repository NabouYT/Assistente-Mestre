import json
import os

ARQUIVO_JSON = 'apps.json'

def carregar_dados():
    """Carrega os dados do arquivo JSON."""
    if not os.path.exists(ARQUIVO_JSON):
        # Cria um arquivo padrão se ele não existir
        dados_padrao = {"apps_locais": {}, "sites_conhecidos": {}}
        salvar_dados(dados_padrao)
        return dados_padrao
    try:
        with open(ARQUIVO_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERRO ao carregar {ARQUIVO_JSON}: {e}. Usando dados vazios.")
        return {"apps_locais": {}, "sites_conhecidos": {}}

def salvar_dados(dados):
    """Salva os dados no arquivo JSON."""
    try:
        with open(ARQUIVO_JSON, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"ERRO CRÍTICO ao salvar {ARQUIVO_JSON}: {e}")
        raise e # Propaga o erro para ser tratado pela UI

def adicionar_app(nome, caminho, sinonimos=[]):
    """Adiciona um novo aplicativo ao JSON."""
    dados = carregar_dados()
    nome_app = nome.lower()
    
    if nome_app in dados["apps_locais"]:
        raise ValueError(f"O aplicativo '{nome_app}' já existe.")

    # Extrai o nome do executável do caminho
    executavel = os.path.basename(caminho)
    if caminho.endswith(".lnk"):
        # Se for um atalho, o executável real pode ser diferente, mas isso é um bom palpite
        executavel = os.path.splitext(executavel)[0] + ".exe"

    dados["apps_locais"][nome_app] = {
        "caminho": caminho,
        "executavel": executavel,
        "usa_hotkey": "testar", # Inicia em modo de teste
        "sinonimos": sinonimos
    }
    salvar_dados(dados)
    print(f"App '{nome_app}' adicionado com sucesso.")

def adicionar_sinonimo(nome_app, sinonimo):
    """Adiciona um novo sinônimo a um aplicativo existente."""
    dados = carregar_dados()
    if nome_app in dados["apps_locais"]:
        if "sinonimos" not in dados["apps_locais"][nome_app]:
            dados["apps_locais"][nome_app]["sinonimos"] = []
        
        if sinonimo.lower() not in dados["apps_locais"][nome_app]["sinonimos"]:
            dados["apps_locais"][nome_app]["sinonimos"].append(sinonimo.lower())
            salvar_dados(dados)
            print(f"Sinônimo '{sinonimo}' adicionado a '{nome_app}'.")
    else:
        raise KeyError(f"Aplicativo '{nome_app}' não encontrado.")

def atualizar_usa_hotkey(nome_app, usa_hotkey_status):
    """Atualiza o status de 'usa_hotkey' para um app."""
    dados = carregar_dados()
    if nome_app in dados["apps_locais"]:
        dados["apps_locais"][nome_app]["usa_hotkey"] = usa_hotkey_status
        salvar_dados(dados)
        print(f"Configuração de hotkey para '{nome_app}' atualizada para {usa_hotkey_status}.")
    else:
        raise KeyError(f"Aplicativo '{nome_app}' não encontrado.")
