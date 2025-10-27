# app/core/config.py
import os

class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./x402.db"
    )

    # x402 / facilitator
    X402_FACILITATOR_API_KEY: str = os.getenv("X402_FACILITATOR_API_KEY", "")
    X402_ASSET: str = os.getenv("X402_ASSET", "USDC")     # informatif
    X402_CHAIN: str = os.getenv("X402_CHAIN", "base")
    X402_MIN_PAY_CENTS: int = int(os.getenv("X402_MIN_PAY_CENTS", "10"))
    X402_MERCHANT: str = os.getenv("X402_MERCHANT_ADDRESS", "0xMerchant")

    # si tu mets l'URL terminant par /verify on détecte; sinon on ajoute /verify
    X402_FACILITATOR_URL: str = os.getenv("X402_FACILITATOR_URL", "")

    # Pricing
    PRICE_PARSE_PDF_CENTS: int = int(os.getenv("PRICE_PARSE_PDF_CENTS", "1"))
    PRICE_EMBED_CENTS: int = int(os.getenv("PRICE_EMBED_CENTS", "1"))
    PRICE_EMBED_BATCH_CENTS: int = int(os.getenv("PRICE_EMBED_BATCH_CENTS", "5"))

    # AI / batching
    EMBED_BATCH: int = int(os.getenv("EMBED_BATCH", "64"))
    EMBED_MAX_WAIT_MS: int = int(os.getenv("EMBED_MAX_WAIT_MS", "25"))

    # Optionnel: override du contrat USDC si autre réseau
    X402_ASSET_CONTRACT: str = os.getenv("X402_ASSET_CONTRACT", "")

    # Nouveau: régler en synchrone (settle) pour renvoyer X-PAYMENT-RESPONSE directement
    X402_SYNC_SETTLE: bool = os.getenv("X402_SYNC_SETTLE", "1") == "1"

settings = Settings()
