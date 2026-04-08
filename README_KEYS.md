## Geração de chaves e integração CI

Este projeto pode usar assinaturas assimétricas (RSA ou ECDSA). A aplicação valida licenças com a chave pública; a assinatura é gerada pelo gerador/servidor com a chave privada.

Arquivos úteis:
- `tools/generate_keys.py`: script para gerar pares de chaves PEM.

Recomendações importantes:
- NUNCA empacote a chave privada no executável.
- Armazene a chave privada como segredo no servidor/CI (variável `PRIVATE_KEY_PEM` ou arquivo seguro) e injete-a no processo de build/geração.
- A chave pública (`public_key.pem`) pode ser distribuída com o app (ou buscada de um servidor seguro) para verificação.

Exemplos de uso local:

1) Gerar par RSA 3072 bits:

```bash
python tools/generate_keys.py --algo rsa --bits 3072 --out-dir keys
```

2) Gerar par ECDSA (P-256):

```bash
python tools/generate_keys.py --algo ecdsa --curve secp256r1 --out-dir keys
```

Após gerar, você terá `keys/private_key.pem` e `keys/public_key.pem`.

Como injetar `PRIVATE_KEY_PEM` no CI (exemplos):

- Bash (Linux runners):

```bash
# Configure no painel de segredos do CI a variável PRIVATE_KEY (conteúdo do PEM)
# No job, exporte:
export PRIVATE_KEY_PEM="$PRIVATE_KEY"
```

- PowerShell (Windows runners / Azure Pipelines / GitHub Actions):

```powershell
# Configure secret PRIVATE_KEY no CI
$env:PRIVATE_KEY_PEM = $env:PRIVATE_KEY
```

No gerador (servidor/CI) use `PRIVATE_KEY_PEM` para assinar. Se preferir apontar um arquivo, use `PRIVATE_KEY_FILE`.

Verificação no app:
- Coloque `public_key.pem` em um local lido pela aplicação (por exemplo, `assets/` ou empacote o `.pem` separadamente) ou carregue via variável `PUBLIC_KEY_PEM`.

Fallback:
- Se não houver chave pública/privada, o gerador aplica HMAC com `MASTER_KEY` (variável de ambiente). Isso mantém compatibilidade com instalações existentes, mas para produção utilize assinaturas assimétricas.

Segurança:
- Proteja o acesso aos segredos do CI.
- Rotacione chaves se houver suspeita de vazamento.
