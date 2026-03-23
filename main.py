import sys
import json
import hmac
import hashlib
import zipfile
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFileDialog, QMessageBox
)
from PySide6.QtGui import QIcon
from pathlib import Path

MASTER_KEY = b"SUA_MASTER_KEY_SUPER_SECRETA"


class LicencaApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador de Licença Mobile")
        self.setGeometry(100, 100, 500, 400)

        layout = QVBoxLayout()

        self.cnpjs_input = QTextEdit()
        self.cnpjs_input.setPlaceholderText("Digite os CNPJs (um por linha)")

        self.device_input = QLineEdit()
        self.device_input.setPlaceholderText("DEVICE_ID")

        self.validade_input = QLineEdit()
        self.validade_input.setPlaceholderText("Validade (YYYY-MM-DD) ou vazio")

        btn_gerar = QPushButton("Gerar Licença")
        btn_gerar.clicked.connect(self.gerar_licenca)

        btn_carregar = QPushButton("Carregar Licença")
        btn_carregar.clicked.connect(self.carregar_licenca)

        layout.addWidget(QLabel("CNPJs:"))
        layout.addWidget(self.cnpjs_input)

        layout.addWidget(QLabel("Device ID:"))
        layout.addWidget(self.device_input)

        layout.addWidget(QLabel("Validade:"))
        layout.addWidget(self.validade_input)

        layout.addWidget(btn_gerar)
        layout.addWidget(btn_carregar)

        self.setLayout(layout)

    def gerar_payload(self):
        cnpjs = [c.strip() for c in self.cnpjs_input.toPlainText().splitlines() if c.strip()]
        device = self.device_input.text().strip()
        validade = self.validade_input.text().strip() or None

        payload = {
            "cnpjs": cnpjs,
            "device": device,
            "validade": validade,
            "gerado_em": datetime.utcnow().isoformat()
        }

        dados = json.dumps(payload, separators=(',', ':')).encode()

        assinatura = hmac.new(
            MASTER_KEY,
            dados,
            hashlib.sha256
        ).digest()

        return dados, assinatura

    def gerar_licenca(self):
        try:
            dados, assinatura = self.gerar_payload()

            caminho, _ = QFileDialog.getSaveFileName(self, "Salvar licença", "licenca_mobile.key", "Key (*.key)")

            if not caminho:
                return

            with zipfile.ZipFile(caminho, 'w') as z:
                z.writestr("licenca_mobile.json", dados)
                z.writestr("licenca_mobile.sig", assinatura)

            QMessageBox.information(self, "Sucesso", "Licença gerada com sucesso!")

        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    def carregar_licenca(self):
        try:
            caminho, _ = QFileDialog.getOpenFileName(self, "Abrir licença", "", "Key (*.key)")

            if not caminho:
                return

            with zipfile.ZipFile(caminho, 'r') as z:
                dados = z.read("licenca_mobile.json")

            payload = json.loads(dados.decode())

            self.cnpjs_input.setText("\n".join(payload.get("cnpjs", [])))
            self.device_input.setText(payload.get("device", ""))
            self.validade_input.setText(payload.get("validade") or "")

            QMessageBox.information(self, "Sucesso", "Licença carregada!")

        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Definir ícone da aplicação usando o PNG em assets
    icon_path = Path(__file__).parent / "assets" / "logo.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = LicencaApp()
    # Também definir no widget principal (opcional)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))

    window.show()
    sys.exit(app.exec())
