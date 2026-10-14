# SCRIPT AIRNAVX



import os

import json

import re

import glob

import time

import shutil

import traceback

from datetime import datetime as dt

from getpass import getpass



import pandas as pd













from pathlib import Path
from google.oauth2 import service_account

import gspread



from googleapiclient.discovery import build

from googleapiclient.http import MediaFileUpload

from gspread.utils import rowcol_to_a1



from selenium import webdriver

from selenium.webdriver.common.by import By

from selenium.webdriver.common.keys import Keys

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import TimeoutException

from platform_utils import find_chrome





# ==========================================================

# LOGS BONITOS

# ==========================================================



class C:

    RESET = "\033[0m"

    BOLD = "\033[1m"

    DIM = "\033[2m"

    RED = "\033[31m"

    GREEN = "\033[32m"

    YELLOW = "\033[33m"

    BLUE = "\033[34m"

    MAGENTA = "\033[35m"

    CYAN = "\033[36m"

    WHITE = "\033[37m"



def _ts():

    return dt.now().strftime("%H:%M:%S")



def log(msg, color=C.WHITE, prefix="INFO"):

    print(f"{C.DIM}[{_ts()}]{C.RESET} {color}{C.BOLD}[{prefix}]{C.RESET} {msg}", flush=True)



def info(msg): log(msg, C.CYAN, "INFO")

def ok(msg):   log(msg, C.GREEN, "OK")

def warn(msg): log(msg, C.YELLOW, "WARN")

def err(msg):  log(msg, C.RED, "ERRO")

def step(msg): log(msg, C.MAGENTA, "STEP")



def head(msg):

    print(f"\n{C.BOLD}{C.BLUE}=== {msg} ==={C.RESET}\n", flush=True)



def err_curto(exc, contexto=""):

    nome = type(exc).__name__

    msg = str(exc).strip()

    if contexto:

        err(f"{contexto}: {nome} - {msg}")

    else:

        err(f"{nome} - {msg}")


def clear_output(wait=False):
    """Compatibilidade com a célula Colab; a GUI preserva todo o log."""
    return None





# ==========================================================

# CONFIGURAÇÕES GERAIS

# ==========================================================



BASE_DIR = Path(__file__).resolve().parent

NOME_PLANILHA = os.environ.get("AERODOC_AIRBUS_SHEET_NAME", "MASTER DATA - ABERTURA TICKET")



# Recomendado preencher com o ID da planilha

# Exemplo:

# https://docs.google.com/spreadsheets/d/ID_DA_PLANILHA/edit

SPREADSHEET_ID = os.environ.get("AERODOC_AIRBUS_SPREADSHEET_ID", "")



PASTA_DRIVE_PDFS_ID = os.environ.get("AERODOC_DRIVE_FOLDER_ID", "1-kqCphZI0IrmNtmAuGecmJvZXt7WuPVU")

PORTAL_AIRBUS_URL = "https://w3.airbus.com/1T40/search/text"



PASTA_TEMP_LOCAL = os.environ.get("AERODOC_DOWNLOAD_DIR", str(BASE_DIR / "downloads"))

os.makedirs(PASTA_TEMP_LOCAL, exist_ok=True)



TIMEOUT_2FA_SEGUNDOS = 240

TIMEOUT_DOWNLOAD_SEGUNDOS = 70



ABAS_VALIDAS = ["Airbus", "Boeing", "Embraer", "Geral"]



# Se True, imprime traceback completo no terminal

VERBOSE_ERROS = False
LOCAL_ONLY = os.environ.get("AERODOC_LOCAL_ONLY", "false").lower() == "true"





# ==========================================================

# AUTENTICAÇÃO GOOGLE SHEETS / DRIVE

# ==========================================================



SCOPES = [

    "https://www.googleapis.com/auth/spreadsheets",

    "https://www.googleapis.com/auth/drive",

]



GOOGLE_CREDENTIALS = Path(os.environ.get("AERODOC_GOOGLE_CREDENTIALS", str(BASE_DIR / "credentials.json")))
gc = None
drive_service = None
if not LOCAL_ONLY:
    if not GOOGLE_CREDENTIALS.exists():
        raise FileNotFoundError(f"Arquivo de credenciais Google não encontrado: {GOOGLE_CREDENTIALS}")
    creds = service_account.Credentials.from_service_account_file(str(GOOGLE_CREDENTIALS), scopes=SCOPES)
    gc = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds)





# ==========================================================

# FUNÇÕES GOOGLE SHEETS

# ==========================================================



def abrir_planilha():

    if SPREADSHEET_ID.strip():

        return gc.open_by_key(SPREADSHEET_ID.strip())

    return gc.open(NOME_PLANILHA)





def escolher_aba(spreadsheet):

    abas_existentes = [ws.title for ws in spreadsheet.worksheets()]

    opcoes = [aba for aba in ABAS_VALIDAS if aba in abas_existentes]



    head("ABAS DISPONÍVEIS")

    for idx, aba in enumerate(opcoes, start=1):

        print(f"{idx} - {aba}")



    if not opcoes:

        raise RuntimeError("Nenhuma das abas esperadas foi encontrada na planilha.")



    while True:

        escolha = os.environ.get("AERODOC_AIRBUS_SHEET_TAB") or input("\nDigite o número ou nome da aba que deseja rodar: ").strip()



        if escolha.isdigit():

            idx = int(escolha)

            if 1 <= idx <= len(opcoes):

                return opcoes[idx - 1]



        for aba in opcoes:

            if escolha.lower() == aba.lower():

                return aba



        warn("Opção inválida. Tente novamente.")





def normalizar_texto(txt):

    return re.sub(r"\s+", " ", str(txt).strip()).upper()





def encontrar_coluna(headers, candidatos):

    mapa = {normalizar_texto(h): h for h in headers}

    candidatos_norm = [normalizar_texto(c) for c in candidatos]



    for cand in candidatos_norm:

        if cand in mapa:

            return mapa[cand]



    for cand in candidatos_norm:

        for h_norm, h_origem in mapa.items():

            if cand in h_norm:

                return h_origem



    return None





def garantir_colunas(ws):

    headers = [h.strip() for h in ws.row_values(1)]

    obrigatorias = ["STATUS", "DETALHE_STATUS", "LINK_PDF"]



    alterou = False

    for col in obrigatorias:

        if col not in headers:

            headers.append(col)

            alterou = True



    if alterou:

        last_cell = rowcol_to_a1(1, len(headers))

        ws.update(range_name=f"A1:{last_cell}", values=[headers])

        ok("Colunas STATUS / DETALHE_STATUS / LINK_PDF garantidas na planilha.")



    return {h: i + 1 for i, h in enumerate(headers)}





def carregar_dataframe_da_aba(ws):

    valores = ws.get_all_values()

    if not valores:

        raise RuntimeError(f"A aba {ws.title} está vazia.")



    headers = [h.strip() for h in valores[0]]



    linhas = []

    for row_number, row in enumerate(valores[1:], start=2):

        row = row + [""] * (len(headers) - len(row))

        row = row[:len(headers)]



        registro = {headers[i]: row[i] for i in range(len(headers))}

        registro["_row_number"] = row_number

        linhas.append(registro)



    return pd.DataFrame(linhas)





def atualizar_linhas_planilha(ws, row_numbers, status, detalhe_status="", link_pdf=""):

    colunas = garantir_colunas(ws)



    col_status = colunas["STATUS"]

    col_detalhe = colunas["DETALHE_STATUS"]

    col_link = colunas["LINK_PDF"]



    updates = []

    for row_number in row_numbers:

        updates.append({

            "range": rowcol_to_a1(row_number, col_status),

            "values": [[status]],

        })

        updates.append({

            "range": rowcol_to_a1(row_number, col_detalhe),

            "values": [[detalhe_status]],

        })

        updates.append({

            "range": rowcol_to_a1(row_number, col_link),

            "values": [[link_pdf]],

        })



    if updates:

        ws.batch_update(updates)





# ==========================================================

# RESUMO FINAL

# ==========================================================



def criar_resumo_inicial(total_linhas, total_pns):

    return {

        "total_linhas_elegiveis": total_linhas,

        "total_pns_unicos": total_pns,

        "sucesso": 0,

        "erro": 0,

        "novo_drive": 0,

        "substituido_drive": 0,

        "inicio": time.time(),

    }





def imprimir_resumo_final(resumo):

    tempo_total = time.time() - resumo["inicio"]

    minutos = int(tempo_total // 60)

    segundos = int(tempo_total % 60)



    head("RESUMO FINAL")

    ok(f"Linhas elegíveis processadas: {resumo['total_linhas_elegiveis']}")

    ok(f"Part Numbers únicos processados: {resumo['total_pns_unicos']}")

    ok(f"Sucessos: {resumo['sucesso']}")

    warn(f"Erros: {resumo['erro']}")

    info(f"PDFs novos no Drive: {resumo['novo_drive']}")

    info(f"PDFs substituídos no Drive: {resumo['substituido_drive']}")

    info(f"Tempo total: {minutos}m {segundos}s")





# ==========================================================

# FUNÇÕES GOOGLE DRIVE

# ==========================================================



def escapar_query_drive(texto):

    return str(texto).replace("\\", "\\\\").replace("'", "\\'")





def buscar_pdf_no_drive(nome_pdf):

    nome_pdf_escapado = escapar_query_drive(nome_pdf)



    query = (

        f"name = '{nome_pdf_escapado}' "

        f"and '{PASTA_DRIVE_PDFS_ID}' in parents "

        f"and trashed = false"

    )



    resposta = drive_service.files().list(

        q=query,

        spaces="drive",

        fields="files(id, name, webViewLink, webContentLink, modifiedTime)",

        orderBy="modifiedTime desc",

        pageSize=20,

        supportsAllDrives=True,

        includeItemsFromAllDrives=True,

    ).execute()



    return resposta.get("files", [])





def upload_ou_substituir_pdf(local_pdf_path, nome_pdf):

    existentes = buscar_pdf_no_drive(nome_pdf)



    media = MediaFileUpload(

        local_pdf_path,

        mimetype="application/pdf",

        resumable=True,

    )



    fields = "id, name, webViewLink, webContentLink, modifiedTime"



    if existentes:

        arquivo_alvo = existentes[0]



        atualizado = drive_service.files().update(

            fileId=arquivo_alvo["id"],

            media_body=media,

            fields=fields,

            supportsAllDrives=True,

        ).execute()



        link = atualizado.get("webViewLink") or f"https://drive.google.com/file/d/{atualizado['id']}/view"



        mensagem = "PDF substituído no Drive."

        if len(existentes) > 1:

            mensagem += f" Atenção: existem {len(existentes)} arquivos com o mesmo nome; atualizei o mais recente."



        return {

            "acao": "substituido",

            "file_id": atualizado["id"],

            "link": link,

            "mensagem": mensagem,

        }



    metadata = {

        "name": nome_pdf,

        "parents": [PASTA_DRIVE_PDFS_ID],

    }



    criado = drive_service.files().create(

        body=metadata,

        media_body=media,

        fields=fields,

        supportsAllDrives=True,

    ).execute()



    link = criado.get("webViewLink") or f"https://drive.google.com/file/d/{criado['id']}/view"



    return {

        "acao": "novo",

        "file_id": criado["id"],

        "link": link,

        "mensagem": "PDF novo anexado no Drive.",

    }





# ==========================================================

# FUNÇÕES SELENIUM / COLAB / PINGID

# ==========================================================



def caminho_chromium():
    return find_chrome()

    candidatos = [

        "/usr/bin/google-chrome",

        "/usr/bin/google-chrome-stable",

        "/usr/bin/chromium-browser",

        "/usr/bin/chromium",

    ]



    for caminho in candidatos:

        if os.path.exists(caminho):

            return caminho



    return shutil.which("google-chrome") or shutil.which("chromium-browser") or shutil.which("chromium")





def criar_driver_local(pasta_download):

    options = webdriver.ChromeOptions()



    binario = caminho_chromium()

    if binario:

        options.binary_location = binario




    options.add_argument("--window-size=1366,900")

    options.add_argument("--no-sandbox")

    options.add_argument("--disable-dev-shm-usage")

    options.add_argument("--disable-gpu")


    options.add_argument("--disable-extensions")
    options.page_load_strategy = "eager"
    if os.environ.get("AERODOC_HEADLESS", "false").lower() == "true":
        options.add_argument("--headless=new")




    user_data_dir = str(BASE_DIR / ".chrome-profile")

    if os.path.exists(user_data_dir):

        shutil.rmtree(user_data_dir, ignore_errors=True)

    options.add_argument(f"--user-data-dir={user_data_dir}")



    prefs = {

        "download.default_directory": pasta_download,

        "download.prompt_for_download": False,

        "download.directory_upgrade": True,

        "plugins.always_open_pdf_externally": True,

        "profile.default_content_settings.popups": 0,

        "safebrowsing.enabled": True,

    }

    options.add_experimental_option("prefs", prefs)



    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(20)



    # As preferências acima já autorizam o download. Em algumas versões do
    # Chrome no macOS, este comando CDP trava o renderer antes da navegação.



    return driver





def coletar_texto_pagina_e_iframes(driver, max_depth=3):

    textos = []



    def walk(depth):

        try:

            texto = driver.execute_script("return document.body ? document.body.innerText : '';")

            if texto:

                textos.append(texto)

        except Exception:

            pass



        if depth >= max_depth:

            return



        try:

            frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")

        except Exception:

            frames = []



        for frame in frames:

            try:

                driver.switch_to.frame(frame)

                walk(depth + 1)

                driver.switch_to.parent_frame()

            except Exception:

                try:

                    driver.switch_to.parent_frame()

                except Exception:

                    pass



    try:

        driver.switch_to.default_content()

        walk(0)

    finally:

        try:

            driver.switch_to.default_content()

        except Exception:

            pass



    return "\n".join(textos)





def extrair_numero_pingid(driver):

    texto = coletar_texto_pagina_e_iframes(driver)



    candidatos_linha = re.findall(r"(?m)^\s*(\d{2,3})\s*$", texto)

    if candidatos_linha:

        return candidatos_linha[0], texto



    candidatos = re.findall(r"\b(\d{2,3})\b", texto)

    if candidatos:

        return candidatos[0], texto



    return None, texto





def portal_airbus_carregado(driver):

    try:

        driver.switch_to.default_content()



        if driver.find_elements(By.XPATH, '//*[@id="searchContent"]/div/adns-searchbar/div/form/input'):

            return True



        if driver.find_elements(By.ID, "searchContent"):

            return True



    except Exception:

        pass



    return False





def clicar_proceed_se_aparecer(driver, timeout=8):

    fim = time.time() + timeout



    while time.time() < fim:

        try:

            botao = WebDriverWait(driver, 1).until(

                EC.element_to_be_clickable((By.ID, "proceed-btn"))

            )

            driver.execute_script("arguments[0].click();", botao)

            time.sleep(2)

            return True

        except Exception:

            pass



        try:

            driver.switch_to.default_content()

            frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")



            for frame in frames:

                try:

                    driver.switch_to.frame(frame)

                    botoes = driver.find_elements(By.ID, "proceed-btn")

                    if botoes:

                        botao = botoes[0]

                        if botao.is_displayed() and botao.is_enabled():

                            driver.execute_script("arguments[0].click();", botao)

                            time.sleep(2)

                            driver.switch_to.default_content()

                            return True

                except Exception:

                    pass

                finally:

                    driver.switch_to.default_content()

        except Exception:

            pass



        time.sleep(0.5)



    return False





def mostrar_checkpoint_2fa(driver, segundos_restantes):
    """Registra o número do MFA para a interface gráfica."""
    numero, _ = extrair_numero_pingid(driver)
    identificador = numero or "não identificado automaticamente"
    info(f"2FA aguardando aprovação. Número: {identificador}. Restante: {int(segundos_restantes)}s.")


def aguardar_2fa_airbus(driver, timeout=TIMEOUT_2FA_SEGUNDOS):

    inicio = time.time()

    ultimo_update = 0



    while True:

        decorrido = time.time() - inicio

        restante = timeout - decorrido



        if portal_airbus_carregado(driver):

            clear_output(wait=True)

            ok("Login 2FA concluído. Portal Airbus carregado.")

            return



        if clicar_proceed_se_aparecer(driver, timeout=2):

            warn("Tela de disclaimer detectada. Botão Proceed clicado.")

            time.sleep(2)



            if portal_airbus_carregado(driver):

                clear_output(wait=True)

                ok("Login 2FA concluído. Portal Airbus carregado.")

                return



        if restante <= 0:

            raise TimeoutException("Tempo limite aguardando autenticação PingID.")



        if time.time() - ultimo_update >= 5:

            mostrar_checkpoint_2fa(driver, restante)

            ultimo_update = time.time()



        time.sleep(1)





def ler_secret_colab(nome):
    """Lê configuração da interface/ambiente local; mantém o nome por compatibilidade."""
    return os.environ.get(f"AERODOC_{nome}")





def obter_credenciais_airbus():

    usuario = ler_secret_colab("AIRBUS_USER") or input("Usuário Airbus: ")

    senha = ler_secret_colab("AIRBUS_PASS") or getpass("Senha Airbus: ")

    return usuario, senha





def acessar_portal_airbus(driver, tentativas=3):
    for tentativa in range(1, tentativas + 1):
        try:
            driver.get(PORTAL_AIRBUS_URL)
        except TimeoutException:
            warn(
                f"O portal demorou além do limite na tentativa {tentativa}/{tentativas}. "
                "Continuando com a página disponível."
            )
            try:
                driver.execute_script("window.stop();")
            except Exception:
                pass

        if portal_airbus_carregado(driver):
            return
        if driver.find_elements(
            By.XPATH,
            '//*[@id="Login"]/table/tbody/tr[1]/td[3]/table/tbody/tr[2]/td/input',
        ):
            return

        if tentativa < tentativas:
            warn("A tela do portal Airbus não respondeu. Tentando novamente...")
            time.sleep(2)

    raise TimeoutException("O portal Airbus não apresentou a tela de login após 3 tentativas.")


def fazer_login_airbus(driver, usuario_airbus, senha_airbus):

    step("Acessando portal Airbus...")

    acessar_portal_airbus(driver)



    wait = WebDriverWait(driver, 30)



    if portal_airbus_carregado(driver):

        ok("Sessão Airbus já autenticada.")

        return



    step("Preenchendo login Airbus...")



    try:
        login_input = wait.until(
            EC.visibility_of_element_located(
                (By.XPATH, '//*[@id="Login"]/table/tbody/tr[1]/td[3]/table/tbody/tr[2]/td/input')
            )
        )
    except TimeoutException:
        diagnostic_dir = BASE_DIR / "screenshots"
        diagnostic_dir.mkdir(parents=True, exist_ok=True)
        diagnostic_path = diagnostic_dir / "airbus_login_timeout.png"
        try:
            driver.save_screenshot(str(diagnostic_path))
        except Exception:
            diagnostic_path = None
        err(
            "Campo de login Airbus não apareceu. "
            f"URL atual: {driver.current_url} | Título: {driver.title}"
        )
        if diagnostic_path:
            err(f"Screenshot de diagnóstico: {diagnostic_path}")
        raise



    senha_input = driver.find_element(

        By.XPATH,

        '//*[@id="Login"]/table/tbody/tr[2]/td[3]/table/tbody/tr[2]/td/input'

    )



    botao_enter = driver.find_element(By.XPATH, '//*[@id="enter_li"]/a')



    login_input.clear()

    login_input.send_keys(usuario_airbus)



    senha_input.clear()

    senha_input.send_keys(senha_airbus)



    botao_enter.click()



    info("Login enviado. Aguardando PingID...")

    aguardar_2fa_airbus(driver)





def aguardar_novo_pdf(pasta_temp, pdfs_antes, timeout=TIMEOUT_DOWNLOAD_SEGUNDOS):

    inicio = time.time()



    while time.time() - inicio < timeout:

        pdfs_agora = set(glob.glob(os.path.join(pasta_temp, "*.pdf")))

        novos = list(pdfs_agora - pdfs_antes)

        incompletos = glob.glob(os.path.join(pasta_temp, "*.crdownload"))



        if novos and not incompletos:

            novos.sort(key=lambda p: os.path.getmtime(p), reverse=True)

            return novos[0]



        time.sleep(2)



    raise TimeoutException("Tempo limite de geração/download do PDF excedido.")





def fechar_abas_extras(driver):

    try:

        while len(driver.window_handles) > 1:

            driver.switch_to.window(driver.window_handles[-1])

            driver.close()

        driver.switch_to.window(driver.window_handles[0])

    except Exception:

        pass





def recuperar_airbus(driver, usuario_airbus, senha_airbus):

    try:

        warn("Recuperando sessão Airbus...")

        fechar_abas_extras(driver)

        driver.get(PORTAL_AIRBUS_URL)

        time.sleep(3)



        if not portal_airbus_carregado(driver):

            fazer_login_airbus(driver, usuario_airbus, senha_airbus)



        ok("Sessão Airbus recuperada.")

    except Exception as erro:

        if VERBOSE_ERROS:

            traceback.print_exc()

        err_curto(erro, "Falha ao tentar recuperar sessão Airbus")





def nome_arquivo_seguro(valor):

    valor = str(valor).strip()

    valor = re.sub(r"[^A-Za-z0-9._-]+", "_", valor)

    return valor[:150] if valor else "arquivo"





# ==========================================================

# ROBÔ POR PART NUMBER

# ==========================================================



def selecionar_tarefas_da_aba(df):

    col_part = encontrar_coluna(df.columns, ["Part Number", "PN_PREFERIVEL", "PN", "PartNumber"])

    col_status = encontrar_coluna(df.columns, ["STATUS"])



    if not col_part:

        raise RuntimeError("Não encontrei a coluna 'Part Number' na aba selecionada.")

    if not col_status:

        raise RuntimeError("Não encontrei a coluna 'STATUS' na aba selecionada.")



    df = df.copy()

    df[col_part] = df[col_part].astype(str).str.strip()

    df[col_status] = df[col_status].fillna("").astype(str).str.strip()



    # Processa SOMENTE STATUS em branco

    filtro_part = df[col_part].ne("")

    filtro_status = df[col_status].eq("")



    df_filtrado = df[filtro_part & filtro_status]



    tarefas = []

    for pn in df_filtrado[col_part].drop_duplicates().tolist():

        linhas_do_pn = df[df[col_part].eq(pn)]["_row_number"].tolist()

        tarefas.append({

            "pn": pn,

            "row_numbers": linhas_do_pn,

        })



    return tarefas, col_part, col_status, len(df_filtrado)





def baixar_pdf_airbus(driver, pn, pasta_temp):

    wait_elements = WebDriverWait(driver, 20)

    pdfs_antes = set(glob.glob(os.path.join(pasta_temp, "*.pdf")))



    step(f"Pesquisando PN: {pn}")



    search_bar = wait_elements.until(

        EC.element_to_be_clickable(

            (By.XPATH, '//*[@id="searchContent"]/div/adns-searchbar/div/form/input')

        )

    )



    search_bar.clear()

    search_bar.send_keys(pn)

    search_bar.send_keys(Keys.RETURN)



    xpath_resultado_fig = "//*[contains(text(), 'FIG.')]"



    try:

        resultado_fig = wait_elements.until(

            EC.presence_of_element_located((By.XPATH, xpath_resultado_fig))

        )

    except Exception:

        raise RuntimeError("PN não localizado na pesquisa ou resultado FIG. não encontrado.")



    driver.execute_script(

        "arguments[0].scrollIntoView({block: 'center'});",

        resultado_fig,

    )



    time.sleep(1.5)



    try:

        wait_elements.until(

            EC.element_to_be_clickable((By.XPATH, xpath_resultado_fig))

        ).click()

    except Exception:

        driver.execute_script("arguments[0].click();", resultado_fig)



    time.sleep(3)



    xpath_impressora = '//*[@id="tool"]/md-menu[1]/button'

    icone_impressora = wait_elements.until(

        EC.element_to_be_clickable((By.XPATH, xpath_impressora))

    )

    icone_impressora.click()



    time.sleep(1)



    xpath_export_pdf = "//a[@ng-click='vm.printTaskPdf($event)']"



    try:

        botao_export_pdf = wait_elements.until(

            EC.visibility_of_element_located((By.XPATH, xpath_export_pdf))

        )

        botao_export_pdf.click()

    except Exception:

        botao_export_pdf = driver.find_element(By.XPATH, xpath_export_pdf)

        driver.execute_script("arguments[0].click();", botao_export_pdf)



    time.sleep(2)



    xpath_input_name = "//input[@name='pdfBasketName']"

    input_package_name = wait_elements.until(

        EC.visibility_of_element_located((By.XPATH, xpath_input_name))

    )



    input_package_name.clear()

    input_package_name.send_keys(pn)

    input_package_name.send_keys(Keys.TAB)



    time.sleep(1)



    xpath_print_pdf = "//button[@ng-click='addSinglePdf()']"



    try:

        botao_print = wait_elements.until(

            EC.element_to_be_clickable((By.XPATH, xpath_print_pdf))

        )

        botao_print.click()

    except Exception:

        botao_print = driver.find_element(By.XPATH, xpath_print_pdf)

        driver.execute_script("arguments[0].click();", botao_print)



    info("Comando enviado. Aguardando download do PDF...")



    novo_pdf = aguardar_novo_pdf(pasta_temp, pdfs_antes)

    return novo_pdf





def executar_aba(ws):

    head(f"ABA ESCOLHIDA: {ws.title}")



    garantir_colunas(ws)

    df = carregar_dataframe_da_aba(ws)

    tarefas, col_part, col_status, total_linhas_elegiveis = selecionar_tarefas_da_aba(df)



    if not tarefas:

        ok("Nenhum item pendente encontrado na aba selecionada.")

        info("Somente linhas com STATUS em branco são processadas.")

        return



    resumo = criar_resumo_inicial(total_linhas_elegiveis, len(tarefas))



    head(f"RESUMO DA EXECUÇÃO - {ws.title}")

    info(f"Linhas elegíveis com STATUS em branco: {resumo['total_linhas_elegiveis']}")

    info(f"Part Numbers únicos a processar: {resumo['total_pns_unicos']}")

    info("Status final de sucesso: PDF Anexado")

    info("Status final de erro: ERRO")

    info("PDFs serão enviados para a pasta Drive informada.")

    info("Se já existir PDF com o mesmo nome, o conteúdo será substituído.")



    usuario_airbus, senha_airbus = obter_credenciais_airbus()



    if os.path.exists(PASTA_TEMP_LOCAL):

        shutil.rmtree(PASTA_TEMP_LOCAL)

    os.makedirs(PASTA_TEMP_LOCAL, exist_ok=True)



    step("Iniciando navegador Chrome no Colab...")

    driver = criar_driver_local(PASTA_TEMP_LOCAL)

    ok("Chrome iniciado com sucesso.")



    try:

        fazer_login_airbus(driver, usuario_airbus, senha_airbus)



        for indice, tarefa in enumerate(tarefas, start=1):

            pn = tarefa["pn"]

            row_numbers = tarefa["row_numbers"]



            step(f"[{indice}/{len(tarefas)}] Iniciando PN {pn}")



            try:

                local_pdf = baixar_pdf_airbus(driver, pn, PASTA_TEMP_LOCAL)

                nome_pdf = f"{nome_arquivo_seguro(pn)}.pdf"



                resultado_drive = upload_ou_substituir_pdf(

                    local_pdf_path=local_pdf,

                    nome_pdf=nome_pdf,

                )



                atualizar_linhas_planilha(

                    ws=ws,

                    row_numbers=row_numbers,

                    status="PDF Anexado",

                    detalhe_status=resultado_drive["mensagem"],

                    link_pdf=resultado_drive["link"],

                )



                resumo["sucesso"] += 1

                if resultado_drive["acao"] == "novo":

                    resumo["novo_drive"] += 1

                else:

                    resumo["substituido_drive"] += 1



                ok(f"Sucesso PN {pn}: {resultado_drive['mensagem']}")

                info(f"Arquivo: {nome_pdf}")



                try:

                    os.remove(local_pdf)

                except Exception:

                    pass



                fechar_abas_extras(driver)



            except Exception as erro_pn:

                mensagem_erro = str(erro_pn)



                atualizar_linhas_planilha(

                    ws=ws,

                    row_numbers=row_numbers,

                    status="ERRO",

                    detalhe_status=mensagem_erro,

                    link_pdf="",

                )



                resumo["erro"] += 1



                err_curto(erro_pn, f"PN {pn}")

                warn("Tentando recuperar sessão Airbus...")

                recuperar_airbus(driver, usuario_airbus, senha_airbus)



    finally:

        try:

            driver.quit()

        except Exception:

            pass



        try:

            if os.path.exists(PASTA_TEMP_LOCAL):

                shutil.rmtree(PASTA_TEMP_LOCAL)

        except Exception:

            pass



    imprimir_resumo_final(resumo)

    ok("Execução concluída.")





# ==========================================================

# PLACEHOLDERS DAS OUTRAS ABAS

# ==========================================================



def executar_boeing(ws):

    head("BOEING")

    info("A aba Boeing foi selecionada.")

    info("Robô Boeing ainda não desenvolvido.")

    info("Quando você desenvolver essa automação, ela pode usar a mesma estrutura de Part Number + STATUS.")





def executar_embraer(ws):

    head("EMBRAER")

    info("A aba Embraer foi selecionada.")

    info("Robô Embraer ainda não desenvolvido.")





def executar_geral(ws):

    head("GERAL")

    info("A aba Geral foi selecionada.")

    info("Fluxo Geral ainda não desenvolvido.")





# ==========================================================

# MAIN

# ==========================================================



def iniciar_automacao():

    spreadsheet = abrir_planilha()

    aba_escolhida = escolher_aba(spreadsheet)

    ws = spreadsheet.worksheet(aba_escolhida)



    if aba_escolhida in ABAS_VALIDAS:

        executar_aba(ws)

    else:

        raise RuntimeError(f"Aba não reconhecida: {aba_escolhida}")


def emitir_resultado_local(pn, status, detalhe, arquivo=None):
    print(
        "[AERODOC_RESULT] "
        + json.dumps(
            {
                "pn": pn,
                "status": status,
                "detail": detalhe,
                "file": str(arquivo) if arquivo else "",
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def executar_local(pns):
    """Executa AirNavX com PNs informados pela interface, sem Sheets ou Drive."""
    if not pns:
        raise RuntimeError("Nenhum Part Number foi informado.")

    if os.path.exists(PASTA_TEMP_LOCAL):
        shutil.rmtree(PASTA_TEMP_LOCAL)
    os.makedirs(PASTA_TEMP_LOCAL, exist_ok=True)

    usuario, senha = obter_credenciais_airbus()
    driver = criar_driver_local(PASTA_TEMP_LOCAL)
    try:
        fazer_login_airbus(driver, usuario, senha)
        for indice, pn in enumerate(pns, start=1):
            step(f"[{indice}/{len(pns)}] PN {pn}")
            try:
                arquivo = baixar_pdf_airbus(driver, pn, PASTA_TEMP_LOCAL)
                detalhe = f"PDF baixado localmente: {arquivo}"
                ok(detalhe)
                emitir_resultado_local(pn, "PDF BAIXADO", detalhe, arquivo)
            except Exception as exc:
                detalhe = f"{type(exc).__name__}: {exc}"
                err_curto(exc, f"PN {pn}")
                emitir_resultado_local(pn, "ERRO", detalhe)
    finally:
        driver.quit()





if __name__ == "__main__":
    if LOCAL_ONLY:
        executar_local(
            [pn.strip() for pn in os.environ.get("AERODOC_PNS", "").splitlines() if pn.strip()]
        )
    else:
        iniciar_automacao()

