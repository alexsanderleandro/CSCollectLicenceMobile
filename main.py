import sys
import json
import hmac
import hashlib
import zipfile
from datetime import datetime
import os
import base64
import binascii

# tentar importar cryptography para assinaturas assimétricas
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, ec, utils as asym_utils
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except Exception:
    CRYPTO_AVAILABLE = False

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFileDialog, QMessageBox,
    QDateEdit, QHBoxLayout, QCheckBox
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QDate
from pathlib import Path
from dotenv import load_dotenv

# Versão do aplicativo
from version import VERSION

# Carregar MASTER_KEY a partir do arquivo .env (se presente).
# Quando empacotado pelo PyInstaller, o .env pode estar em sys._MEIPASS.
base_dir = getattr(sys, '_MEIPASS', Path(__file__).parent)
dotenv_path = Path(base_dir) / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path)
# preferir variável de ambiente (ex.: no pipeline); fallback para string hardcoded
MASTER_KEY = os.environ.get('MASTER_KEY', 'SUA_MASTER_KEY_SUPER_SECRETA')

# Garantir bytes para uso com HMAC
MASTER_KEY_BYTES = MASTER_KEY.encode('utf-8')


def _sanitize_for_filename(s: str) -> str:
    """Sanitiza `s` para uso em nomes de arquivo: mantém alfanuméricos, '-' e '_', substitui espaços por '_' e limita tamanho."""
    if not s:
        return ""
    s = s.strip()
    s = s.replace(' ', '_')
    safe = []
    for ch in s:
        if ch.isalnum() or ch in ('-', '_'):
            safe.append(ch)
    return ''.join(safe)[:30]


def _load_private_key():
    """Tenta carregar chave privada a partir de:
    - variável de ambiente PRIVATE_KEY_PEM (PEM string)
    - arquivo apontado por PRIVATE_KEY_FILE
    - arquivo private_key.pem em base_dir (útil em server, NÃO empacotar no exe)
    Retorna None se não encontrada ou se cryptography não estiver disponível.
    """
    if not CRYPTO_AVAILABLE:
        return None

    pem = os.environ.get('PRIVATE_KEY_PEM')
    if pem:
        try:
            return serialization.load_pem_private_key(pem.encode('utf-8'), password=None)
        except Exception:
            return None

    path = os.environ.get('PRIVATE_KEY_FILE')
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates.append(Path(base_dir) / 'private_key.pem')

    for p in candidates:
        try:
            if p and p.exists():
                return serialization.load_pem_private_key(p.read_bytes(), password=None)
        except Exception:
            continue

    return None


def _load_public_key():
    """Carrega chave pública a partir de PUBLIC_KEY_PEM env ou public_key.pem em base_dir.
    Retorna None se não encontrada.
    """
    if not CRYPTO_AVAILABLE:
        return None

    pem = os.environ.get('PUBLIC_KEY_PEM')
    if pem:
        try:
            return serialization.load_pem_public_key(pem.encode('utf-8'))
        except Exception:
            return None

    p = Path(base_dir) / 'public_key.pem'
    try:
        if p.exists():
            return serialization.load_pem_public_key(p.read_bytes())
    except Exception:
        return None

    return None


def _sign_with_private_key(private_key, data: bytes):
    """Assina `data` com a chave privada fornecida. Retorna tuple(alg, signature_bytes).
    Suporta RSA (PSS+SHA256) e ECDSA (SHA256).
    """
    if isinstance(private_key, rsa.RSAPrivateKey):
        sig = private_key.sign(
            data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256()
        )
        return 'RSA', sig

    # assumir EC
    try:
        sig = private_key.sign(data, ec.ECDSA(hashes.SHA256()))
        return 'ECDSA', sig
    except Exception:
        raise


def _verify_with_public_key(public_key, alg: str, data: bytes, sig: bytes) -> bool:
    if not CRYPTO_AVAILABLE:
        return False

    try:
        if alg == 'RSA' and isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(
                sig,
                data,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256()
            )
            return True

        if alg == 'ECDSA':
            public_key.verify(sig, data, ec.ECDSA(hashes.SHA256()))
            return True

    except InvalidSignature:
        return False
    except Exception:
        return False

    return False


class LicencaApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador de Licença Mobile")
        self.setGeometry(100, 100, 500, 400)

        layout = QVBoxLayout()

        self.cnpjs_input = QTextEdit()
        self.cnpjs_input.setPlaceholderText("Digite os CNPJs (um por linha)")

        # Nome do cliente (obrigatório, máximo 30 caracteres)
        self.nome_input = QLineEdit()
        self.nome_input.setPlaceholderText("Nome do cliente (obrigatório, máximo 30 caracteres)")
        self.nome_input.setMaxLength(30)

        self.device_input = QLineEdit()
        self.device_input.setPlaceholderText("DEVICE_ID")

        # campo de data com calendário popup e opção 'Sem validade'
        self.validade_input = QDateEdit()
        self.validade_input.setCalendarPopup(True)
        self.validade_input.setDisplayFormat("yyyy-MM-dd")
        self.validade_input.setDate(QDate.currentDate())
        self.sem_validade_checkbox = QCheckBox("Sem validade")
        self.sem_validade_checkbox.stateChanged.connect(self._on_sem_validade_changed)

        btn_gerar = QPushButton("Gerar Licença")
        btn_gerar.clicked.connect(self.gerar_licenca)

        btn_carregar = QPushButton("Carregar Licença")
        btn_carregar.clicked.connect(self.carregar_licenca)

        layout.addWidget(QLabel("CNPJs:"))
        layout.addWidget(self.cnpjs_input)

        layout.addWidget(QLabel("Nome do cliente:"))
        layout.addWidget(self.nome_input)

        layout.addWidget(QLabel("Device ID:"))
        layout.addWidget(self.device_input)

        layout.addWidget(QLabel("Validade:"))
        h_date = QHBoxLayout()
        h_date.addWidget(self.validade_input)
        h_date.addWidget(self.sem_validade_checkbox)
        layout.addLayout(h_date)

        layout.addWidget(btn_gerar)
        layout.addWidget(btn_carregar)

        # Mostrar versão do app no formulário principal
        self.version_label = QLabel(f"Versão: {VERSION}")
        layout.addWidget(self.version_label)

        self.setLayout(layout)

    def _on_sem_validade_changed(self, state):
        checked = self.sem_validade_checkbox.isChecked()
        self.validade_input.setEnabled(not checked)
        if checked:
            # quando sem validade, podemos manter a data visual mas ela será ignorada na geração
            pass

    def gerar_payload(self):
        cnpjs = [c.strip() for c in self.cnpjs_input.toPlainText().splitlines() if c.strip()]
        nome_cliente = self.nome_input.text().strip()
        device = self.device_input.text().strip()
        if getattr(self, 'sem_validade_checkbox', None) and self.sem_validade_checkbox.isChecked():
            validade = None
        else:
            try:
                validade = self.validade_input.date().toString("yyyy-MM-dd")
            except Exception:
                validade = None

        payload = {
            "cnpjs": cnpjs,
            "nome_cliente": nome_cliente,
            "device": device,
            "validade": validade,
            "gerado_em": datetime.utcnow().isoformat()
        }

        dados = json.dumps(payload, separators=(',', ':')).encode()

        # retorna apenas os dados; assinatura será aplicada em gerar_licenca
        return dados, None

    def gerar_licenca(self):
        try:
            dados, _ = self.gerar_payload()

            # Validações do nome do cliente
            nome_cliente = self.nome_input.text().strip()
            if not nome_cliente:
                QMessageBox.warning(self, "Validação", "O campo Nome do cliente é obrigatório.")
                return
            if len(nome_cliente) > 30:
                QMessageBox.warning(self, "Validação", "O Nome do cliente deve ter no máximo 30 caracteres.")
                return

            # Priorizar assinatura assimétrica se houver chave privada disponível
            sig_algo = 'HMAC'
            assinatura_bytes = None
            priv = _load_private_key()
            if priv is not None:
                sig_algo, assinatura_bytes = _sign_with_private_key(priv, dados)
            else:
                # fallback HMAC simétrico
                assinatura_bytes = hmac.new(MASTER_KEY_BYTES, dados, hashlib.sha256).digest()
                sig_algo = 'HMAC'

            # nome padrão: Licenca_CSCollectMobile_nomecliente_deviceID.key
            safe_name = _sanitize_for_filename(nome_cliente)
            device = self.device_input.text().strip() or "device"
            safe_device = _sanitize_for_filename(device)
            default_fname = f"Licenca_CSCollectMobile_{safe_name}_{safe_device}.key"
            caminho, _ = QFileDialog.getSaveFileName(self, "Salvar licença", default_fname, "Key (*.key)")

            if not caminho:
                return

            # Assinatura escrita com prefixo de algoritmo: ALGO$BASE64
            sig_b64 = base64.b64encode(assinatura_bytes).decode('ascii')
            sig_text = f"{sig_algo}${sig_b64}"
            with zipfile.ZipFile(caminho, 'w') as z:
                z.writestr("licenca_mobile.json", dados)
                z.writestr("licenca_mobile.sig", sig_text)

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
                sig_raw = z.read("licenca_mobile.sig")

            # interpretar assinatura: esperamos formato ALGO$BASE64 ou texto base64/hex/bytes
            alg = None
            sig_bytes = None
            try:
                sig_text = sig_raw.decode('utf-8').strip()
                if '$' in sig_text:
                    alg, b64 = sig_text.split('$', 1)
                    try:
                        sig_bytes = base64.b64decode(b64)
                    except (binascii.Error, ValueError):
                        sig_bytes = None
                else:
                    # sem algoritmo explícito: tentar base64 ou hex
                    try:
                        sig_bytes = base64.b64decode(sig_text)
                    except (binascii.Error, ValueError):
                        try:
                            sig_bytes = bytes.fromhex(sig_text)
                        except ValueError:
                            sig_bytes = None
            except UnicodeDecodeError:
                sig_bytes = sig_raw

            # se ainda sem bytes, tentar usar raw
            if sig_bytes is None and len(sig_raw) in (32, 64):
                sig_bytes = sig_raw

            # Verificação: se algoritmo assimétrico indicado, tentar verificar com chave pública
            verified = False
            if alg and alg != 'HMAC':
                pub = _load_public_key()
                if pub is None:
                    QMessageBox.critical(self, "Erro", f"Assinatura {alg} presente mas chave pública não encontrada.")
                    return
                if _verify_with_public_key(pub, alg, dados, sig_bytes):
                    verified = True
            
            # fallback para HMAC se não verificado por assimétrico
            if not verified:
                expected = hmac.new(MASTER_KEY_BYTES, dados, hashlib.sha256).digest()
                if sig_bytes is None or not hmac.compare_digest(expected, sig_bytes):
                    QMessageBox.critical(self, "Erro", "Assinatura inválida na licença (falha na verificação).")
                    return

            payload = json.loads(dados.decode())

            self.cnpjs_input.setText("\n".join(payload.get("cnpjs", [])))
            self.nome_input.setText(payload.get("nome_cliente", ""))
            self.device_input.setText(payload.get("device", ""))
            # configurar QDateEdit e checkbox com a validade carregada
            validade = payload.get("validade")
            if validade:
                try:
                    d = QDate.fromString(validade, "yyyy-MM-dd")
                    if d.isValid():
                        self.validade_input.setDate(d)
                        self.sem_validade_checkbox.setChecked(False)
                    else:
                        self.sem_validade_checkbox.setChecked(True)
                except Exception:
                    self.sem_validade_checkbox.setChecked(True)
            else:
                self.sem_validade_checkbox.setChecked(True)

            QMessageBox.information(self, "Sucesso", "Licença carregada!")

        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Preferir ícone .ico se presente, fallback para PNG
    base = Path(__file__).parent / "assets"
    icon_candidates = [base / "logo.ico", base / "logo.png"]
    icon_path = None
    for p in icon_candidates:
        if p.exists():
            icon_path = p
            break

    if icon_path:
        app.setWindowIcon(QIcon(str(icon_path)))

    window = LicencaApp()
    if icon_path:
        window.setWindowIcon(QIcon(str(icon_path)))

    window.show()
    sys.exit(app.exec())

