from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aerodoc.modules.platform_utils import PLATFORMS, host_platform


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "aerodoc" / "modules"
LEGACY_CONFIG_FILE = ROOT / "aerodoc_config.json"


def user_config_file() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "AeroDoc Extractor" / "aerodoc_config.json"


CONFIG_FILE = user_config_file()


@dataclass(frozen=True)
class ModuleSpec:
    key: str
    label: str
    command: tuple[str, ...]
    cwd: Path


MODULES = {
    "airbus": ModuleSpec(
        "airbus",
        "Referência Técnica Airbus",
        (sys.executable, "airbus.py"),
        MODULE_DIR,
    ),
    "boeing": ModuleSpec(
        "boeing",
        "Referência Técnica Boeing",
        (sys.executable, "boeing.py"),
        MODULE_DIR,
    ),
    "mxi": ModuleSpec(
        "mxi",
        "Referência Técnica MXI",
        (sys.executable, "mxi.py"),
        MODULE_DIR,
    ),
    "toolbox": ModuleSpec(
        "toolbox",
        "Referência Técnica Toolbox",
        (sys.executable, "toolbox.py"),
        MODULE_DIR,
    ),
}


PIPELINE_STEPS = [
    ("start", "Script iniciado"),
    ("login", "Login"),
    ("mfa", "Autenticação de dois fatores"),
    ("query", "Consulta do material"),
    ("verify", "Verificação do PDF"),
    ("download", "Download do PDF"),
    ("done", "Concluído"),
]

MODULE_HELP = {
    "airbus": "Consulta documentos técnicos Airbus para os Part Numbers informados.",
    "boeing": "Consulta documentos técnicos Boeing usando seus acessos LATAM.",
    "mxi": "Consulta formulários no Maintenix. Confira o arquivo de configuração MXI.",
    "toolbox": "Consulta os Part Numbers em todas as frotas disponíveis.",
}


APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #F4F7FB;
    color: #101828;
    font-size: 10pt;
}
QLabel { background: transparent; }
QLabel#pageTitle { color: #101828; font-size: 22pt; font-weight: 700; }
QLabel#pageSubtitle, QLabel[role="hint"] { color: #475467; }
QLabel#sectionIntro { color: #344054; font-size: 11pt; font-weight: 600; }
QLabel#helperText { color: #475467; }
QLabel#stepSummary { color: #1849A9; font-weight: 700; }
QLabel#stepSummary[tone="success"] { color: #067647; }
QLabel#stepSummary[tone="error"] { color: #B42318; }
QLabel#resultSummary { color: #344054; font-weight: 600; }
QWidget#headerPanel {
    background: #FFFFFF;
    border: 1px solid #D0D5DD;
    border-left: 5px solid #155EEF;
    border-radius: 10px;
}
QGroupBox {
    background: #FFFFFF;
    border: 1px solid #D0D5DD;
    border-radius: 9px;
    margin-top: 13px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #344054;
}
QLineEdit, QComboBox, QPlainTextEdit, QTableWidget, QListWidget {
    background: #FFFFFF;
    border: 1px solid #98A2B3;
    border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: #D1E0FF;
    selection-color: #101828;
}
QLineEdit, QComboBox { min-height: 32px; padding: 4px 9px; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus,
QTableWidget:focus, QListWidget:focus {
    border: 2px solid #155EEF;
}
QComboBox::drop-down { border: 0; width: 28px; }
QPushButton {
    background: #FFFFFF;
    color: #344054;
    border: 1px solid #98A2B3;
    border-radius: 6px;
    min-height: 20px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover { background: #EFF4FF; border-color: #155EEF; }
QPushButton:pressed { background: #D1E0FF; }
QPushButton:focus { border: 2px solid #155EEF; }
QPushButton:disabled { color: #667085; background: #EAECF0; border-color: #D0D5DD; }
QPushButton#primaryAction { background: #155EEF; color: #FFFFFF; border-color: #155EEF; }
QPushButton#primaryAction:hover { background: #004EEB; border-color: #004EEB; }
QPushButton#primaryAction:disabled { background: #A6C3FF; border-color: #A6C3FF; color: #FFFFFF; }
QPushButton#dangerAction { color: #B42318; border-color: #FDA29B; }
QPushButton#dangerAction:hover { background: #FEF3F2; }
QTabWidget::pane { border: 1px solid #D0D5DD; border-radius: 8px; background: #F4F7FB; top: -1px; }
QTabBar::tab {
    background: #EAECF0;
    color: #475467;
    border: 1px solid #D0D5DD;
    border-bottom: 0;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    padding: 10px 18px;
    margin-right: 4px;
    min-width: 105px;
}
QTabBar::tab:selected { background: #FFFFFF; color: #155EEF; font-weight: 700; }
QTabBar::tab:focus { border: 2px solid #155EEF; }
QHeaderView::section {
    background: #EFF4FF;
    color: #344054;
    padding: 8px;
    border: 0;
    border-bottom: 1px solid #D0D5DD;
    font-weight: 700;
}
QTableWidget { gridline-color: #EAECF0; alternate-background-color: #F9FAFB; }
QTableWidget::item { padding: 6px; }
QListWidget { padding: 6px; }
QListWidget::item { padding: 3px 7px; border-radius: 5px; min-height: 18px; }
QListWidget::item:selected { background: #EFF4FF; color: #1849A9; font-weight: 700; }
QProgressBar {
    background: #EAECF0;
    border: 0;
    border-radius: 5px;
    min-width: 150px;
    max-width: 220px;
    min-height: 10px;
    max-height: 10px;
}
QProgressBar::chunk { background: #155EEF; border-radius: 5px; }
QProgressBar#pipelineProgress { max-width: 16777215px; min-width: 80px; min-height: 12px; max-height: 12px; }
QLabel[tone="muted"] { color: #475467; }
QLabel[tone="success"] { color: #067647; font-weight: 600; }
QLabel[tone="error"] { color: #B42318; font-weight: 600; }
QLabel[tone="info"] { color: #1849A9; font-weight: 600; }
QLabel#currentItem { color: #344054; font-weight: 700; }
QLabel#approvalNumber {
    color: #1849A9;
    background: #EFF4FF;
    border: 2px solid #84ADFF;
    border-radius: 10px;
    padding: 8px;
    font-size: 30pt;
    font-weight: 700;
}
QLabel#approvalNumber[state="approved"] {
    color: #067647;
    background: #ECFDF3;
    border-color: #6CE9A6;
}
QLabel#approvalNumber[state="denied"] {
    color: #B42318;
    background: #FEF3F2;
    border-color: #FDA29B;
}
QLabel#approvalInstruction { color: #344054; padding: 4px; }
QFrame#sectionDivider { color: #D0D5DD; }
QPlainTextEdit#logView {
    background: #101828;
    color: #F2F4F7;
    border: 1px solid #344054;
    font-family: monospace;
}
"""


def read_config() -> dict:
    config_path = CONFIG_FILE if CONFIG_FILE.exists() else LEGACY_CONFIG_FILE
    if not config_path.exists():
        return {
            "latam_email": "",
            "latam_password": "",
            "airbus_user": "",
            "airbus_password": "",
            "toolbox_user": "",
            "toolbox_password": "",
            "mxi_user": "",
            "mxi_password": "",
            "mxi_config": str(ROOT / "mxi_config.ini"),
            "download_dir": str(ROOT / "downloads"),
            "platform": host_platform(),
        }
    try:
        values = json.loads(config_path.read_text(encoding="utf-8"))
        mxi_config = Path(str(values.get("mxi_config", "")))
        if not mxi_config.exists() and (ROOT / "mxi_config.ini").exists():
            values["mxi_config"] = str(ROOT / "mxi_config.ini")
        return values
    except (OSError, json.JSONDecodeError):
        return {}


def write_config(values: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(values, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.process: QProcess | None = None
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self.config = read_config()
        self.step_items: dict[str, QListWidgetItem] = {}
        self.pipeline_message = "Pronto para iniciar"
        self.pipeline_tone = "muted"
        self.current_pn = "—"
        self.setWindowTitle("AeroDoc Extractor")
        self.resize(1180, 760)
        self.setMinimumSize(880, 720)
        self.setStyleSheet(APP_STYLESHEET)
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 16, 18, 18)
        root_layout.setSpacing(14)

        header = QWidget()
        header.setObjectName("headerPanel")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 13, 18, 13)
        title = QLabel("AeroDoc Extractor")
        title.setObjectName("pageTitle")
        title.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        subtitle = QLabel(
            "Configure uma vez, escolha o que consultar e acompanhe cada etapa."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        self.page_subtitle = subtitle
        root_layout.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._build_settings_tab(), "1  Configurar")
        self.tabs.addTab(self._build_execution_tab(), "2  Executar")
        self.tabs.addTab(self._build_monitor_tab(), "3  Acompanhar")
        self.tabs.setTabToolTip(0, "Salve seus acessos e escolha onde guardar os PDFs")
        self.tabs.setTabToolTip(1, "Escolha um módulo e informe os Part Numbers")
        self.tabs.setTabToolTip(2, "Veja o progresso, confirmação de acesso e resultados")
        self.tabs.currentChanged.connect(self._update_page_subtitle)
        root_layout.addWidget(self.tabs)

    def _update_page_subtitle(self, index: int) -> None:
        guidance = {
            0: "Passo 1 de 2: informe os acessos que serão usados e salve a configuração.",
            1: "Passo 2 de 2: escolha o módulo, cole os Part Numbers e inicie a consulta.",
            2: "Acompanhe o progresso, aprove o acesso se solicitado e confira os PDFs encontrados.",
        }
        self.page_subtitle.setText(guidance.get(index, "AeroDoc Extractor"))

    def _build_settings_tab(self) -> QWidget:
        page = QWidget()
        page.setMinimumWidth(0)
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        intro = QLabel(
            "Comece por aqui: informe os acessos necessários e escolha onde salvar os PDFs. "
            "Depois, clique em Salvar configuração. Os dados ficam somente neste computador."
        )
        intro.setObjectName("sectionIntro")
        intro.setProperty("role", "hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        access_box = QGroupBox("Acessos gerais")
        access_layout = QFormLayout(access_box)
        access_layout.setVerticalSpacing(9)
        self.email = QLineEdit()
        self.email.setPlaceholderText("usuario@latam.com")
        self.email.setAccessibleName("E-mail LATAM")
        access_layout.addRow("E-mail LATAM:", self.email)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Senha LATAM")
        self.password.setAccessibleName("Senha LATAM")
        access_layout.addRow("Senha LATAM:", self.password)

        self.platform_combo = QComboBox()
        for key, label in PLATFORMS:
            self.platform_combo.addItem(label, key)
        access_layout.addRow("Sistema operacional:", self.platform_combo)
        platform_hint = QLabel(
            "Escolha o sistema onde o executável será executado. "
            "A escolha define atalhos e caminhos compatíveis."
        )
        platform_hint.setProperty("role", "hint")
        platform_hint.setWordWrap(True)
        access_layout.addRow("", platform_hint)
        layout.addWidget(access_box)

        module_box = QGroupBox("Acessos específicos dos módulos")
        module_layout = QGridLayout(module_box)
        module_layout.setVerticalSpacing(8)
        module_layout.setHorizontalSpacing(12)
        module_layout.addWidget(QLabel("Portal"), 0, 0)
        module_layout.addWidget(QLabel("Nome de usuário"), 0, 1)
        module_layout.addWidget(QLabel("Senha do portal"), 0, 2)

        self.airbus_user = QLineEdit()
        self.airbus_user.setPlaceholderText("Usuário Airbus")
        self.airbus_user.setAccessibleName("Nome de usuário Airbus")
        self.airbus_password = QLineEdit()
        self.airbus_password.setPlaceholderText("Senha Airbus")
        self.airbus_password.setAccessibleName("Senha Airbus")
        self.airbus_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.toolbox_user = QLineEdit()
        self.toolbox_user.setPlaceholderText("Usuário Toolbox")
        self.toolbox_user.setAccessibleName("Nome de usuário Toolbox")
        self.toolbox_password = QLineEdit()
        self.toolbox_password.setPlaceholderText("Senha Toolbox")
        self.toolbox_password.setAccessibleName("Senha Toolbox")
        self.toolbox_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.mxi_user = QLineEdit()
        self.mxi_user.setPlaceholderText("Usuário MXI")
        self.mxi_user.setAccessibleName("Nome de usuário MXI")
        self.mxi_password = QLineEdit()
        self.mxi_password.setPlaceholderText("Senha MXI")
        self.mxi_password.setAccessibleName("Senha MXI")
        self.mxi_password.setEchoMode(QLineEdit.EchoMode.Password)

        for row, label, user_field, password_field in [
            (1, "Airbus", self.airbus_user, self.airbus_password),
            (2, "Toolbox", self.toolbox_user, self.toolbox_password),
            (3, "MXI", self.mxi_user, self.mxi_password),
        ]:
            module_layout.addWidget(QLabel(label), row, 0)
            module_layout.addWidget(user_field, row, 1)
            module_layout.addWidget(password_field, row, 2)
        module_hint = QLabel(
            "Preencha os acessos dos portais que pretende usar. Os demais podem ficar vazios."
        )
        module_hint.setProperty("role", "hint")
        module_hint.setWordWrap(True)
        module_layout.addWidget(module_hint, 4, 0, 1, 3)
        layout.addWidget(module_box)

        integration_box = QGroupBox("Configurações dos módulos")
        integration_layout = QFormLayout(integration_box)
        integration_layout.setVerticalSpacing(9)
        mxi_config_row = QHBoxLayout()
        self.mxi_config = QLineEdit()
        self.mxi_config.setPlaceholderText("config.ini do MXI")
        mxi_browse = QPushButton("Procurar arquivo…")
        mxi_browse.setAccessibleName("Procurar arquivo de configuração MXI")
        mxi_browse.clicked.connect(self._choose_mxi_config)
        mxi_config_row.addWidget(self.mxi_config)
        mxi_config_row.addWidget(mxi_browse)
        integration_layout.addRow("Configuração MXI:", mxi_config_row)
        layout.addWidget(integration_box)

        storage_box = QGroupBox("Pasta de saída")
        storage_layout = QFormLayout(storage_box)
        storage_layout.setVerticalSpacing(9)
        download_row = QHBoxLayout()
        self.download_dir = QLineEdit()
        download_browse = QPushButton("Escolher pasta…")
        download_browse.setAccessibleName("Escolher pasta de destino dos PDFs")
        download_browse.clicked.connect(self._choose_download_dir)
        download_row.addWidget(self.download_dir)
        download_row.addWidget(download_browse)
        storage_layout.addRow("Downloads locais:", download_row)
        storage_hint = QLabel("Os arquivos baixados serão salvos nesta pasta.")
        storage_hint.setProperty("role", "hint")
        storage_layout.addRow("", storage_hint)
        layout.addWidget(storage_box)

        save_row = QHBoxLayout()
        save_button = QPushButton("Salvar configuração")
        save_button.setObjectName("primaryAction")
        save_button.setAccessibleName("Salvar configuração local")
        save_button.setToolTip("Salvar os acessos e caminhos nesta máquina")
        save_button.setDefault(True)
        save_button.clicked.connect(self.save_configuration)
        save_row.addWidget(save_button)
        self.config_status = QLabel("Nenhuma alteração pendente")
        self.config_status.setProperty("tone", "muted")
        self.config_status.setWordWrap(True)
        save_row.addWidget(self.config_status)
        save_row.addStretch()
        layout.addLayout(save_row)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setObjectName("settingsScrollArea")
        scroll.setAccessibleName("Configuração da aplicação")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def _build_execution_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        execution_box = QGroupBox("1. Onde você quer consultar?")
        execution_layout = QVBoxLayout(execution_box)
        self.module_combo = QComboBox()
        self.module_combo.setAccessibleName("Automação a executar")
        for key, spec in MODULES.items():
            self.module_combo.addItem(spec.label, key)
        self.module_combo.currentIndexChanged.connect(self._module_changed)
        execution_layout.addWidget(QLabel("Selecione o portal técnico:"))
        execution_layout.addWidget(self.module_combo)
        self.module_help = QLabel()
        self.module_help.setObjectName("helperText")
        self.module_help.setWordWrap(True)
        execution_layout.addWidget(self.module_help)
        self._update_module_help()

        layout.addWidget(execution_box)

        pn_box = QGroupBox("2. Quais Part Numbers você precisa?")
        pn_layout = QVBoxLayout(pn_box)
        pn_instructions = QLabel(
            "Cole ou digite um código por linha. Você pode copiar a lista direto de uma planilha."
        )
        pn_instructions.setProperty("role", "hint")
        pn_instructions.setWordWrap(True)
        pn_layout.addWidget(pn_instructions)
        self.pn_input = QPlainTextEdit()
        self.pn_input.setPlaceholderText("Exemplo:\nABC123\nDEF456")
        self.pn_input.setAccessibleName("Part Numbers, um por linha")
        self.pn_input.setToolTip("Informe um Part Number por linha. Linhas vazias serão ignoradas.")
        self.pn_input.setMinimumHeight(120)
        self.pn_input.textChanged.connect(self._update_pn_count)
        pn_layout.addWidget(self.pn_input)
        pn_footer = QHBoxLayout()
        self.pn_count = QLabel("0 Part Numbers informados")
        self.pn_count.setProperty("tone", "muted")
        pn_footer.addWidget(self.pn_count)
        pn_footer.addStretch()
        self.clear_pn_button = QPushButton("Limpar lista")
        self.clear_pn_button.setAccessibleName("Limpar lista de Part Numbers")
        self.clear_pn_button.setEnabled(False)
        self.clear_pn_button.clicked.connect(self.pn_input.clear)
        pn_footer.addWidget(self.clear_pn_button)
        pn_layout.addLayout(pn_footer)
        layout.addWidget(pn_box, 1)

        actions = QHBoxLayout()
        self.start_button = QPushButton("Iniciar consulta e download")
        self.start_button.setObjectName("primaryAction")
        self.start_button.setAccessibleName("Iniciar automação selecionada")
        self.start_button.clicked.connect(self.start_automation)
        self.stop_button = QPushButton("Interromper")
        self.stop_button.setObjectName("dangerAction")
        self.stop_button.setAccessibleName("Interromper automação em execução")
        self.stop_button.setToolTip("Solicita a interrupção da automação atual")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_automation)
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addStretch()
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        actions.addWidget(self.progress)
        layout.addLayout(actions)
        self.execution_status = QLabel("Pronto. Escolha um portal e informe pelo menos um Part Number.")
        self.execution_status.setProperty("tone", "muted")
        self.execution_status.setWordWrap(True)
        layout.addWidget(self.execution_status)
        return page

    def _update_module_help(self) -> None:
        key = self.module_combo.currentData()
        self.module_help.setText(MODULE_HELP.get(key, "Selecione um portal para ver mais informações."))

    def _build_monitor_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self._build_pipeline_box(), 3)
        top.addWidget(self._build_mfa_box(), 2)
        layout.addLayout(top, 4)

        result_box = QGroupBox("Resultados dos Part Numbers")
        result_layout = QVBoxLayout(result_box)
        result_header = QHBoxLayout()
        result_intro = QLabel("Documentos encontrados e situação de cada código:")
        result_intro.setProperty("role", "hint")
        result_header.addWidget(result_intro)
        result_header.addStretch()
        self.results_summary = QLabel("Aguardando consulta")
        self.results_summary.setObjectName("resultSummary")
        result_header.addWidget(self.results_summary)
        result_layout.addLayout(result_header)
        self.results_empty = QLabel(
            "Ainda não há resultados. Inicie uma consulta para ver aqui os documentos encontrados."
        )
        self.results_empty.setObjectName("helperText")
        self.results_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_empty.setWordWrap(True)
        result_layout.addWidget(self.results_empty)
        self.results = QTableWidget(0, 4)
        self.results.setAccessibleName("Resultados dos Part Numbers")
        self.results.setHorizontalHeaderLabels(["Part Number", "Status", "Detalhe", "Arquivo local"])
        self.results.setAlternatingRowColors(True)
        self.results.setWordWrap(True)
        self.results.verticalHeader().setVisible(False)
        self.results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results.setMinimumHeight(120)
        self.results.horizontalHeader().setStretchLastSection(True)
        self.results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        result_layout.addWidget(self.results)
        layout.addWidget(result_box, 3)

        log_controls = QHBoxLayout()
        self.log_toggle = QPushButton("Mostrar detalhes técnicos")
        self.log_toggle.setCheckable(True)
        self.log_toggle.setAccessibleName("Mostrar ou ocultar o log técnico")
        self.log_toggle.toggled.connect(self._toggle_log)
        log_controls.addWidget(self.log_toggle)
        log_controls.addStretch()
        layout.addLayout(log_controls)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setAccessibleName("Log da execução")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(100)
        self.log_view.setVisible(False)
        layout.addWidget(self.log_view, 1)
        return page

    def _build_pipeline_box(self) -> QGroupBox:
        box = QGroupBox("Progresso da consulta")
        box.setMinimumHeight(330)
        layout = QVBoxLayout(box)
        step_header = QHBoxLayout()
        self.step_summary = QLabel("Pronto para iniciar")
        self.step_summary.setObjectName("stepSummary")
        step_header.addWidget(self.step_summary)
        step_header.addStretch()
        self.step_count = QLabel(f"0 de {len(PIPELINE_STEPS)} etapas")
        self.step_count.setProperty("tone", "muted")
        step_header.addWidget(self.step_count)
        layout.addLayout(step_header)
        self.pipeline_progress = QProgressBar()
        self.pipeline_progress.setObjectName("pipelineProgress")
        self.pipeline_progress.setRange(0, len(PIPELINE_STEPS))
        self.pipeline_progress.setValue(0)
        self.pipeline_progress.setTextVisible(False)
        layout.addWidget(self.pipeline_progress)
        self.pipeline = QListWidget()
        self.pipeline.setAccessibleName("Etapas da consulta")
        self.pipeline.setMinimumHeight(175)
        for key, label in PIPELINE_STEPS:
            item = QListWidgetItem(f"○  {label}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{label}: aguardando")
            self.pipeline.addItem(item)
            self.step_items[key] = item
        layout.addWidget(self.pipeline)
        return box

    def _build_mfa_box(self) -> QGroupBox:
        mfa_box = QGroupBox("Confirmação de acesso")
        mfa_box.setMinimumHeight(330)
        mfa_layout = QVBoxLayout(mfa_box)
        mfa_intro = QLabel(
            "Alguns portais pedem uma confirmação extra. Se aparecer, abra o autenticador da LATAM."
        )
        mfa_intro.setProperty("role", "hint")
        mfa_intro.setWordWrap(True)
        mfa_layout.addWidget(mfa_intro)
        self.mfa_number = QLabel("—")
        self.mfa_number.setObjectName("approvalNumber")
        self.mfa_number.setAccessibleName("Número de aprovação MFA")
        self.mfa_number.setProperty("state", "pending")
        self.mfa_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mfa_number.setMinimumHeight(112)
        self.mfa_number.setWordWrap(True)
        mfa_layout.addWidget(self.mfa_number)
        self.mfa_state = QLabel("Aguardando solicitação de aprovação")
        self.mfa_state.setProperty("tone", "muted")
        self.mfa_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mfa_layout.addWidget(self.mfa_state)
        self.mfa_instruction = QLabel(
            "Quando necessário, o número aparecerá aqui. Não digite o número; aprove a solicitação no aplicativo."
        )
        self.mfa_instruction.setObjectName("approvalInstruction")
        self.mfa_instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mfa_instruction.setWordWrap(True)
        mfa_layout.addWidget(self.mfa_instruction)
        mfa_layout.addStretch()
        return mfa_box

    def _toggle_log(self, visible: bool) -> None:
        self.log_view.setVisible(visible)
        self.log_toggle.setText(
            "Ocultar detalhes técnicos" if visible else "Mostrar detalhes técnicos"
        )

    def _load_values(self) -> None:
        values = self.config
        self.mxi_config.setText(values.get("mxi_config", str(ROOT / "mxi_config.ini")))
        self.email.setText(values.get("latam_email", ""))
        self.password.setText(values.get("latam_password", ""))
        self.airbus_user.setText(values.get("airbus_user", ""))
        self.airbus_password.setText(values.get("airbus_password", ""))
        self.toolbox_user.setText(values.get("toolbox_user", ""))
        self.toolbox_password.setText(values.get("toolbox_password", ""))
        self.mxi_user.setText(values.get("mxi_user", ""))
        self.mxi_password.setText(values.get("mxi_password", ""))
        self.download_dir.setText(values.get("download_dir", str(ROOT / "downloads")))
        platform = values.get("platform", host_platform())
        self.platform_combo.setCurrentIndex(max(0, self.platform_combo.findData(platform)))
        self._update_pn_count()

    def _set_feedback(self, label: QLabel, text: str, tone: str = "muted") -> None:
        label.setText(text)
        label.setProperty("tone", tone)
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()

    def _set_pipeline_status(self, message: str, tone: str = "muted") -> None:
        self.pipeline_message = message
        self.pipeline_tone = tone
        if self.current_pn != "—":
            message = f"{message}  ·  Part Number atual: {self.current_pn}"
        self._set_feedback(self.step_summary, message, tone)

    def _set_current_pn(self, pn: str) -> None:
        self.current_pn = pn
        self._set_pipeline_status(self.pipeline_message, self.pipeline_tone)

    def _set_mfa_state(self, text: str, state: str, instruction: str) -> None:
        self.mfa_number.setText(text)
        self.mfa_number.setProperty("state", state)
        self.mfa_number.style().unpolish(self.mfa_number)
        self.mfa_number.style().polish(self.mfa_number)
        self.mfa_number.update()
        state_messages = {
            "pending": (
                "Aguardando solicitação de aprovação"
                if text == "—"
                else "Aguardando aprovação no aplicativo"
            ),
            "approved": "Aprovação confirmada",
            "denied": "Aprovação recusada ou não concluída",
        }
        tone = {"pending": "info", "approved": "success", "denied": "error"}.get(
            state,
            "muted",
        )
        self._set_feedback(self.mfa_state, state_messages.get(state, ""), tone)
        self.mfa_instruction.setText(instruction)

    def _update_pn_count(self) -> None:
        count = sum(bool(line.strip()) for line in self.pn_input.toPlainText().splitlines())
        noun = "Part Number" if count == 1 else "Part Numbers"
        self.pn_count.setText(f"{count} {noun} informado" + ("s" if count != 1 else ""))
        self.clear_pn_button.setEnabled(count > 0)

    def _module_changed(self) -> None:
        key = self.module_combo.currentData()
        self._update_module_help()
        message = f"Portal selecionado: {MODULES[key].label}. Confira a lista e inicie a consulta."
        self._set_feedback(self.execution_status, message, "info")

    def _choose_mxi_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar configuração MXI",
            str(ROOT),
            "Configuração INI (*.ini);;Todos os arquivos (*)",
        )
        if path:
            self.mxi_config.setText(path)

    def _choose_download_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Selecionar pasta de downloads", str(ROOT))
        if path:
            self.download_dir.setText(path)

    def _config_values(self) -> dict:
        return {
            "mxi_config": self.mxi_config.text().strip(),
            "latam_email": self.email.text().strip(),
            "latam_password": self.password.text(),
            "airbus_user": self.airbus_user.text().strip(),
            "airbus_password": self.airbus_password.text(),
            "toolbox_user": self.toolbox_user.text().strip(),
            "toolbox_password": self.toolbox_password.text(),
            "mxi_user": self.mxi_user.text().strip(),
            "mxi_password": self.mxi_password.text(),
            "download_dir": self.download_dir.text().strip(),
            "platform": self.platform_combo.currentData(),
        }

    def _values(self) -> dict:
        values = self._config_values()
        values.update({
            "pns": [line.strip() for line in self.pn_input.toPlainText().splitlines() if line.strip()],
        })
        return values

    def save_configuration(self, silent: bool = False) -> None:
        values = self._config_values()
        write_config(values)
        self.config = values
        self._set_feedback(
            self.config_status,
            f"Configuração salva localmente em {CONFIG_FILE.name}.",
            "success",
        )
        if not silent:
            self._set_pipeline_status(
                "Configuração salva. Agora abra a aba Executar.",
                "success",
            )

    def _reset_pipeline(self) -> None:
        for key, label in PIPELINE_STEPS:
            self.step_items[key].setText(f"○  {label}")
            self.step_items[key].setForeground(QColor("#667085"))
            self.step_items[key].setSelected(False)
            self.step_items[key].setData(Qt.ItemDataRole.AccessibleTextRole, f"{label}: aguardando")
        self.pipeline_progress.setValue(0)
        self.step_count.setText(f"0 de {len(PIPELINE_STEPS)} concluídas")
        self.pipeline.setCurrentRow(-1)
        self.pipeline_message = "Pronto para iniciar"
        self.pipeline_tone = "muted"
        self._set_current_pn("—")

    def _set_step(self, key: str, state: str = "active") -> None:
        labels = dict(PIPELINE_STEPS)
        item = self.step_items.get(key)
        if not item:
            return
        if state == "active":
            current_index = [name for name, _ in PIPELINE_STEPS].index(key)
            for previous_key, _ in PIPELINE_STEPS[:current_index]:
                if self.step_items[previous_key].text().startswith(("○", "●")):
                    self._set_step(previous_key, "done")
        symbol, color = {
            "active": ("●", "#155EEF"),
            "done": ("✓", "#039855"),
            "error": ("!", "#D92D20"),
        }.get(state, ("○", "#667085"))
        item.setText(f"{symbol}  {labels[key]}")
        item.setForeground(QColor(color))
        item.setSelected(state == "active")
        state_label = {
            "active": "em andamento",
            "done": "concluída",
            "error": "com erro",
        }.get(state, "aguardando")
        item.setData(
            Qt.ItemDataRole.AccessibleTextRole,
            f"{labels[key]}: {state_label}",
        )
        index = [name for name, _ in PIPELINE_STEPS].index(key)
        progress = index if state == "error" else index + (state in {"active", "done"})
        self.pipeline_progress.setValue(progress)
        if state == "active":
            self.step_count.setText(f"Etapa {index + 1} de {len(PIPELINE_STEPS)}")
        elif state == "error":
            self.step_count.setText(f"Etapa {index + 1} de {len(PIPELINE_STEPS)}")
        else:
            self.step_count.setText(f"{progress} de {len(PIPELINE_STEPS)} concluídas")
        if state == "error":
            self._set_pipeline_status(f"Falha na etapa: {labels[key]}", "error")
        elif state == "done" and key == "done":
            self._set_pipeline_status("Todas as etapas concluídas", "success")
        elif state == "done":
            self._set_pipeline_status(f"Etapa concluída: {labels[key]}", "success")
        else:
            self._set_pipeline_status(f"Etapa atual: {labels[key]}", "info")

    def _detect_step(self, line: str) -> str | None:
        text = line.lower()
        if "2fa" in text or "mfa" in text or "authy" in text or "pingid" in text:
            return "mfa"
        if "login" in text or "senha" in text or "chrome iniciado" in text:
            return "login"
        if "download" in text or "baix" in text or "pdf" in text:
            return "download"
        if "verific" in text or "document" in text or "form pss" in text:
            return "verify"
        if "pn" in text or "pesquis" in text or "consulta" in text:
            return "query"
        return None

    def start_automation(self) -> None:
        if self.process is not None:
            return
        key = self.module_combo.currentData()
        spec = MODULES[key]
        values = self._values()
        if not spec.cwd.exists():
            QMessageBox.critical(self, "Módulo indisponível", str(spec.cwd))
            return
        if not values["pns"]:
            QMessageBox.warning(self, "Part Numbers", "Informe pelo menos um Part Number.")
            self.tabs.setCurrentIndex(1)
            return

        self.save_configuration(silent=True)
        self._reset_pipeline()
        self._set_step("start", "done")
        self._set_step("login")
        self.log_view.clear()
        self._set_mfa_state(
            "—",
            "pending",
            "Aguardando solicitação de autenticação...",
        )
        self._set_current_pn("—")
        self.results.setRowCount(0)
        self.results_empty.setVisible(True)
        self.results_summary.setText("Aguardando resultados")
        self.log_toggle.setChecked(False)
        self.log_view.clear()
        self._append_log(f"Iniciando: {spec.label}")
        self._set_pipeline_status("Executando automação.", "info")
        self._set_feedback(
            self.execution_status,
            "Executando. Acompanhe os detalhes na aba Monitoramento.",
            "info",
        )
        self.tabs.setCurrentIndex(2)

        module_credentials = {
            "airbus": (values["airbus_user"], values["airbus_password"]),
            "mxi": (values["mxi_user"], values["mxi_password"]),
            "toolbox": (values["toolbox_user"], values["toolbox_password"]),
            "boeing": ("", ""),
        }
        module_user, module_password = module_credentials[key]

        env = QProcessEnvironment.systemEnvironment()
        env.insert("AERODOC_LOCAL_ONLY", "true")
        env.insert("AERODOC_NO_DRIVE", "true")
        env.insert("AERODOC_HEADLESS", "true")
        env.insert("AERODOC_PLATFORM", values["platform"])
        env.insert("AERODOC_PNS", "\n".join(values["pns"]))
        env.insert("AERODOC_LATAM_EMAIL", values["latam_email"])
        env.insert("AERODOC_LATAM_PASSWORD", values["latam_password"])
        env.insert("AERODOC_TOOLBOX_USER", module_user)
        env.insert("AERODOC_TOOLBOX_PASS", module_password)
        env.insert("AERODOC_AIRBUS_USER", module_user)
        env.insert("AERODOC_AIRBUS_PASS", module_password)
        env.insert("AERODOC_MXI_USER", module_user)
        env.insert("AERODOC_MXI_PASSWORD", module_password)
        env.insert("AERODOC_MXI_CONFIG", values["mxi_config"])
        env.insert("AERODOC_B787_USER", module_user)
        env.insert("AERODOC_B787_PASS", module_password)
        # O Toolbox sempre pesquisa no modo GERAL, cobrindo todas as frotas.
        env.insert("AERODOC_FLEET", "GERAL")
        env.insert("AERODOC_DOWNLOAD_DIR", values["download_dir"])
        env.insert("AERODOC_LOG_DIR", str(ROOT / "logs"))
        env.insert("AERODOC_LOG_FILE", str(ROOT / "logs" / f"{key}.log"))

        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(spec.cwd))
        self.process.setProcessEnvironment(env)
        self.process.setProgram(spec.command[0])
        # O modo unbuffered faz cada etapa chegar imediatamente ao painel.
        self.process.setArguments(["-u", *spec.command[1:]])
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.readyReadStandardError.connect(self._read_error)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress.setVisible(True)
        self.process.start()

    def stop_automation(self) -> None:
        if self.process is not None:
            self._append_log("Interrupção solicitada pelo usuário.")
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.process.kill()

    def closeEvent(self, event) -> None:
        """Encerra o módulo filho antes de fechar a interface."""
        if self.process is not None:
            self._append_log("Interface fechada. Encerrando a automação em execução.")
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.process.kill()
        event.accept()

    def _read_output(self) -> None:
        if self.process:
            self._consume(self.process.readAllStandardOutput().data().decode(errors="replace"))

    def _read_error(self) -> None:
        if self.process:
            self._consume(self.process.readAllStandardError().data().decode(errors="replace"), error=True)

    def _consume(self, text: str, error: bool = False, flush: bool = False) -> None:
        buffer_name = "_stderr_buffer" if error else "_stdout_buffer"
        pending = getattr(self, buffer_name) + text.replace("\r\n", "\n").replace("\r", "\n")
        lines = pending.split("\n")
        if flush:
            setattr(self, buffer_name, "")
        else:
            setattr(self, buffer_name, lines.pop())

        for line in lines:
            if not line:
                continue
            clean_line = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line)
            self._append_log(clean_line, error=error)
            if clean_line.startswith("[AERODOC_RESULT] "):
                try:
                    result = json.loads(clean_line.removeprefix("[AERODOC_RESULT] "))
                    self._add_result(result)
                except json.JSONDecodeError:
                    self._append_log("Resultado inválido recebido do módulo.", error=True)
            pn_match = re.search(r"(?:PN|Part Number)\s*[=:]?\s*([A-Z0-9][A-Z0-9./_-]*)", clean_line, re.IGNORECASE)
            if pn_match:
                self._set_current_pn(pn_match.group(1))
            mfa_status_match = re.search(
                r"\[AERODOC_MFA_STATUS\]\s+status=(approved|denied)",
                clean_line,
                re.IGNORECASE,
            )
            if mfa_status_match:
                mfa_status = mfa_status_match.group(1).lower()
                if mfa_status == "approved":
                    self._set_mfa_state(
                        "✓ APROVADO",
                        "approved",
                        "Autenticação aprovada. Aguardando o carregamento do Toolbox..."
                    )
                else:
                    self._set_mfa_state(
                        "NEGADO",
                        "denied",
                        "A autenticação foi recusada no aplicativo."
                    )
            if not mfa_status_match:
                structured_mfa_match = re.search(
                    r"\[AERODOC_MFA\]\s+number=(\d{2,8})",
                    clean_line,
                    re.IGNORECASE,
                )
                if structured_mfa_match:
                    self._set_mfa_state(
                        structured_mfa_match.group(1),
                        "pending",
                        "Abra o Microsoft Authenticator e selecione este número na notificação. "
                        "Se a notificação não aparecer, abra o aplicativo e atualize a tela.",
                    )
                    self._set_pipeline_status(
                        "Aguardando aprovação no aplicativo autenticador.",
                        "info",
                    )
                    continue
                mfa_match = re.search(
                    r"(?:verification\s+code|security\s+code|matching\s+number|"
                    r"microsoft\s+authenticator|authenticator|número|numero|number|"
                    r"código|codigo|code)"
                    r"[^0-9]{0,100}(\d{2,8})\b",
                    clean_line,
                    re.IGNORECASE,
                )
                if mfa_match:
                    self._set_mfa_state(
                        mfa_match.group(1),
                        "pending",
                        "Abra o Microsoft Authenticator e selecione este número na notificação. "
                        "Não digite o número manualmente.",
                    )
                    self._set_pipeline_status(
                        "Aguardando aprovação no aplicativo autenticador.",
                        "info",
                    )
                elif any(
                    token in clean_line.lower()
                    for token in (
                        "2fa", "mfa", "authenticator", "authy", "approve a request",
                        "aprovar uma solicitação", "aprovação do 2fa", "verification code",
                    )
                ):
                    self._set_mfa_state(
                        self.mfa_number.text(),
                        "pending",
                        "Confirme a solicitação no aplicativo de autenticação para continuar."
                    )
                    self._set_pipeline_status(
                        "Aguardando aprovação no aplicativo autenticador.",
                        "info",
                    )
            step = self._detect_step(clean_line)
            if step:
                self._set_step(step, "active")

    def _add_result(self, result: dict) -> None:
        row = self.results.rowCount()
        self.results.insertRow(row)
        values = [
            result.get("pn", ""),
            result.get("status", ""),
            result.get("detail", ""),
            result.get("file", "") or "",
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if column == 1:
                status = str(value).lower()
                if any(token in status for token in ("erro", "falha", "negado")):
                    item.setForeground(QColor("#B42318"))
                elif any(token in status for token in ("baixado", "sucesso", "encontrado", "ok")):
                    item.setForeground(QColor("#067647"))
                font = item.font()
                font.setWeight(QFont.Weight.DemiBold)
                item.setFont(font)
            self.results.setItem(row, column, item)
        self.results_empty.setVisible(False)
        count = self.results.rowCount()
        noun = "resultado" if count == 1 else "resultados"
        self.results_summary.setText(f"{count} {noun}")

    def _append_log(self, line: str, error: bool = False) -> None:
        prefix = "ERRO | " if error else ""
        self.log_view.appendPlainText(prefix + line)

    def _process_error(self, error) -> None:
        self._append_log(f"Falha ao iniciar o processo: {error}", error=True)
        self._set_feedback(self.execution_status, "Falha ao iniciar a automação.", "error")

    def _process_finished(self, exit_code: int, _exit_status) -> None:
        self._consume("", flush=True)
        self._consume("", error=True, flush=True)
        success = exit_code == 0
        if not success:
            current_item = self.pipeline.currentItem()
            failed_step = current_item.data(Qt.ItemDataRole.UserRole) if current_item else "start"
            self._set_step(failed_step, "error")
        if success:
            for step_key, _ in PIPELINE_STEPS:
                self._set_step(step_key, "done")
            self._set_pipeline_status("Execução concluída.", "success")
            self._set_feedback(
                self.execution_status,
                "Execução concluída. Você pode iniciar outro processamento.",
                "success",
            )
            self._append_log("Automação concluída.")
        else:
            self._set_pipeline_status(
                f"Execução encerrada com código {exit_code}.",
                "error",
            )
            self._set_feedback(
                self.execution_status,
                f"Execução encerrada com erro (código {exit_code}).",
                "error",
            )
            if self.mfa_number.property("state") == "pending":
                self._set_mfa_state(
                    self.mfa_number.text(),
                    "denied",
                    "A autenticação não foi confirmada antes do encerramento da execução."
                )
            self._append_log(f"Automação encerrada com código {exit_code}.", error=True)
        self.progress.setVisible(False)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.process.deleteLater()
        self.process = None


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
