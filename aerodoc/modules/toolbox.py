import time
import json



# AUTOMACAO DE DOWNLOAD DE PDFS TECNICOS

# Versão: seleção de aeronave, download do PDF e anexo no Google Drive.

import os

import glob

import base64

import urllib.parse

import traceback

import re

import logging

import sys

LOCAL_ONLY = os.environ.get("AERODOC_LOCAL_ONLY", "false").lower() == "true"

from datetime import datetime
import pypdf



import requests

import urllib3



# Desativa avisos de SSL do requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



from pathlib import Path
from google.oauth2 import service_account

class _Auth:
    @staticmethod
    def authenticate_user():
        return None

class _UserData:
    @staticmethod
    def get(name):
        return os.environ.get(f"AERODOC_{name}")

auth = _Auth()
userdata = _UserData()

def default(scopes=None):
    credentials_file = Path(os.environ.get(
        "AERODOC_GOOGLE_CREDENTIALS",
        str(Path(__file__).resolve().parent / "credentials.json"),
    ))
    if not credentials_file.exists():
        raise FileNotFoundError(f"Arquivo de credenciais Google não encontrado: {credentials_file}")
    return service_account.Credentials.from_service_account_file(
        str(credentials_file),
        scopes=scopes or [],
    ), None

import gspread



from googleapiclient.discovery import build

from googleapiclient.http import MediaFileUpload



from selenium import webdriver

from selenium.webdriver.common.by import By

from selenium.webdriver.common.keys import Keys

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.support import expected_conditions as EC



from selenium.common.exceptions import (

    TimeoutException,

    ElementClickInterceptedException,

    StaleElementReferenceException,

    WebDriverException,

    NoSuchWindowException

)

from platform_utils import find_chrome, select_all_key



def display(_value):
    return None

class Image:
    def __init__(self, filename, width=None):
        self.filename = filename
        self.width = width



# =======================================================

# 1. MODO DE BUSCA

# =======================================================

# O módulo Toolbox sempre percorre todas as frotas. A seleção individual
# existia no script original, mas não é necessária para a execução local.
FROTA_ALVO = "GERAL"
print("\n[SELEÇÃO] Toolbox configurado para pesquisar todas as frotas.\n")



MAPA_ABAS_AERONAVE = {

    "A320": "Airbus",

    "B767": "Boeing",

    "B777": "Boeing",

    "B787": "Boeing",

    "E2": "Embraer",

}



# GID informado no link da planilha para a aba Boeing.

# O acesso por GID evita problemas com espaços ou caracteres invisíveis no nome.

MAPA_GID_ABAS = {

    "Boeing": 1117048061,

}



# Mapeamento explícito da aeronave para a aba da planilha.

# B767, B777 e B787 sempre usam a aba Boeing.

ABA_POR_AERONAVE = {

    "A320": "Airbus",

    "B767": "Boeing",

    "B777": "Boeing",

    "B787": "Boeing",

    "E2": "Embraer",

}



# =======================================================

# 2. CONFIGURAÇÕES DE AERONAVES, PLANILHA E DRIVE

# =======================================================

CONFIG_FROTAS = {

    "A320": {

        "link_text": "launch a320",

        "url": "https://toolbox.appslatam.com/a320/ToolboxRemote.html#/ap/01832",

        "model_payload": "320",

        "book_base": "Application/v2/lan/320/ipd/",

    },



    "B767": {

        "link_text": "launch b767",

        "url": "https://toolbox.appslatam.com/b767/ToolboxRemote.html#/ap/34245",

        "model_payload": "767",

        "book_base": "Application/v2/lan/767/ipd/",

    },



    "B777": {

        "link_text": "launch b777",

        "url": "https://toolbox.appslatam.com/b777/ToolboxRemote.html#/ap/40589",

        "model_payload": "777",

        "book_base": "Application/v2/lan/777/ipd/",

    },



    "B787": {

        "link_text": "launch b787",

        "url": "https://toolbox.appslatam.com/B787/ToolboxRemote.html#/ap/38483",

        "model_payload": "787",

        "book_base": "Application/v2/lan/787/ipd/",

    },



    "E2": {

        "link_text": "launch e2",

        "url": "https://toolbox.appslatam.com/e195/ToolboxRemote.html#/ap/19020234",

        "model_payload": "E2",

        "book_base": "Application/v2/lan/e2/ipd/",

    },

}



URL_PLANILHA = (

    "https://docs.google.com/spreadsheets/d/"

    "17tXzBd-mVXk9BjdrlUqltmLrEPPHmr9MzlNmH-3-dco/"

    "edit?gid=1117048061#gid=1117048061"

)



ID_PASTA_DRIVE = os.environ.get("AERODOC_DRIVE_FOLDER_ID", "1-kqCphZI0IrmNtmAuGecmJvZXt7WuPVU")

PASTA_DOWNLOADS = os.environ.get("AERODOC_DOWNLOAD_DIR", str(Path(__file__).resolve().parent / "downloads"))

PASTA_LOGS = os.environ.get("AERODOC_LOG_DIR", str(Path(__file__).resolve().parent / "logs"))

ARQUIVO_LOG = os.path.join(PASTA_LOGS, "automacao_b787.log")



URL_TOOLBOX = (

    "https://sites.google.com/latam.com/mdmmro/documentos/"

    "acesso-toolbox?authuser=0"

)



COLUNA_PN_PADRAO = 1

COLUNA_STATUS_PADRAO = 2

COLUNA_DETALHE_STATUS_PADRAO = 3

COLUNA_LINK_DRIVE_PADRAO = 4



MIN_COLUNAS_PLANILHA = 4

TEMPO_ESPERA_RESULTADO = 40

TEMPO_ESPERA_DOWNLOAD = 90

MAX_TENTATIVAS_PN = 3





# =======================================================

# 3. LOGGING

# O console mostra apenas mensagens resumidas. O arquivo mantém detalhes.

# =======================================================

os.makedirs(PASTA_DOWNLOADS, exist_ok=True)

os.makedirs(PASTA_LOGS, exist_ok=True)



logger = logging.getLogger("automacao_b787")

logger.setLevel(logging.DEBUG)

logger.propagate = False



if not logger.handlers:

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    handler_arquivo = logging.FileHandler(ARQUIVO_LOG, encoding="utf-8")

    handler_arquivo.setLevel(logging.DEBUG)

    handler_arquivo.setFormatter(formatter)

    logger.addHandler(handler_arquivo)



def log_info(mensagem):

    print(f"[INFO] {mensagem}", flush=True)

    logger.info(mensagem)



def log_ok(mensagem):

    print(f"[OK] {mensagem}", flush=True)

    logger.info(f"SUCESSO | {mensagem}")



def log_alerta(mensagem):

    print(f"[AVISO] {mensagem}", flush=True)

    logger.warning(mensagem)



def log_erro(mensagem):

    print(f"[ERRO] {mensagem}", flush=True)

    logger.error(mensagem)



def iniciar_etapa(numero, titulo):

    print(f"\n[{numero}] {titulo}", flush=True)

    print("-" * 64, flush=True)



print("\n[INÍCIO] Automação de download e anexo de PDFs")

# =======================================================

# FUNÇÕES AUXILIARES E PLANILHA

# =======================================================

def nome_seguro(texto):

    texto = str(texto or "").strip()

    texto = re.sub(r"[^\w\-.]+", "_", texto)

    return texto.strip("_") or "sem_nome"



def salvar_screenshot(driver, nome_arquivo, largura=800):

    """Salva e exibe uma captura de tela para apoiar o acompanhamento do login."""

    nome_arquivo = nome_seguro(nome_arquivo)

    if not nome_arquivo.endswith(".png"):

        nome_arquivo += ".png"

    caminho = os.path.join(PASTA_LOGS, nome_arquivo)

    try:

        driver.save_screenshot(caminho)

        display(Image(caminho, width=largura))

        return caminho

    except Exception as e:

        log_alerta(f"Não foi possível salvar screenshot {caminho}: {str(e)}")

        return None


def _coletar_conteudo_mfa_visivel(driver):
    """Coleta texto e atributos visíveis da página e de seus iframes."""
    textos = []
    atributos = []

    def coletar_contexto():
        try:
            textos.append(driver.find_element(By.TAG_NAME, "body").text)
        except Exception:
            pass
        try:
            elementos = driver.find_elements(
                By.XPATH, "//*[@aria-label or @title or @value or @alt]"
            )
            for elemento in elementos:
                if not elemento.is_displayed():
                    continue
                for atributo in ("aria-label", "title", "value", "alt"):
                    valor = (elemento.get_attribute(atributo) or "").strip()
                    if valor:
                        atributos.append(valor)
        except Exception:
            pass

    try:
        driver.switch_to.default_content()
        coletar_contexto()
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in frames:
            try:
                driver.switch_to.default_content()
                driver.switch_to.frame(frame)
                coletar_contexto()
            except Exception:
                continue
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

    return "\n".join(textos), atributos


def registrar_status_mfa(driver):
    try:
        title = (driver.title or "").lower()
        texto, atributos_visiveis = _coletar_conteudo_mfa_visivel(driver)
    except Exception:
        title = ""
        texto = ""
        atributos_visiveis = []

    if os.environ.get("AERODOC_MFA_DEBUG", "false").lower() == "true":
        try:
            caminho_debug = os.path.join(
                PASTA_LOGS, f"mfa_debug_{int(time.time())}.png"
            )
            driver.save_screenshot(caminho_debug)
            log_info(f"MFA debug - screenshot: {caminho_debug}")
        except Exception:
            pass
        try:
            controles = []
            for elemento in driver.find_elements(
                By.XPATH, "//button | //*[@role='button'] | //a"
            ):
                if not elemento.is_displayed():
                    continue
                rotulo = (
                    elemento.text
                    or elemento.get_attribute("aria-label")
                    or elemento.get_attribute("title")
                    or ""
                ).strip()
                if rotulo:
                    controles.append(" ".join(rotulo.split())[:100])
            if controles:
                log_info("MFA debug - controles: " + " | ".join(controles[:20]))
        except Exception:
            pass

    texto_lower = texto.lower()
    termos_mfa = (
        "microsoft authenticator",
        "approve sign-in request",
        "aprovar solicitação",
        "aprovar solicitacao",
        "digite o número",
        "digite o numero",
        "enter the number",
        "number shown",
        "corresponder ao número",
        "corresponder ao numero",
        "match the number",
        "verificar sua identidade",
    )

    if not any(termo in title or termo in texto_lower for termo in termos_mfa):
        log_info("2FA aguardando aprovação no aplicativo de autenticação.")
        return None

    numero = None
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    linhas.extend(valor for valor in atributos_visiveis if valor)
    termos_numero = (
        "número", "numero", "number", "código", "codigo", "code",
        "matching number", "verification code",
    )
    for indice, linha in enumerate(linhas):
        if not any(termo in linha.lower() for termo in termos_numero):
            continue
        numeros_na_linha = re.findall(r"\b\d{2,8}\b", linha)
        if numeros_na_linha:
            numero = numeros_na_linha[-1]
            break
        for proxima_linha in linhas[indice + 1:indice + 4]:
            if re.fullmatch(r"\d{2,8}", proxima_linha):
                numero = proxima_linha
                break
        if not numero:
            for linha_anterior in reversed(linhas[max(0, indice - 3):indice]):
                if re.fullmatch(r"\d{2,8}", linha_anterior):
                    numero = linha_anterior
                    break
        if numero:
            break

    if not numero:
        termos_prompt = (
            "approve sign-in request", "aprovar", "enter the number",
            "number shown", "matching number", "digite o número",
            "digite o numero", "match the number",
        )
        if any(termo in linha.lower() for linha in linhas for termo in termos_prompt):
            candidatos = [
                linha for linha in linhas
                if re.fullmatch(r"\d{2,8}", linha)
            ]
            if candidatos:
                numero = candidatos[-1]

    if numero:
        print(
            f"[AERODOC_MFA] number={numero} app=Microsoft Authenticator",
            flush=True,
        )
        linhas_relevantes = [
            linha.strip()
            for linha in texto.splitlines()
            if re.search(r"\b\d{2,8}\b", linha)
            and any(
                termo in linha.lower()
                for termo in ("number", "número", "numero", "code", "código")
            )
        ]
        if linhas_relevantes:
            log_info(f"Texto visível do MFA: {' | '.join(linhas_relevantes[:2])}")
    elif os.environ.get("AERODOC_MFA_DEBUG", "false").lower() == "true":
        linhas_numericas = [
            linha.strip()
            for linha in linhas
            if re.search(r"\b\d{2,8}\b", linha)
        ]
        log_info(
            "MFA debug - linhas numéricas visíveis: "
            + (" | ".join(linhas_numericas[:8]) if linhas_numericas else "nenhuma")
        )

    log_info(
        f"2FA aguardando aprovação. Número: {numero}."
        if numero
        else "2FA aguardando aprovação no aplicativo de autenticação."
    )
    return numero


def detectar_recusa_mfa(driver):
    """Detecta uma recusa explícita do Microsoft Authenticator."""
    try:
        texto = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return False

    termos_recusa = (
        "request was denied",
        "sign-in request was denied",
        "access denied",
        "authentication denied",
        "request denied",
        "rejected",
        "declined",
        "solicitação negada",
        "solicitacao negada",
        "acesso negado",
        "autenticação recusada",
        "autenticacao recusada",
    )
    return any(termo in texto for termo in termos_recusa)


def selecionar_microsoft_authenticator(driver):
    """Seleciona o Microsoft Authenticator quando a Microsoft pede o método."""
    try:
        texto, atributos_visiveis = _coletar_conteudo_mfa_visivel(driver)
        texto = (texto + "\n" + "\n".join(atributos_visiveis)).lower()
    except Exception:
        return False

    termos_tela_metodo = (
        "verificar sua identidade",
        "verificar a sua identidade",
        "verify your identity",
        "choose how you want to verify",
        "choose how you'd like to verify",
        "choose an option",
        "choose a verification method",
        "select a method",
        "escolha como deseja verificar",
        "escolha uma opção",
        "escolha uma opcao",
        "selecione um método",
        "selecione um metodo",
        "selecionar método",
        "selecionar metodo",
        "método de autenticação",
        "metodo de autenticacao",
        "outras formas de entrar",
        "other ways to sign in",
    )
    termos_tela_numero = (
        "approve sign-in request",
        "aprovar uma solicitação",
        "aprovar uma solicitacao",
        "enter the number",
        "enter the number shown",
        "type the number",
        "number shown",
        "number displayed",
        "matching number",
        "match this number",
        "digite o número",
        "digite o numero",
        "insira o número",
        "insira o numero",
        "introduza o número",
        "introduza o numero",
        "número exibido",
        "numero exibido",
        "número apresentado",
        "numero apresentado",
    )
    if any(termo in texto for termo in termos_tela_numero):
        return False
    termos_numero_visivel = (
        "número", "numero", "number", "código", "codigo", "code",
        "matching", "correspond",
    )
    linhas_tela = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    for indice, linha in enumerate(linhas_tela):
        if not any(termo in linha for termo in termos_numero_visivel):
            continue
        if re.search(r"\b\d{2,8}\b", linha):
            return False
        if any(
            re.fullmatch(r"\d{2,8}", candidata)
            for candidata in (
                linhas_tela[max(0, indice - 1):indice]
                + linhas_tela[indice + 1:indice + 3]
            )
        ):
            return False

    tela_metodo = any(termo in texto for termo in termos_tela_metodo)
    tela_metodo = tela_metodo or (
        ("microsoft authenticator" in texto or "authenticator app" in texto)
        and not any(termo in texto for termo in termos_tela_numero)
    )

    xpath_authenticator = (
        "//button[contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÃÕÇ', "
        "'abcdefghijklmnopqrstuvwxyzáéíóúãõç'), 'microsoft authenticator')]"
        " | //*[@role='button' and contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÃÕÇ', "
        "'abcdefghijklmnopqrstuvwxyzáéíóúãõç'), 'microsoft authenticator')]"
        " | //a[contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÃÕÇ', "
        "'abcdefghijklmnopqrstuvwxyzáéíóúãõç'), 'microsoft authenticator')]"
        " | //*[@role='link' and contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÃÕÇ', "
        "'abcdefghijklmnopqrstuvwxyzáéíóúãõç'), 'microsoft authenticator')]"
        " | //*[@role='button' and contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÃÕÇ', "
        "'abcdefghijklmnopqrstuvwxyzáéíóúãõç'), 'authenticator app')]"
        " | //*[contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÃÕÇ', "
        "'abcdefghijklmnopqrstuvwxyzáéíóúãõç'), 'microsoft authenticator')]/ancestor::*[@role='button' or @role='link'][1]"
    )
    try:
        driver.switch_to.default_content()
        opcao = buscar_elemento_em_frames(driver, xpath_authenticator)
        if opcao and opcao.is_displayed() and opcao.is_enabled():
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", opcao)
            driver.execute_script("arguments[0].click();", opcao)
            log_info("Método Microsoft Authenticator selecionado automaticamente.")
            return True
    except Exception as erro:
        logger.debug(f"selecionar_microsoft_authenticator: {erro}")
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
    return False



def exibir_resumo_logs():

    """Exibe somente o caminho do log detalhado ao final da execução."""

    print("\n" + "=" * 64)

    print("RESUMO DA EXECUÇÃO")

    print("=" * 64)

    print(f"Log detalhado: {ARQUIVO_LOG}")

    print("=" * 64)



def normalizar_texto(texto):

    return re.sub(r"\s+", " ", str(texto or "").strip().upper())



def localizar_aba_planilha(planilha, nome_desejado, gid=None):

    """Localiza a aba ignorando maiúsculas, espaços extras e acentos simples."""

    if gid is not None:

        try:

            aba_por_gid = planilha.get_worksheet_by_id(int(gid))

            if aba_por_gid is not None:

                return aba_por_gid

        except Exception as erro:

            log_alerta(f"Não foi possível localizar a aba '{nome_desejado}' pelo GID {gid}: {erro}")



    try:

        abas_disponiveis = planilha.worksheets()

    except Exception as erro:

        raise Exception(f"Não foi possível listar as abas da planilha: {erro}")



    alvo = normalizar_texto(nome_desejado)

    for aba_disponivel in abas_disponiveis:

        if normalizar_texto(aba_disponivel.title) == alvo:

            return aba_disponivel



    nomes_encontrados = ", ".join(repr(aba.title) for aba in abas_disponiveis)

    log_alerta(f"Aba '{nome_desejado}' não encontrada. Abas disponíveis: {nomes_encontrados}")

    return None



def limpar_pasta_downloads(pasta_downloads):

    log_info("Limpando arquivos antigos da pasta de downloads...")

    for padrao in ["*.pdf", "*.crdownload", "*.tmp"]:

        for arquivo in glob.glob(os.path.join(pasta_downloads, padrao)):

            try:

                os.remove(arquivo)

            except Exception as e:

                log_alerta(f"Não foi possível remover {arquivo}: {str(e)}")



def garantir_colunas_planilha(worksheet, minimo_colunas=13):

    propriedades = worksheet._properties.get("gridProperties", {})

    colunas_atuais = propriedades.get("columnCount", 0)

    linhas_atuais = propriedades.get("rowCount", 0)

    if colunas_atuais < minimo_colunas:

        log_info(f"A planilha possui {colunas_atuais} coluna(s). Expandindo para {minimo_colunas} colunas...")

        worksheet.resize(rows=max(linhas_atuais, 1000), cols=minimo_colunas)

        time.sleep(2)

    else:

        log_info(f"Planilha validada: {linhas_atuais} linhas e {colunas_atuais} colunas.")



def localizar_coluna_por_cabecalho(cabecalhos, opcoes, padrao):

    cabecalhos_normalizados = [normalizar_texto(c) for c in cabecalhos]

    for opcao in opcoes:

        opcao_normalizada = normalizar_texto(opcao)

        if opcao_normalizada in cabecalhos_normalizados:

            return cabecalhos_normalizados.index(opcao_normalizada) + 1

    return padrao



def obter_mapeamento_colunas(registros):

    if not registros:

        return {

        "pn": COLUNA_PN_PADRAO, "status": COLUNA_STATUS_PADRAO,

            "detalhe_status": COLUNA_DETALHE_STATUS_PADRAO,

            "link_drive": COLUNA_LINK_DRIVE_PADRAO

        }

    cabecalhos = registros[0]

    return {

        "pn": localizar_coluna_por_cabecalho(cabecalhos, ["PART_NUMBER", "PART NUMBER", "PPN", "PPN (PART GROUP)", "PART_GROUP", "REFERENCE_CODE", "REFERENCE CODE"], COLUNA_PN_PADRAO),

        "status": localizar_coluna_por_cabecalho(cabecalhos, ["STATUS", "STATUS PDF", "PDF STATUS"], COLUNA_STATUS_PADRAO),

        "detalhe_status": localizar_coluna_por_cabecalho(cabecalhos, ["DETALHE_STATUS", "DETALHE STATUS", "DETAIL STATUS"], COLUNA_DETALHE_STATUS_PADRAO),

        "link_drive": localizar_coluna_por_cabecalho(cabecalhos, ["LINK_DRIVE", "LINK DRIVE", "DRIVE LINK", "PDF LINK", "LINK PDF"], COLUNA_LINK_DRIVE_PADRAO)

    }



def obter_valor_linha(linha, coluna_1_based):

    indice = coluna_1_based - 1

    return str(linha[indice]).strip() if 0 <= indice < len(linha) else ""



def atualizar_celula_segura(worksheet, linha, coluna, valor):

    try:

        worksheet.update_cell(linha, coluna, valor)

        log_info(f"Planilha atualizada | linha={linha} | coluna={coluna} | valor={str(valor)[:60]}...")

        return True

    except Exception as e:

        log_alerta(f"Falha ao atualizar planilha (linha {linha}, coluna {coluna}): {str(e)}")

        return False





# =======================================================

# LOGIN E NAVEGAÇÃO

# =======================================================

def verificar_e_clicar_profile_chrome(driver):

    try:

        xpath_profile = "//button[contains(., 'Continue as') or contains(., 'Continuar como') or contains(., 'Continue') or contains(., 'Continuar')]"

        botoes = driver.find_elements(By.XPATH, xpath_profile)

        for btn in botoes:

            if btn.is_displayed():

                log_info("Tela de perfil do Chrome detectada. Clicando em continuar...")

                driver.execute_script("arguments[0].click();", btn)

                time.sleep(3)

                return True

    except Exception as e:

        logger.debug(f"verificar_e_clicar_profile_chrome: {str(e)}")

    return False



def detectar_captcha_google(driver):

    seletores_campo = [(By.NAME, "ca"), (By.ID, "ca"), (By.CSS_SELECTOR, "input[name='ca']")]

    seletores_imagem = [(By.ID, "captchaimg"), (By.CSS_SELECTOR, "img#captchaimg")]

    campo_captcha = None

    imagem_captcha = None



    for by, seletor in seletores_campo:

        try:

            for el in driver.find_elements(by, seletor):

                if el.is_displayed():

                    campo_captcha = el

                    break

            if campo_captcha:

                break

        except Exception:

            pass



    for by, seletor in seletores_imagem:

        try:

            for el in driver.find_elements(by, seletor):

                if el.is_displayed():

                    imagem_captcha = el

                    break

            if imagem_captcha:

                break

        except Exception:

            pass



    texto_pagina = ""

    try:

        texto_pagina = driver.find_element(By.TAG_NAME, "body").text.lower()

    except Exception:

        pass



    termos = ["captcha", "verify", "verificar", "security check", "tráfego incomum"]

    texto_indica_captcha = any(termo in texto_pagina for termo in termos)

    url_indica_captcha = any(termo in driver.current_url.lower() for termo in ["captcha", "challenge"])



    return {

        "detectado": bool(campo_captcha or imagem_captcha or texto_indica_captcha or url_indica_captcha),

        "campo": campo_captcha,

        "imagem": imagem_captcha

    }



def solicitar_captcha_manual(driver, tentativa):

    print("\n" + "=" * 70)

    print(f"[!] CAPTCHA DETECTADO — TENTATIVA {tentativa}")

    print("=" * 70)

    info = detectar_captcha_google(driver)

    imagem = info.get("imagem")

    if imagem:

        try:

            caminho_zoom = os.path.join(PASTA_LOGS, f"captcha_zoom_{tentativa}.png")

            imagem.screenshot(caminho_zoom)

            display(Image(caminho_zoom, width=500))

            time.sleep(1)

            sys.stdout.flush()

        except Exception as e:

            log_alerta(f"Não foi possível exibir o CAPTCHA: {str(e)}")



    print("\n👉 DIGITE O CAPTCHA ABAIXO E PRESSIONE ENTER (ou ENTER se concluiu manualmente): ")

    sys.stdout.flush()

    resposta = input("Sua resposta: ")

    campo = info.get("campo")

    if campo and resposta.strip():

        campo.clear()

        campo.send_keys(resposta.strip() + Keys.RETURN)

        log_info("Resposta do CAPTCHA enviada.")

        time.sleep(5)

        return True

    log_alerta("Nenhuma resposta foi enviada ao campo CAPTCHA.")

    time.sleep(3)

    return False



def aguardar_transicao_google_para_microsoft(driver, timeout_total=180):

    inicio = time.time()

    tentativa_captcha = 0

    ultimo_log = 0



    while time.time() - inicio < timeout_total:

        verificar_e_clicar_profile_chrome(driver)

        if driver.find_elements(By.ID, "i0116"):

            log_ok("Tela de login Microsoft identificada.")

            return True



        info_captcha = detectar_captcha_google(driver)

        if info_captcha["detectado"]:

            tentativa_captcha += 1

            log_alerta("Campo ou imagem de CAPTCHA identificado.")

            solicitar_captcha_manual(driver, tentativa_captcha)

            time.sleep(3)

            continue



        segundos = int(time.time() - inicio)

        if segundos - ultimo_log >= 15:

            log_info(f"Aguardando transição Google → Microsoft | tempo={segundos}s | URL={driver.current_url}")

            ultimo_log = segundos

        time.sleep(2)



    return False



def clicar_e_tratar_destino(driver, elemento, descricao, timeout=15):

    abas_antes = set(driver.window_handles)

    url_antes = driver.current_url



    try:

        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", elemento)

        time.sleep(1)

    except Exception:

        pass



    try:

        elemento.click()

    except Exception:

        driver.execute_script("arguments[0].click();", elemento)



    limite = time.time() + timeout

    while time.time() < limite:

        novas_abas = [aba for aba in driver.window_handles if aba not in abas_antes]

        if novas_abas:

            nova_aba = novas_abas[-1]

            driver.switch_to.window(nova_aba)

            return nova_aba

        if driver.current_url != url_antes:

            return driver.current_window_handle

        time.sleep(0.5)



    log_alerta(f"Nenhuma alteração de aba/URL detectada após: {descricao}")

    return driver.current_window_handle



def buscar_elemento_em_frames(driver, xpath, profundidade=0, max_profundidade=5):

    try:

        elementos = driver.find_elements(By.XPATH, xpath)

        for elemento in elementos:

            try:

                if elemento.is_displayed():

                    return elemento

            except StaleElementReferenceException:

                continue



        if profundidade >= max_profundidade:

            return None



        frames = driver.find_elements(By.TAG_NAME, "iframe")

        for frame in frames:

            try:

                driver.switch_to.frame(frame)

                resultado = buscar_elemento_em_frames(driver, xpath, profundidade + 1, max_profundidade)

                if resultado:

                    return resultado

                driver.switch_to.parent_frame()

            except Exception:

                try:

                    driver.switch_to.parent_frame()

                except Exception:

                    driver.switch_to.default_content()

        return None

    except Exception:

        return None



def obter_href_launch_b787(driver, timeout=25):

    xpath_b787 = """

    //a[

        contains(@href, 'toolbox.appslatam.com/B787/ToolboxRemote.html')

        and contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'launch b787 backup')

    ]

    """

    limite = time.time() + timeout

    while time.time() < limite:

        driver.switch_to.default_content()

        link = buscar_elemento_em_frames(driver, xpath_b787)

        if link:

            href = link.get_attribute("href")

            if href:

                href = urllib.parse.urljoin(driver.current_url, href)

                log_info(f"Link B787 identificado: {href}")

                return href

        driver.switch_to.default_content()

        try:

            driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight * 0.75));")

        except Exception:

            pass

        time.sleep(1)



    raise TimeoutException("Não foi possível localizar o link Launch B787 Backup.")



def abrir_b787_em_nova_aba(driver, href_b787, b787_user, b787_pass):

    driver.switch_to.default_content()

    driver.switch_to.new_window("tab")

    aba_b787 = driver.current_window_handle



    token_basic = base64.b64encode(f"{b787_user}:{b787_pass}".encode("utf-8")).decode("utf-8")

    try:

        driver.execute_cdp_cmd("Network.enable", {})

        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {"Authorization": f"Basic {token_basic}"}})

    except Exception as e:

        log_alerta(f"Falha ao configurar Basic Auth via CDP: {str(e)}")



    try:

        driver.set_page_load_timeout(45)

        driver.get(href_b787)

    except TimeoutException:

        log_alerta("B787 excedeu 45 segundos para carregar. Continuará validando a tela.")

    finally:

        try:

            driver.set_page_load_timeout(60)

        except Exception:

            pass



    time.sleep(5)

    if "toolbox.appslatam.com" not in driver.current_url:

        raise Exception(f"A guia não foi direcionada para Toolbox B787. URL atual: {driver.current_url}")



    return aba_b787



def aceitar_termos_b787(driver):

    try:

        wait_termos = WebDriverWait(driver, 15)

        footer = wait_termos.until(EC.element_to_be_clickable((By.ID, "footer_text")))

        footer.click()

        time.sleep(1)

        btn_continue = wait_termos.until(EC.element_to_be_clickable((

            By.XPATH, "//b[contains(text(), 'Continue') or contains(text(), 'Continuar')]"

        )))

        btn_continue.click()

        log_ok("Termos do B787 aceitos.")

    except TimeoutException:

        pass



def remover_modais_sobrepostos(driver):

    try:

        driver.execute_script("""

            var modais = document.querySelectorAll('.modal-backdrop, .tb_airplaneModalWindow, .modal');

            modais.forEach(function(el) { el.remove(); });

            document.body.classList.remove('modal-open');

        """)

    except Exception:

        pass





# =======================================================

# MÓDULO API DE BUSCA E DOWNLOAD

# =======================================================



# =======================================================

# BUSCA SELENIUM — PESQUISA E NAVEGAÇÃO

# =======================================================



def obter_campo_busca_frota(driver, timeout=30):

    """Localiza o campo de pesquisa do Toolbox."""

    xpaths_busca = [

        "//*[@id='tb_searchInputText']",

        "//input[contains(@id, 'search')]",

        "//input[contains(@placeholder, 'Search')]",

        "//input[contains(@placeholder, 'search')]",

        "//input[@type='text' and not(@disabled)]"

    ]

    limite = time.time() + timeout

    while time.time() < limite:

        driver.switch_to.default_content()

        for xpath in xpaths_busca:

            try:

                campos = driver.find_elements(By.XPATH, xpath)

                for campo in campos:

                    try:

                        if campo.is_displayed() and campo.is_enabled():

                            return campo

                    except StaleElementReferenceException:

                        continue

            except Exception:

                pass

        time.sleep(1)

    raise TimeoutException("Campo de pesquisa do Toolbox não localizado.")





def aguardar_frota_pronta(driver, timeout=45):

    """Aguarda o Toolbox ficar pronto para consultas."""

    campo = obter_campo_busca_frota(driver, timeout=timeout)

    log_ok("Toolbox pronto para consultas.")

    return campo





def limpar_campo_busca(driver, campo):

    """Limpa o campo de busca com múltiplas estratégias."""

    try:

        campo.click()

    except Exception:

        pass

    try:

        campo.send_keys(select_all_key(Keys), "a")

        campo.send_keys(Keys.BACKSPACE)

    except Exception:

        pass

    try:

        campo.clear()

    except Exception:

        pass

    try:

        driver.execute_script("""

            arguments[0].value = '';

            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));

            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));

        """, campo)

    except Exception:

        pass





def pesquisar_pn_frota(driver, pn):

    """Digita o PN no campo de busca e dispara a pesquisa."""

    campo = obter_campo_busca_frota(driver, timeout=20)

    limpar_campo_busca(driver, campo)

    try:

        campo.click()

        campo.send_keys(pn)

        campo.send_keys(Keys.ENTER)

    except Exception:

        driver.execute_script("""

            const campo = arguments[0];

            const valor = arguments[1];

            campo.focus();

            campo.value = valor;

            campo.dispatchEvent(new Event('input', { bubbles: true }));

            campo.dispatchEvent(new Event('change', { bubbles: true }));

            campo.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));

            campo.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));

        """, campo, pn)

    time.sleep(2)





def localizar_hyperlink_reference(driver):

    """Localiza hyperlinks técnicos próximos ao label 'Reference:'."""

    xpaths = [

        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reference:')]/following::a[1]",

        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reference:')]//a",

        "//a[starts-with(normalize-space(.), 'DMC-') or starts-with(normalize-space(.), 'AMM-') or starts-with(normalize-space(.), 'CMM-') or starts-with(normalize-space(.), 'IPC-')]"

    ]

    for xpath in xpaths:

        try:

            for link in driver.find_elements(By.XPATH, xpath):

                try:

                    if link.is_displayed():

                        return link

                except StaleElementReferenceException:

                    continue

        except Exception:

            pass

    return None





def localizar_mensagem_sem_resultado(driver):

    """Detecta mensagem de nenhum resultado na tela."""

    xpath = "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'no results to display') or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'no results found')]"

    try:

        for el in driver.find_elements(By.XPATH, xpath):

            if el.is_displayed():

                return el

    except Exception:

        pass

    return None





def aguardar_resultado_pesquisa(driver, pn, timeout=40):

    """Aguarda resultado da busca ou mensagem de ausência."""

    limite = time.time() + timeout

    ultimo_log = 0

    while time.time() < limite:

        hyperlink = localizar_hyperlink_reference(driver)

        if hyperlink:

            texto = hyperlink.text.strip() or hyperlink.get_attribute("href")

            return {"status": "encontrado", "elemento": hyperlink, "texto": texto}

        sem_resultado = localizar_mensagem_sem_resultado(driver)

        if sem_resultado:

            return {"status": "nao_encontrado", "elemento": None, "texto": sem_resultado.text.strip()}

        decorridos = int(timeout - (limite - time.time()))

        if decorridos - ultimo_log >= 10:

            log_info(f"Aguardando resultado PN={pn} | {decorridos}s/{timeout}s")

            ultimo_log = decorridos

        time.sleep(1)

    raise TimeoutException(f"Tempo esgotado aguardando resultado do PN {pn}.")





def clicar_hyperlink_reference(driver, link_reference, pn):

    """Clica no hyperlink do documento e retorna a aba ativa."""

    abas_antes = set(driver.window_handles)

    url_antes = driver.current_url

    try:

        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", link_reference)

        time.sleep(1)

    except Exception:

        pass

    try:

        link_reference.click()

    except Exception:

        driver.execute_script("arguments[0].click();", link_reference)

    limite = time.time() + 15

    while time.time() < limite:

        novas_abas = [a for a in driver.window_handles if a not in abas_antes]

        if novas_abas:

            driver.switch_to.window(novas_abas[-1])

            return novas_abas[-1]

        if driver.current_url != url_antes:

            return driver.current_window_handle

        try:

            if driver.find_elements(By.XPATH, "//i[contains(@class, 'fa-print')]"):

                return driver.current_window_handle

        except Exception:

            pass

        time.sleep(0.5)

    return driver.current_window_handle





def localizar_botao_impressao(driver, pn, timeout=25):

    """Localiza o ícone/botão de impressão."""

    xpaths = [

        "//i[contains(@class, 'fa-print') and contains(@class, 'dropdown-toggle')]",

        "//i[contains(@class, 'fa-print')]",

        "//*[@title='Print']",

        "//*[@title='Imprimir']",

        "//button[contains(., 'Print')]",

        "//button[contains(., 'Imprimir')]"

    ]

    limite = time.time() + timeout

    while time.time() < limite:

        for xpath in xpaths:

            try:

                for el in driver.find_elements(By.XPATH, xpath):

                    if el.is_displayed():

                        return el

            except Exception:

                pass

        time.sleep(1)

    raise TimeoutException(f"Botão de impressão não localizado | PN={pn}")





def localizar_botao_confirmar_impressao(driver, pn, timeout=15):

    """Localiza o botão que confirma a geração do PDF."""

    xpaths = [

        "//*[@id='tb_PrintButtonPopup']",

        "//button[contains(., 'Print')]",

        "//button[contains(., 'Imprimir')]",

        "//input[@value='Print']",

        "//input[@value='Imprimir']"

    ]

    limite = time.time() + timeout

    while time.time() < limite:

        for xpath in xpaths:

            try:

                for el in driver.find_elements(By.XPATH, xpath):

                    if el.is_displayed() and el.is_enabled():

                        return el

            except Exception:

                pass

        time.sleep(1)

    raise TimeoutException(f"Botão de confirmação de impressão não localizado | PN={pn}")





def obter_e_salvar_pdf(driver, aba_frota, url_pdf, pasta_downloads, pn, toolbox_user, toolbox_pass):

    """

    Estratégia tripla para obter o PDF:

    TIER 1 — <a download> no DOM

    TIER 2 — requests com cookies + Basic Auth

    TIER 3 — Navegação direta na aba principal

    """

    caminho_final = os.path.join(pasta_downloads, f"{nome_seguro(pn)}.pdf")

    if os.path.exists(caminho_final):

        try:

            os.remove(caminho_final)

        except Exception:

            pass

    def estado_dos_pdfs():
        estado = {}
        for arquivo in glob.glob(os.path.join(pasta_downloads, "*.pdf")):
            try:
                informacoes = os.stat(arquivo)
                estado[os.path.abspath(arquivo)] = (
                    informacoes.st_mtime_ns,
                    informacoes.st_size,
                )
            except OSError:
                continue
        return estado

    def aguardar_pdf_novo(estado_anterior, timeout):
        limite = time.time() + timeout
        while time.time() < limite:
            if glob.glob(os.path.join(pasta_downloads, "*.crdownload")):
                time.sleep(1)
                continue
            candidatos = []
            for arquivo in glob.glob(os.path.join(pasta_downloads, "*.pdf")):
                caminho_absoluto = os.path.abspath(arquivo)
                try:
                    informacoes = os.stat(arquivo)
                except OSError:
                    continue
                estado_atual = (informacoes.st_mtime_ns, informacoes.st_size)
                if (
                    informacoes.st_size > 100
                    and estado_anterior.get(caminho_absoluto) != estado_atual
                ):
                    candidatos.append(arquivo)
            if candidatos:
                return max(candidatos, key=os.path.getmtime)
            time.sleep(1)
        return None

    try:

        driver.switch_to.window(aba_frota)

        driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": pasta_downloads})

    except Exception:

        pass



    # TIER 1: elemento <a download>

    try:
        estado_anterior = estado_dos_pdfs()

        driver.execute_script("""

            var a = document.createElement('a');

            a.href = arguments[0]; a.download = arguments[1];

            a.style.display = 'none';

            document.body.appendChild(a); a.click(); document.body.removeChild(a);

        """, url_pdf, f"{nome_seguro(pn)}.pdf")

        recente = aguardar_pdf_novo(estado_anterior, timeout=8)
        if recente:
            if os.path.abspath(recente) != os.path.abspath(caminho_final):
                os.replace(recente, caminho_final)
            return caminho_final

    except Exception:

        pass



    # TIER 2: requests com cookies do browser

    try:

        session = requests.Session()

        session.verify = False

        for cookie in driver.get_cookies():

            session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'))

        session.auth = (toolbox_user, toolbox_pass)

        session.headers.update({

            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

            "Referer": driver.current_url,

            "Accept": "application/pdf,application/octet-stream,*/*"

        })

        resposta = session.get(url_pdf, timeout=30)

        if resposta.status_code == 200 and resposta.content.startswith(b"%PDF-"):

            with open(caminho_final, "wb") as f:

                f.write(resposta.content)

            return caminho_final

    except Exception:

        pass



    # TIER 3: navegação direta

    try:
        estado_anterior = estado_dos_pdfs()

        driver.switch_to.window(aba_frota)

        driver.get(url_pdf)

        recente = aguardar_pdf_novo(estado_anterior, timeout=10)
        if recente:
            if os.path.abspath(recente) != os.path.abspath(caminho_final):
                os.replace(recente, caminho_final)
            return caminho_final

    except Exception:

        pass



    return None





def gerar_pdf_do_documento(driver, pasta_downloads, aba_frota, pn, toolbox_user, toolbox_pass):

    """Clica em Print, captura a URL do PDF e faz o download com estratégia tripla."""

    if aba_frota not in driver.window_handles:

        raise Exception(f"Aba da frota não disponível | PN={pn}")



    icone_impressora = localizar_botao_impressao(driver, pn, timeout=25)

    try:

        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", icone_impressora)

        driver.execute_script("arguments[0].click();", icone_impressora)

    except Exception as e:

        raise Exception(f"Não foi possível abrir menu Print | PN={pn} | {e}")



    time.sleep(1)



    btn_print = localizar_botao_confirmar_impressao(driver, pn, timeout=15)

    abas_antes = set(driver.window_handles)

    try:

        driver.execute_script("arguments[0].click();", btn_print)

    except Exception as e:

        raise Exception(f"Não foi possível clicar em Print | PN={pn} | {e}")



    url_pdf = None

    aba_pdf_extra = None

    limite = time.time() + 20

    while time.time() < limite:

        for handle in [h for h in driver.window_handles if h not in abas_antes]:

            try:

                driver.switch_to.window(handle)

                if "/getPDF" in driver.current_url or ".pdf" in driver.current_url.lower():

                    url_pdf = driver.current_url

                    aba_pdf_extra = handle

                    break

            except Exception:

                pass

        if url_pdf:

            break

        time.sleep(0.5)



    if not url_pdf:

        driver.switch_to.window(aba_frota)

        raise Exception(f"Aba do PDF não identificada em 20s | PN={pn}")



    try:

        if aba_pdf_extra and aba_pdf_extra in driver.window_handles:

            driver.switch_to.window(aba_pdf_extra)

            driver.close()

    except Exception:

        pass



    driver.switch_to.window(aba_frota)



    caminho_pdf = obter_e_salvar_pdf(driver, aba_frota, url_pdf, pasta_downloads, pn, toolbox_user, toolbox_pass)

    if not caminho_pdf or not os.path.exists(caminho_pdf):

        raise Exception(f"Todas as estratégias de download falharam | PN={pn}")



    return caminho_pdf





def recuperar_tela_pesquisa_frota(driver, aba_frota, url_pesquisa, timeout=40):

    """Recupera a tela de busca sem fechar a aba principal."""

    if aba_frota not in driver.window_handles:

        raise Exception("Aba da frota foi fechada.")

    driver.switch_to.window(aba_frota)

    try:

        driver.get(url_pesquisa)

    except TimeoutException:

        pass

    remover_modais_sobrepostos(driver)

    aguardar_frota_pronta(driver, timeout=timeout)



class LocalWorksheet:
    def __init__(self, title, pns):
        self.title = title
        self._properties = {"gridProperties": {"columnCount": 13, "rowCount": len(pns) + 1}}
        self._headers = ["PART NUMBER", "STATUS", "DETALHE_STATUS", "LINK PDF"] + [f"COL_{index}" for index in range(5, 14)]
        self._rows = [self._headers] + [[pn, "", "", ""] + [""] * 9 for pn in pns]

    def get_all_values(self):
        return self._rows

    def row_values(self, row):
        return self._rows[row - 1]

    def resize(self, rows, cols):
        self._properties["gridProperties"] = {"columnCount": cols, "rowCount": rows}

    def update_cell(self, row, column, value):
        while len(self._rows[row - 1]) < column:
            self._rows[row - 1].append("")
        self._rows[row - 1][column - 1] = value
        failure_status = str(value).lower()
        is_terminal_failure = column == 2 and any(
            marker in failure_status
            for marker in ("erro", "não encontrado", "no results", "sem form pss")
        )
        if column == 3 or is_terminal_failure:
            pn = self._rows[row - 1][0]
            match = re.search(r"PDF baixado localmente:\s*(.+)", str(value))
            arquivo = match.group(1).strip() if match else ""
            print(
                "[AERODOC_RESULT] "
                + json.dumps(
                    {"pn": pn, "status": self._rows[row - 1][1], "detail": value, "file": arquivo},
                    ensure_ascii=False,
                ),
                flush=True,
            )


class LocalSpreadsheet:
    def __init__(self, pns):
        # A interface fornece uma única lista local de PNs. As abas do Sheets
        # original não devem duplicar o processamento nessa modalidade.
        self._worksheets = [LocalWorksheet("Local", pns)]

    def worksheets(self):
        return self._worksheets

    def worksheet(self, title):
        for worksheet in self._worksheets:
            if worksheet.title == title:
                return worksheet
        return self._worksheets[0]

    def get_worksheet_by_id(self, _gid):
        return self._worksheets[0]


if LOCAL_ONLY:
    _local_pns = [pn.strip() for pn in os.environ.get("AERODOC_PNS", "").splitlines() if pn.strip()]
    default = lambda scopes=None: (None, None)
    gspread.authorize = lambda _credentials: type(
        "LocalClient", (), {"open_by_url": lambda _self, _url: LocalSpreadsheet(_local_pns)}
    )()
    build = lambda *args, **kwargs: None


try:

    # ===================================================

    # 4. CONEXÃO COM GOOGLE SHEETS E GOOGLE DRIVE

    # ===================================================

    iniciar_etapa(
        "1/5",
        "Preparando execução local" if LOCAL_ONLY else "Conectando à planilha e ao Google Drive",
    )

    log_info(
        "Usando Part Numbers informados na interface; Google Sheets e Drive desativados."
        if LOCAL_ONLY
        else "Solicitando permissão para acessar Google Drive/Sheets..."
    )

    auth.authenticate_user()

    creds, _ = default()



    log_info(
        "Preparando lista local de Part Numbers..."
        if LOCAL_ONLY
        else "Conectando à planilha VERIFICAR REF TECNICA..."
    )

    gc = gspread.authorize(creds)

    planilha = gc.open_by_url(URL_PLANILHA)



    nome_aba_alvo = ABA_POR_AERONAVE.get(FROTA_ALVO)

    if LOCAL_ONLY:
        nomes_abas_alvo = ["Local"]
    elif FROTA_ALVO == "GERAL":

        nomes_abas_alvo = ["Airbus", "Boeing", "Embraer", "Geral"]

    else:

        nomes_abas_alvo = [nome_aba_alvo]



    abas_processamento = []

    for nome_aba in nomes_abas_alvo:

        aba_encontrada = localizar_aba_planilha(

            planilha,

            nome_aba,

            gid=MAPA_GID_ABAS.get(nome_aba),

        )

        if aba_encontrada is not None:

            abas_processamento.append((aba_encontrada.title, aba_encontrada))



    if not abas_processamento:

        raise Exception(f"Nenhuma aba válida encontrada para a seleção '{FROTA_ALVO}'.")



    log_ok(f"Planilha conectada: VERIFICAR REF TECNICA | Abas: {', '.join(nomes for nomes, _ in abas_processamento)}")



    drive_service = build("drive", "v3", credentials=creds)



    limpar_pasta_downloads(PASTA_DOWNLOADS)

    for _, aba_validada in abas_processamento:

        garantir_colunas_planilha(aba_validada, minimo_colunas=MIN_COLUNAS_PLANILHA)



    # ===================================================

    # 5. CREDENCIAIS E INICIALIZAÇÃO DO CHROME

    # ===================================================

    iniciar_etapa("2/5", "Preparando credenciais e navegador")

    log_info("Resgatando credenciais dos Secrets...")

    email = os.environ.get("AERODOC_LATAM_EMAIL") or userdata.get("LATAM_EMAIL")

    senha = os.environ.get("AERODOC_LATAM_PASSWORD") or userdata.get("LATAM_PASSWORD")

    b787_user = os.environ.get("AERODOC_B787_USER") or userdata.get("B787_USER")

    b787_pass = os.environ.get("AERODOC_B787_PASS") or userdata.get("B787_PASS")



    if not email or not senha or not b787_user or not b787_pass:

        raise Exception("Credenciais (LATAM_EMAIL, LATAM_PASSWORD, B787_USER, B787_PASS) não encontradas nos Secrets.")



    token_basic = base64.b64encode(f"{b787_user}:{b787_pass}".encode("utf-8")).decode("utf-8")



    options = webdriver.ChromeOptions()

    chrome_binary = find_chrome()
    if chrome_binary:
        options.binary_location = chrome_binary

    if os.environ.get("AERODOC_HEADLESS", "false").lower() == "true":
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")

    options.add_argument("--disable-dev-shm-usage")

    options.add_argument("--disable-gpu")

    options.add_argument("--window-size=1920,1080")

    options.add_argument("--lang=pt-BR")

    options.page_load_strategy = "eager"

    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    options.add_argument("--disable-sync")

    options.add_argument("--no-first-run")

    options.add_argument("--no-service-autorun")

    options.add_argument("--password-store=basic")

    options.add_argument("--disable-features=ChromeSigninInterceptSetup,BrowserSignin,SyncConsentOptional")

    options.add_argument("--disable-blink-features=AutomationControlled")

    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    options.add_experimental_option("useAutomationExtension", False)



    prefs = {

        "download.default_directory": PASTA_DOWNLOADS,

        "download.prompt_for_download": False,

        "download.directory_upgrade": True,

        "plugins.always_open_pdf_externally": True,

        "profile.default_content_settings.popups": 0,

        "safebrowsing.enabled": True,

    }

    options.add_experimental_option("prefs", prefs)



    driver = webdriver.Chrome(options=options)

    driver.set_page_load_timeout(60)



    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {

        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"

    })



    try:

        driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": PASTA_DOWNLOADS})

    except Exception as e:

        log_alerta(f"Falha ao ativar instrução CDP: {str(e)}")



    wait = WebDriverWait(driver, 20)



    # ===================================================

    # 6. LOGIN CORPORATIVO

    # ===================================================

    iniciar_etapa("3/5", "Realizando login corporativo")

    log_info(f"Acessando URL inicial: {URL_TOOLBOX}")

    driver.get(URL_TOOLBOX)



    log_info("Inserindo e-mail no Google...")

    wait.until(EC.visibility_of_element_located((By.ID, "identifierId"))).send_keys(email + Keys.RETURN)



    log_info("Aguardando transição Google → Microsoft...")

    microsoft_carregou = aguardar_transicao_google_para_microsoft(driver, timeout_total=180)



    if not microsoft_carregou:

        raise Exception("Não foi possível chegar à tela Microsoft após 180 segundos.")



    log_info("Inserindo credenciais na Microsoft...")

    wait.until(EC.visibility_of_element_located((By.ID, "i0116"))).send_keys(email + Keys.RETURN)

    time.sleep(2)

    wait.until(EC.visibility_of_element_located((By.ID, "i0118"))).send_keys(senha)

    time.sleep(1)

    wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()



    # ===================================================

    # 7. AUTENTICAÇÃO DE DOIS FATORES

    # ===================================================

    iniciar_etapa("4/5", "Aguardando aprovação do 2FA")

    log_info("Aguardando aprovação do 2FA...")

    time.sleep(5)



    tempo_decorrido = 0

    toolbox_pronto = False
    ultimo_url_mfa = ""

    ultimo_status_mfa = -5

    while tempo_decorrido < 90:

        if detectar_recusa_mfa(driver):
            print(
                "[AERODOC_MFA_STATUS] status=denied app=Microsoft Authenticator",
                flush=True,
            )
            log_erro("Autenticação do Microsoft Authenticator foi recusada.")
            raise RuntimeError("Autenticação Microsoft recusada pelo usuário.")

        url_atual_mfa = driver.current_url
        if url_atual_mfa != ultimo_url_mfa:
            log_info(f"Navegação após MFA: {url_atual_mfa}")
            ultimo_url_mfa = url_atual_mfa

        # Captura a tela atual antes de qualquer clique para não perder um
        # número transitório. Um novo número substitui o anterior no painel.
        if tempo_decorrido - ultimo_status_mfa >= 5:
            registrar_status_mfa(driver)
            ultimo_status_mfa = tempo_decorrido

        # Algumas contas exibem novamente a tela de escolha do método depois
        # da primeira transição. A seleção precisa ser repetida nesse caso.
        metodo_authenticator_selecionado = selecionar_microsoft_authenticator(driver)
        if metodo_authenticator_selecionado:
            time.sleep(4)

        verificar_e_clicar_profile_chrome(driver)

        try:

            botoes_seguir = driver.find_elements(By.XPATH, "//button[contains(., 'Continue') or contains(., 'Continuar')] | //input[@id='idSIButton9']")

            for btn in botoes_seguir:

                if btn.is_displayed():

                    driver.execute_script("arguments[0].click();", btn)

                    time.sleep(4)

                    break

        except Exception:

            pass



        xpath_latam_toolbox = (
            "//*[@id='h.1703ce369e5de618_12']//a"
            " | //a[contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
            "'latam toolbox')]"
            " | //a[contains(@href, 'toolbox.appslatam.com')]"
        )

        driver.switch_to.default_content()
        link_toolbox = buscar_elemento_em_frames(driver, xpath_latam_toolbox)
        if link_toolbox:
            clicar_e_tratar_destino(driver, link_toolbox, descricao="LATAM TOOLBOX")
            toolbox_pronto = True
        driver.switch_to.default_content()



        if toolbox_pronto:

            print(
                "[AERODOC_MFA_STATUS] status=approved app=Microsoft Authenticator",
                flush=True,
            )
            log_ok("Autenticação Microsoft aprovada; Toolbox carregado.")

            break

        time.sleep(2)

        tempo_decorrido += 2



    if not toolbox_pronto:

        raise Exception("Link LATAM TOOLBOX não carregou após 90 segundos.")



    # ===================================================

    # 8. ABERTURA DO MÓDULO TÉCNICO

    # ===================================================

    iniciar_etapa("5/5", "Abrindo o módulo técnico selecionado")

    verificar_e_clicar_profile_chrome(driver)



    xpath_backup = "//a[contains(., 'Access Backup')] | //*[contains(text(), 'TOOLBOX BACKUP')]"

    btn_access_backup = wait.until(EC.presence_of_element_located((By.XPATH, xpath_backup)))

    clicar_e_tratar_destino(driver, btn_access_backup, descricao="Access Backup")

    time.sleep(4)

    verificar_e_clicar_profile_chrome(driver)



    aba_menu_principal = driver.current_window_handle

    abas_frotas_abertas = {}  # {frota: {"aba": handle, "url_pesquisa": url}}



    def garantir_sessao_frota_selenium(frota_nome):

        if frota_nome in abas_frotas_abertas:

            driver.switch_to.window(abas_frotas_abertas[frota_nome]["aba"])

            return True



        log_info(f"Carregando módulo do servidor para a frota: {frota_nome}...")

        cfg = CONFIG_FROTAS[frota_nome]

        url_base_frota = cfg["url"].split("#", 1)[0].lower()
        xpath_link = (
            f"//a[contains(translate(normalize-space(.), "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{cfg['link_text']}')]"
            f" | //a[contains(translate(@href, "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{url_base_frota}')]"
        )



        try:

            link = None

            limite = time.time() + 25

            while time.time() < limite:

                # O Chrome pode abrir uma aba interna de aviso do perfil
                # (chrome://managed-user-profile-notice/). Ela não contém os
                # Launches; a busca percorre as abas reais do portal.
                for aba in list(driver.window_handles):
                    try:
                        driver.switch_to.window(aba)
                        url_aba = (driver.current_url or "").lower()
                        if url_aba.startswith(("chrome://", "about:", "devtools://")):
                            continue
                        driver.switch_to.default_content()
                        link = buscar_elemento_em_frames(driver, xpath_link)
                        if link:
                            aba_menu_principal = aba
                            break
                    except Exception:
                        continue

                if link:
                    break

                time.sleep(1)



            if not link:

                raise Exception(
                    f"Link de Launch para {frota_nome} não localizado. "
                    f"URL atual: {driver.current_url}"
                )



            url_pesquisa = cfg["url"]



            driver.switch_to.new_window("tab")

            aba_modulo = driver.current_window_handle



            driver.execute_cdp_cmd("Network.enable", {})

            driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": {"Authorization": f"Basic {token_basic}"}})



            try:

                driver.set_page_load_timeout(45)

                driver.get(url_pesquisa)

            except TimeoutException:

                pass

            finally:

                try:

                    driver.set_page_load_timeout(60)

                except Exception:

                    pass



            time.sleep(3)

            aceitar_termos_b787(driver)

            remover_modais_sobrepostos(driver)

            aguardar_frota_pronta(driver, timeout=45)



            abas_frotas_abertas[frota_nome] = {"aba": aba_modulo, "url_pesquisa": url_pesquisa}

            log_ok(f"Sessão da frota {frota_nome} inicializada.")

            return True



        except Exception as e:

            log_erro(f"Falha ao carregar sessão da frota {frota_nome}: {str(e)}")

            return False



    # ===================================================

    # 9. PROCESSAMENTO DOS PART NUMBERS

    # ===================================================

    iniciar_etapa("PROCESSAMENTO", f"Lendo PNs da aba {', '.join(nomes for nomes, _ in abas_processamento)}")



    frotas_para_busca = list(CONFIG_FROTAS.keys()) if FROTA_ALVO == "GERAL" else [FROTA_ALVO]



    total_processados = 0

    total_sucesso = 0

    total_nao_encontrado = 0

    total_erro = 0



    for nome_aba_atual, aba in abas_processamento:

        log_info(f"Lendo itens da aba '{nome_aba_atual}'...")

        registros = aba.get_all_values()

        if not registros:

            log_alerta(f"Aba '{nome_aba_atual}' não contém dados.")

            continue



        mapa_colunas = obter_mapeamento_colunas(registros)

        coluna_pn = mapa_colunas["pn"]

        coluna_status = mapa_colunas["status"]

        coluna_detalhe_status = mapa_colunas["detalhe_status"]

        coluna_link_drive = mapa_colunas["link_drive"]



        for indice, linha in enumerate(registros[1:], start=2):

            pn = obter_valor_linha(linha, coluna_pn)

            status_atual = obter_valor_linha(linha, coluna_status)



            if not pn or status_atual.strip() != "":

                continue



            total_processados += 1

            print(f"\n[PN {total_processados}] {pn} | Aba: {nome_aba_atual} | Linha: {indice}")



            sucesso_no_processamento = False

            teve_erro = False



            for frota in frotas_para_busca:

                if sucesso_no_processamento:

                    break



                if not garantir_sessao_frota_selenium(frota):

                    continue



                info_sessao = abas_frotas_abertas[frota]

                aba_frota = info_sessao["aba"]

                url_pesquisa_frota = info_sessao["url_pesquisa"]



                for tentativa_pn in range(1, MAX_TENTATIVAS_PN + 1):

                    try:

                        if aba_frota not in driver.window_handles:

                            raise Exception(f"Aba da frota {frota} foi fechada.")



                        driver.switch_to.window(aba_frota)

                        remover_modais_sobrepostos(driver)



                        try:

                            obter_campo_busca_frota(driver, timeout=12)

                        except TimeoutException:

                            recuperar_tela_pesquisa_frota(driver, aba_frota, url_pesquisa_frota, timeout=40)



                        pesquisar_pn_frota(driver, pn)

                        resultado = aguardar_resultado_pesquisa(driver, pn, timeout=TEMPO_ESPERA_RESULTADO)



                        if resultado["status"] == "nao_encontrado":

                            log_alerta(f"PN={pn} não encontrado na frota {frota}.")

                            break  # tenta próxima frota



                        aba_documento = clicar_hyperlink_reference(driver, resultado["elemento"], pn)

                        remover_modais_sobrepostos(driver)



                        caminho_final = gerar_pdf_do_documento(

                            driver, PASTA_DOWNLOADS, aba_frota, pn, b787_user, b787_pass

                        )



                        if LOCAL_ONLY:
                            link_drive = ""
                            log_ok(f"PDF baixado localmente | PN={pn} | Frota={frota}")
                        else:
                            file_metadata = {

                                "name": f"{nome_seguro(pn)}_{frota}.pdf",

                                "parents": [ID_PASTA_DRIVE],

                            }

                            media = MediaFileUpload(caminho_final, mimetype="application/pdf")

                            arquivo_drive = drive_service.files().create(

                                body=file_metadata,

                                media_body=media,

                                fields="id, webViewLink"

                            ).execute()



                            link_drive = arquivo_drive.get("webViewLink", "")



                            log_ok(f"PDF baixado e anexado | PN={pn} | Frota={frota}")

                        atualizar_celula_segura(aba, indice, coluna_status, f"PDF Extraido ({frota})")

                        detalhe_local = f"PDF baixado localmente: {caminho_final} ({frota})"
                        detalhe_drive = f"PDF anexado na pasta do Drive ({frota})"
                        atualizar_celula_segura(aba, indice, coluna_detalhe_status, detalhe_local if LOCAL_ONLY else detalhe_drive)

                        atualizar_celula_segura(aba, indice, coluna_link_drive, link_drive)



                        total_sucesso += 1



                        try:

                            if not LOCAL_ONLY and os.path.exists(caminho_final):

                                os.remove(caminho_final)

                        except Exception:

                            pass



                        # Retorna para tela de pesquisa

                        try:

                            driver.switch_to.window(aba_frota)

                            obter_campo_busca_frota(driver, timeout=5)

                        except Exception:

                            recuperar_tela_pesquisa_frota(driver, aba_frota, url_pesquisa_frota, timeout=30)



                        sucesso_no_processamento = True

                        break



                    except Exception as e:

                        erro_texto = str(e)

                        log_erro(f"Erro PN={pn} | Frota={frota} | Tentativa={tentativa_pn}/{MAX_TENTATIVAS_PN} | {erro_texto}")

                        logger.error(traceback.format_exc())

                        teve_erro = True

                        if tentativa_pn < MAX_TENTATIVAS_PN:

                            try:

                                recuperar_tela_pesquisa_frota(driver, aba_frota, url_pesquisa_frota, timeout=40)

                                time.sleep(3)

                            except Exception as erro_rec:

                                log_erro(f"Falha na recuperação | PN={pn} | {erro_rec}")



            if not sucesso_no_processamento:

                if teve_erro:

                    atualizar_celula_segura(aba, indice, coluna_status, "Erro no processamento")

                    atualizar_celula_segura(aba, indice, coluna_detalhe_status, erro_texto[:500] if teve_erro else "")

                    total_erro += 1

                else:

                    msg = "Não encontrado em nenhuma frota" if FROTA_ALVO == "GERAL" else "No Results to Display"

                    atualizar_celula_segura(aba, indice, coluna_status, msg)

                    atualizar_celula_segura(aba, indice, coluna_detalhe_status, "PN não localizado no módulo selecionado")

                    total_nao_encontrado += 1



    print("\n" + "=" * 64)

    print("AUTOMAÇÃO CONCLUÍDA")

    print("=" * 64)

    print(f"Processados : {total_processados}")

    print(f"Sucesso     : {total_sucesso}")

    print(f"Não encontrados: {total_nao_encontrado}")

    print(f"Erros       : {total_erro}")

    print("=" * 64)



except KeyboardInterrupt:

    log_alerta("Execução interrompida manualmente pelo usuário.")



except Exception as e:

    log_erro(f"Erro crítico na execução: {str(e)}")

    logger.error(traceback.format_exc())



finally:

    exibir_resumo_logs()

    log_info("Encerrando o navegador...")

    try:

        navegador = globals().get("driver")

        if navegador is not None and getattr(navegador, "session_id", None):

            navegador.quit()

    except (WebDriverException, ConnectionError):

        # O navegador pode já ter sido encerrado após uma interrupção manual.

        pass

    except Exception as erro_fechamento:

        logger.debug(f"Falha não crítica ao encerrar o navegador: {erro_fechamento}")


