"""Genera el par de claves Ed25519 del worker GPU.

La clave PÚBLICA se publica en el repo (cloud/worker_public_key.txt): no es
secreta y permite al backend verificar peticiones firmadas sin guardar ningún
secreto en Render. La clave PRIVADA queda en cloud/data/ (gitignored) y se
inyecta solo en la copia de build del kernel de Kaggle (privado).
"""
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

BASE = Path(__file__).resolve().parents[1]
PRIV = BASE / "cloud" / "data" / "worker_ed25519.pem"
PUB = BASE / "cloud" / "worker_public_key.txt"


def main() -> None:
    PRIV.parent.mkdir(parents=True, exist_ok=True)
    if PRIV.exists():
        key = serialization.load_pem_private_key(PRIV.read_bytes(), password=None)
        print("CLAVE EXISTENTE reutilizada")
    else:
        key = Ed25519PrivateKey.generate()
        PRIV.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        print("CLAVE NUEVA generada en", PRIV)
    raw_pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    PUB.write_text(raw_pub.hex(), encoding="utf-8")
    print("PUBLICA escrita en", PUB, len(raw_pub.hex()), "hex")


if __name__ == "__main__":
    main()
