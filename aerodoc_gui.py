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
        self.setWindowTitle("AeroDoc Extractor")
        self.resize(1180, 760)
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        title = QLabel("AeroDoc Extractor")
        title.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        subtitle = QLabel(
            "Selecione uma automação, confira a configuração e acompanhe o pipeline."
        )
        subtitle.setStyleSheet("color: #667085;")
        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_settings_tab(), "1. Configuração")
        self.tabs.addTab(self._build_execution_tab(), "2. Execução")
        self.tabs.addTab(self._build_monitor_tab(), "3. Monitoramento")
        root_layout.addWidget(self.tabs)

    def _build_settings_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        intro = QLabel(
            "Preencha seus acessos uma vez e clique em 'Salvar configuração'. "
            "Os dados ficam somente nesta máquina."
        )
        intro.setStyleSheet("color: #667085;")
        layout.addWidget(intro)

        access_box = QGroupBox("Acessos gerais")
        access_layout = QFormLayout(access_box)
        self.email = QLineEdit()
        self.email.setPlaceholderText("usuario@latam.com")
        access_layout.addRow("E-mail LATAM:", self.email)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Senha LATAM")
        access_layout.addRow("Senha LATAM:", self.password)

        self.platform_combo = QComboBox()
        for key, label in PLATFORMS:
            self.platform_combo.addItem(label, key)
        access_layout.addRow("Sistema operacional:", self.platform_combo)
        platform_hint = QLabel(
            "Escolha o sistema onde o executável será executado. "
            "A escolha define atalhos e caminhos compatíveis."
        )
        platform_hint.setStyleSheet("color: #667085;")
        access_layout.addRow("", platform_hint)
        layout.addWidget(access_box)

        module_box = QGroupBox("Acessos específicos dos módulos")
        module_layout = QGridLayout(module_box)
        module_layout.addWidget(QLabel("Módulo"), 0, 0)
        module_layout.addWidget(QLabel("Usuário"), 0, 1)
        module_layout.addWidget(QLabel("Senha"), 0, 2)

        self.airbus_user = QLineEdit()
        self.airbus_password = QLineEdit()
        self.airbus_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.toolbox_user = QLineEdit()
        self.toolbox_password = QLineEdit()
        self.toolbox_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.mxi_user = QLineEdit()
        self.mxi_password = QLineEdit()
        self.mxi_password.setEchoMode(QLineEdit.EchoMode.Password)

        for row, label, user_field, password_field in [
            (1, "Airbus", self.airbus_user, self.airbus_password),
            (2, "Toolbox", self.toolbox_user, self.toolbox_password),
            (3, "MXI", self.mxi_user, self.mxi_password),
        ]:
            module_layout.addWidget(QLabel(label), row, 0)
            module_layout.addWidget(user_field, row, 1)
            module_layout.addWidget(password_field, row, 2)
        layout.addWidget(module_box)

        integration_box = QGroupBox("Configurações dos módulos")
        integration_layout = QFormLayout(integration_box)
        mxi_config_row = QHBoxLayout()
        self.mxi_config = QLineEdit()
        self.mxi_config.setPlaceholderText("config.ini do MXI")
        mxi_browse = QPushButton("Selecionar")
        mxi_browse.clicked.connect(self._choose_mxi_config)
        mxi_config_row.addWidget(self.mxi_config)
        mxi_config_row.addWidget(mxi_browse)
        integration_layout.addRow("Configuração MXI:", mxi_config_row)
        layout.addWidget(integration_box)

        storage_box = QGroupBox("Pasta de saída")
        storage_layout = QFormLayout(storage_box)
        download_row = QHBoxLayout()
        self.download_dir = QLineEdit()
        download_browse = QPushButton("Selecionar")
        download_browse.clicked.connect(self._choose_download_dir)
        download_row.addWidget(self.download_dir)
        download_row.addWidget(download_browse)
        storage_layout.addRow("Downloads locais:", download_row)
        layout.addWidget(storage_box)

        save_row = QHBoxLayout()
        save_button = QPushButton("Salvar configuração")
        save_button.setDefault(True)
        save_button.clicked.connect(self.save_configuration)
        save_row.addWidget(save_button)
        self.config_status = QLabel("Nenhuma alteração pendente")
        self.config_status.setStyleSheet("color: #667085;")
        save_row.addWidget(self.config_status)
        save_row.addStretch()
        layout.addLayout(save_row)
        layout.addStretch()
        return page

    def _build_execution_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        execution_box = QGroupBox("Escolha a automação")
        execution_layout = QFormLayout(execution_box)
        self.module_combo = QComboBox()
        for key, spec in MODULES.items():
            self.module_combo.addItem(spec.label, key)
        self.module_combo.currentIndexChanged.connect(self._module_changed)
        execution_layout.addRow("Funcionalidade:", self.module_combo)

        layout.addWidget(execution_box)

        pn_box = QGroupBox("Part Numbers")
        pn_layout = QVBoxLayout(pn_box)
        pn_layout.addWidget(QLabel("Informe um Part Number por linha:"))
        self.pn_input = QPlainTextEdit()
        self.pn_input.setPlaceholderText("Exemplo:\nABC123\nDEF456")
        pn_layout.addWidget(self.pn_input)
        layout.addWidget(pn_box, 1)

        actions = QHBoxLayout()
        self.start_button = QPushButton("Iniciar automação")
        self.start_button.clicked.connect(self.start_automation)
        self.stop_button = QPushButton("Parar")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_automation)
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addStretch()
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        actions.addWidget(self.progress)
        layout.addLayout(actions)
        self.execution_status = QLabel("Pronto para iniciar")
        self.execution_status.setStyleSheet("color: #667085;")
        layout.addWidget(self.execution_status)
        return page

    def _build_monitor_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        top.addWidget(self._build_pipeline_box(), 1)
        layout.addLayout(top)

        result_box = QGroupBox("Resultados dos Part Numbers")
        result_layout = QVBoxLayout(result_box)
        self.results = QTableWidget(0, 4)
        self.results.setHorizontalHeaderLabels(["Part Number", "Status", "Detalhe", "Arquivo local"])
        self.results.horizontalHeader().setStretchLastSection(True)
        self.results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        result_layout.addWidget(self.results)
        layout.addWidget(result_box, 1)

        log_box = QGroupBox("Log da execução")
        log_layout = QVBoxLayout(log_box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "QPlainTextEdit { background: #101828; color: #D0D5DD; "
            "font-family: monospace; }"
        )
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_box, 1)
        return page

    def _build_pipeline_box(self) -> QGroupBox:
        box = QGroupBox("Pipeline")
        layout = QVBoxLayout(box)
        self.pipeline = QListWidget()
        for key, label in PIPELINE_STEPS:
            item = QListWidgetItem(f"○  {label}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.pipeline.addItem(item)
            self.step_items[key] = item
        layout.addWidget(self.pipeline)
        self.status_label = QLabel("Pronto para iniciar")
        self.status_label.setStyleSheet("color: #667085;")
        layout.addWidget(self.status_label)
        self.item_status = QLabel("Part Number atual: —")
        self.item_status.setStyleSheet("font-weight: 600; color: #344054;")
        layout.addWidget(self.item_status)
        mfa_box = QGroupBox("Confirmação de autenticação")
        mfa_layout = QVBoxLayout(mfa_box)
        self.mfa_number = QLabel("—")
        self.mfa_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mfa_number.setMinimumHeight(95)
        self.mfa_number.setFont(QFont("Arial", 38, QFont.Weight.Bold))
        self.mfa_number.setStyleSheet(
            "color: #155EEF; background: #EFF4FF; border: 2px solid #84ADFF; "
            "border-radius: 10px; padding: 8px;"
        )
        mfa_layout.addWidget(self.mfa_number)
        self.mfa_instruction = QLabel("O código ou número de aprovação aparecerá aqui durante o login.")
        self.mfa_instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mfa_instruction.setWordWrap(True)
        self.mfa_instruction.setStyleSheet("color: #667085; padding: 4px;")
        mfa_layout.addWidget(self.mfa_instruction)
        layout.addWidget(mfa_box)
        return box

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

    def _module_changed(self) -> None:
        key = self.module_combo.currentData()
        message = f"Selecionado: {MODULES[key].label}"
        self.execution_status.setText(message)
        self.status_label.setText(message)

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
        self.config_status.setText(f"Salvo localmente em {CONFIG_FILE.name}")
        self.config_status.setStyleSheet("color: #039855;")
        if not silent:
            self.status_label.setText("Configuração salva. Vá para a aba Execução.")

    def _reset_pipeline(self) -> None:
        for key, label in PIPELINE_STEPS:
            self.step_items[key].setText(f"○  {label}")
            self.step_items[key].setForeground(QColor("#667085"))

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
        self.mfa_number.setText("—")
        self.mfa_instruction.setText("Aguardando solicitação de autenticação...")
        self.item_status.setText("Part Number atual: —")
        self.results.setRowCount(0)
        self._append_log(f"Iniciando: {spec.label}")
        self.status_label.setText("Executando")
        self.execution_status.setText("Executando. Acompanhe os detalhes na aba Monitoramento.")
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
                self.item_status.setText(f"Part Number atual: {pn_match.group(1)}")
            mfa_status_match = re.search(
                r"\[AERODOC_MFA_STATUS\]\s+status=(approved|denied)",
                clean_line,
                re.IGNORECASE,
            )
            if mfa_status_match:
                mfa_status = mfa_status_match.group(1).lower()
                if mfa_status == "approved":
                    self.mfa_number.setText("✓")
                    self.mfa_instruction.setText(
                        "Autenticação aprovada. Aguardando o carregamento do Toolbox..."
                    )
                else:
                    self.mfa_number.setText("NEGADO")
                    self.mfa_instruction.setText(
                        "A autenticação foi recusada no aplicativo."
                    )
            if not mfa_status_match:
                structured_mfa_match = re.search(
                    r"\[AERODOC_MFA\]\s+number=(\d{2,8})",
                    clean_line,
                    re.IGNORECASE,
                )
                if structured_mfa_match:
                    self.mfa_number.setText(structured_mfa_match.group(1))
                    self.mfa_instruction.setText(
                        "Abra o Microsoft Authenticator e selecione este número na notificação. "
                        "Se a notificação não aparecer, abra o aplicativo e atualize a tela."
                    )
                    self.status_label.setText(
                        "Autenticação de dois fatores aguardando confirmação."
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
                    self.mfa_number.setText(mfa_match.group(1))
                    self.mfa_instruction.setText(
                        "Abra o Microsoft Authenticator e selecione este número na notificação. "
                        "Não digite o número manualmente."
                    )
                    self.status_label.setText(
                        "Autenticação de dois fatores aguardando confirmação."
                    )
                elif any(
                    token in clean_line.lower()
                    for token in (
                        "2fa", "mfa", "authenticator", "authy", "approve a request",
                        "aprovar uma solicitação", "aprovação do 2fa", "verification code",
                    )
                ):
                    self.mfa_instruction.setText(
                        "Confirme a solicitação no aplicativo de autenticação para continuar."
                    )
                    self.status_label.setText("Autenticação de dois fatores aguardando confirmação.")
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
            self.results.setItem(row, column, QTableWidgetItem(str(value)))

    def _append_log(self, line: str, error: bool = False) -> None:
        prefix = "ERRO | " if error else ""
        self.log_view.appendPlainText(prefix + line)

    def _process_error(self, error) -> None:
        self._append_log(f"Falha ao iniciar o processo: {error}", error=True)
        self.execution_status.setText("Falha ao iniciar a automação")

    def _process_finished(self, exit_code: int, _exit_status) -> None:
        self._consume("", flush=True)
        self._consume("", error=True, flush=True)
        success = exit_code == 0
        self._set_step("done" if success else "start", "done" if success else "error")
        if success:
            for step_key, _ in PIPELINE_STEPS:
                self._set_step(step_key, "done")
            self.status_label.setText("Execução concluída")
            self.execution_status.setText("Execução concluída. Você pode iniciar outro processamento.")
            self._append_log("Automação concluída.")
        else:
            self.status_label.setText(f"Execução encerrada com código {exit_code}")
            self.execution_status.setText(f"Execução encerrada com erro (código {exit_code}).")
            if self.mfa_number.text() not in {"—", "NEGADO"}:
                self.mfa_instruction.setText(
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
