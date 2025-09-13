# core_web.py
from core_utils import log_interface
import asyncio

# Variável global para armazenar os links da última pesquisa
ultimos_resultados_pesquisa = []

async def pausar_video(page):
    """Pressiona a tecla 'k' para pausar/retomar vídeos (padrão YouTube)."""
    try:
        await page.keyboard.press("k")
        log_interface("[WEB] Comando de pausa/play enviado.", "web")
    except Exception as e:
        log_interface(f"[WEB] Erro ao enviar comando de play/pause: {e}", "error")

async def retomar_video(page):
    """Pressiona a tecla 'k' para pausar/retomar vídeos."""
    try:
        await page.keyboard.press("k")
        log_interface("[WEB] Comando de play/retomar enviado.", "web")
    except Exception as e:
        log_interface(f"[WEB] Erro ao enviar comando de play/resume: {e}", "error")

async def pesquisar_youtube(termo: str, page):
    global ultimos_resultados_pesquisa
    ultimos_resultados_pesquisa.clear()
    try:
        log_interface(f"[WEB] Pesquisando no YouTube por: '{termo}'", "web")
        termo_formatado = termo.replace(' ', '+')
        url_pesquisa = f"https://www.youtube.com/results?search_query={termo_formatado}"
        await page.goto(url_pesquisa, timeout=60000)

        await page.wait_for_selector('ytd-video-renderer', timeout=10000)
        videos = await page.locator('ytd-video-renderer').all()

        log_interface("--- Resultados da Pesquisa no YouTube ---", "success")
        for i, video in enumerate(videos[:5]):
            titulo = await video.locator('#video-title').inner_text()
            link = await video.locator('a#video-title').get_attribute('href')
            url_completa = f"https://www.youtube.com{link}"
            
            ultimos_resultados_pesquisa.append({"tipo": "yt", "url": url_completa})
            log_interface(f"{i + 1}: {titulo}", "info")
        
        log_interface("Para tocar um vídeo, digite apenas o número.", "info")

    except Exception as e:
        log_interface(f"[WEB] Erro ao pesquisar no YouTube ou extrair resultados: {e}", "error")

async def pesquisar_google(termo: str, page):
    global ultimos_resultados_pesquisa
    ultimos_resultados_pesquisa.clear()
    try:
        log_interface(f"[WEB] Pesquisando no Google por: '{termo}'", "web")
        url_pesquisa = f"https://www.google.com/search?q={termo.replace(' ', '+')}&hl=pt-BR"
        await page.goto(url_pesquisa, timeout=60000)
        
        await page.wait_for_selector('div.g', timeout=10000)
        resultados = await page.locator('div.g').all()
        
        log_interface("--- Resultados da Pesquisa na Web ---", "success")
        for i, res in enumerate(resultados[:5]):
            try:
                titulo_element = await res.locator('h3').first
                link_element = await res.locator('a').first
                titulo = await titulo_element.inner_text()
                link = await link_element.get_attribute('href')
                if titulo and link:
                    ultimos_resultados_pesquisa.append({"tipo": "web", "url": link})
                    log_interface(f"{i + 1}: {titulo}", "info")
            except Exception:
                continue
        
        log_interface("Para abrir um link, digite apenas o número.", "info")

    except Exception as e:
        log_interface(f"[WEB] Erro ao pesquisar no Google ou extrair resultados: {e}", "error")

async def tocar_video_youtube(numero: int, page):
    global ultimos_resultados_pesquisa
    try:
        index = numero - 1
        if 0 <= index < len(ultimos_resultados_pesquisa) and ultimos_resultados_pesquisa[index]["tipo"] == "yt":
            resultado = ultimos_resultados_pesquisa[index]
            log_interface(f"[WEB] Tocando vídeo {numero}...", "web")
            await page.goto(resultado["url"], timeout=60000)
            
            await asyncio.sleep(2)
            await page.keyboard.press("k")
            
            ultimos_resultados_pesquisa.clear()
            return True
    except Exception as e:
        log_interface(f"[WEB] Erro ao tentar tocar o vídeo {numero}: {e}", "error")
    
    log_interface(f"[WEB] Número de vídeo {numero} inválido ou não encontrado.", "warning")
    return False

async def abrir_link_web(numero: int, page):
    global ultimos_resultados_pesquisa
    try:
        index = numero - 1
        if 0 <= index < len(ultimos_resultados_pesquisa) and ultimos_resultados_pesquisa[index]["tipo"] == "web":
            resultado = ultimos_resultados_pesquisa[index]
            log_interface(f"[WEB] Abrindo link {numero}...", "web")
            await page.goto(resultado["url"], timeout=60000)
            ultimos_resultados_pesquisa.clear()
            return True
    except Exception as e:
        log_interface(f"[WEB] Erro ao tentar abrir o link {numero}: {e}", "error")

    log_interface(f"[WEB] Número de link {numero} inválido ou não encontrado.", "warning")
    return False