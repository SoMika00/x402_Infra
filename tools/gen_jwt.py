# tools/gen_jwt.py
import os, time, base64, sys, jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

def _load_ed25519_private(key_material: str) -> Ed25519PrivateKey:
    # 1) PEM ?
    if key_material.strip().startswith("-----BEGIN"):
        k = load_pem_private_key(key_material.encode(), password=None)
        if not isinstance(k, Ed25519PrivateKey):
            raise ValueError("La clé PEM fournie n'est pas Ed25519.")
        return k

    # 2) base64 brut (32 ou 64 octets)
    raw = base64.b64decode(key_material)
    if len(raw) == 32:
        return Ed25519PrivateKey.from_private_bytes(raw)
    if len(raw) == 64:
        # certains exports donnent (priv 32 + pub 32) → on garde les 32 premiers
        return Ed25519PrivateKey.from_private_bytes(raw[:32])

    raise ValueError(
        f"CDP_API_KEY_SECRET doit être un Ed25519 privé en base64 (32 ou 64 octets), reçu {len(raw)}."
    )

def gen_jwt(method: str, host: str, path: str, ttl: int = 120) -> str:
    kid = os.environ["CDP_API_KEY_ID"]            # Key ID complet
    secret = os.environ["CDP_API_KEY_SECRET"]     # privateKey (base64 32/64) ou PEM
    key = _load_ed25519_private(secret)

    now = int(time.time())
    claims = {
        "iss": "cdp",
        "sub": kid,
        "aud": "cdp",
        "iat": now,
        "nbf": now - 30,
        "exp": now + ttl,
        "uris": [f"{method.upper()} {host}{path}"],  # ex: POST api.cdp.coinbase.com/platform/v2/x402/verify
    }
    headers = {"alg": "EdDSA", "kid": kid, "typ": "JWT"}
    return jwt.encode(claims, key=key, algorithm="EdDSA", headers=headers)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: python tools/gen_jwt.py <METHOD> <HOST> <PATH>", file=sys.stderr)
        sys.exit(2)
    print(gen_jwt(sys.argv[1], sys.argv[2], sys.argv[3]))


