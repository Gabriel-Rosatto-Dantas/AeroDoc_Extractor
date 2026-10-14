# AeroDoc Extractor

Aplicativo desktop para consultar e baixar referências técnicas localmente. A pessoa seleciona o módulo, informa os Part Numbers, acompanha o pipeline e aprova o MFA pelo painel. Os navegadores são executados em segundo plano.

## Módulos disponíveis

- **Airbus**: consulta o portal Airbus e baixa os PDFs encontrados.
- **Boeing**: consulta o Boeing Toolbox e baixa o documento técnico selecionado.
- **MXI**: autentica no Maintenix, pesquisa os PNs e baixa formulários PDF.
- **Toolbox**: autentica no portal interno, inicializa todas as frotas automaticamente e pesquisa cada PN.

Google Sheets e Google Drive não fazem parte do fluxo da interface. Os PNs são informados na aba **Execução** e os arquivos são salvos em uma pasta local.

## Estrutura

```text
AeroDoc Extractor/
├── main.py                         # ponto de entrada
├── aerodoc_gui.py                  # interface PySide6 e pipeline visual
├── aerodoc/modules/                # executores testados
│   ├── airbus.py
│   ├── boeing.py
│   ├── mxi.py
│   ├── platform_utils.py
│   └── toolbox.py
├── aerodoc_config.example.json     # configuração da interface
├── boeing_config.example.ini       # referência opcional do Boeing
├── mxi_config.example.ini          # referência do MXI
├── requirements.txt
├── downloads/                       # PDFs locais gerados
└── logs/                            # logs das execuções
```

Perfis do Chrome, caches, screenshots temporários, notebooks antigos e repositórios Git internos dos subprojetos não fazem parte da distribuição.

## Instalação

Requer Python 3.10 ou superior e Google Chrome.

```bash
python -m venv .venv
source .venv/bin/activate                 # macOS/Linux
.venv\Scripts\Activate.ps1               # Windows PowerShell
python -m pip install -r requirements.txt
python main.py
```

No Windows, macOS ou Linux, selecione o sistema operacional na aba **Configuração**. A configuração e as credenciais são salvas localmente na pasta de dados do usuário. O arquivo `aerodoc_config.json` da raiz é apenas um legado local e não deve ser compartilhado.

## Configuração

1. Informe os acessos globais e os acessos específicos do módulo.
2. Selecione a pasta de download.
3. Informe o caminho do `mxi_config.ini` quando usar o MXI.
4. Clique em **Salvar configuração**.
5. Na aba **Execução**, selecione o módulo e informe um PN por linha.
6. Acompanhe login, MFA, consulta, verificação, download e resultado na aba **Monitoramento**.

Os arquivos `boeing_config.example.ini` e `mxi_config.example.ini` são modelos. Copie-os para `boeing_config.ini` ou `mxi_config.ini` somente quando precisar configurar uma execução direta. Nunca compartilhe esses arquivos preenchidos.

## Saídas e diagnóstico

Os PDFs ficam em `downloads/` por padrão. Os logs ficam em `logs/`, separados por módulo. O Toolbox usa a frota `GERAL` e percorre todas as frotas disponíveis. Durante o MFA, o número de aprovação aparece em destaque na interface; a aprovação continua sendo feita no Microsoft Authenticator, PingID ou outro autenticador configurado para a conta.

Para validar a instalação sem iniciar uma automação:

```bash
python -m py_compile aerodoc_gui.py aerodoc/modules/*.py
```

## Segurança

Não versione senhas, tokens, credenciais Google, URLs privadas, PDFs, logs ou perfis de navegador. O `.gitignore` já exclui esses artefatos. As credenciais devem permanecer somente na máquina do usuário.
