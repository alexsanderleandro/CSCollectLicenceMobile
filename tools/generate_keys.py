#!/usr/bin/env python3
"""Gerador simples de pares de chaves RSA ou ECDSA.

Gera `private_key.pem` e `public_key.pem` no diretório alvo.
Imprime exemplo de export para `PRIVATE_KEY_PEM` (útil para CI).

Uso:
  python tools/generate_keys.py --algo rsa --out-dir keys --bits 3072
  python tools/generate_keys.py --algo ecdsa --out-dir keys --curve secp256r1

Não comite a `private_key.pem` no repositório.
"""
import argparse
from pathlib import Path
import sys

try:
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import rsa, ec
except Exception as e:
    print("cryptography is required. Install with: pip install cryptography", file=sys.stderr)
    raise


def generate_rsa(bits: int = 3072):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    public_key = private_key.public_key()
    return private_key, public_key


def generate_ecdsa(curve_name: str = 'secp256r1'):
    curve = {
        'secp256r1': ec.SECP256R1(),
        'secp384r1': ec.SECP384R1(),
        'secp521r1': ec.SECP521R1(),
    }.get(curve_name, ec.SECP256R1())
    private_key = ec.generate_private_key(curve)
    public_key = private_key.public_key()
    return private_key, public_key


def write_pem(private_key, public_key, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    priv_p = out_dir / 'private_key.pem'
    pub_p = out_dir / 'public_key.pem'

    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    priv_p.write_bytes(priv_bytes)
    pub_p.write_bytes(pub_bytes)

    return priv_p, pub_p


def main():
    p = argparse.ArgumentParser(description='Gerar par de chaves RSA ou ECDSA')
    p.add_argument('--algo', choices=('rsa', 'ecdsa'), default='rsa')
    p.add_argument('--out-dir', default='keys')
    p.add_argument('--bits', type=int, default=3072, help='RSA key size (bits)')
    p.add_argument('--curve', default='secp256r1', help='ECDSA curve name')
    args = p.parse_args()

    if args.algo == 'rsa':
        priv, pub = generate_rsa(args.bits)
    else:
        priv, pub = generate_ecdsa(args.curve)

    out_dir = Path(args.out_dir)
    priv_p, pub_p = write_pem(priv, pub, out_dir)

    print(f'Chaves geradas:')
    print(f'  private: {priv_p}')
    print(f'  public : {pub_p}')
    print()
    print('Exemplo para exportar PRIVATE_KEY_PEM no CI (bash):')
    print('  export PRIVATE_KEY_PEM="$(cat ' + str(priv_p) + ')"')
    print('PowerShell (Azure DevOps / GitHub Actions runner):')
    print('  $env:PRIVATE_KEY_PEM = Get-Content -Raw ' + str(priv_p))


if __name__ == '__main__':
    main()
