"""
One-shot migration script to encrypt all existing LLM API keys in PlatformSettings with AES-256-GCM.
"""
import asyncio
import os
import sys
from datetime import datetime

# Ensure python path is set
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from app.core.db import AsyncSessionLocal
from app.core.config import settings
from app.models.entities import PlatformSettings
from app.core.crypto_vault import encrypt_api_key, decrypt_api_key, mask_api_key
from app.services.model_routing_service import DEFAULT_CUSTOM_PROVIDERS


async def migrate():
    print("=== STARTING AES-256-GCM LLM KEYS MIGRATION ===")
    async with AsyncSessionLocal() as db:
        stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
        res = await db.execute(stmt)
        ps = res.scalar_one_or_none()

        now = datetime.utcnow()
        current_settings = ps.settings if ps and ps.settings else {}
        
        # 1. Migrate legacy Anthropic key
        anthropic_raw = current_settings.get("anthropic_api_key") or settings.ANTHROPIC_API_KEY
        if anthropic_raw and not anthropic_raw.startswith("enc:v1:"):
            enc = encrypt_api_key(anthropic_raw)
            current_settings["anthropic_api_key"] = enc
            print(f"[Anthropic] Plain key migrated -> {enc[:20]}... (Masked: {mask_api_key(enc)})")
        elif anthropic_raw:
            print(f"[Anthropic] Already encrypted -> {anthropic_raw[:20]}... (Masked: {mask_api_key(anthropic_raw)})")

        # 2. Migrate legacy OpenAI key
        openai_raw = current_settings.get("openai_api_key") or settings.OPENAI_API_KEY
        if openai_raw and not openai_raw.startswith("enc:v1:"):
            enc = encrypt_api_key(openai_raw)
            current_settings["openai_api_key"] = enc
            print(f"[OpenAI] Plain key migrated -> {enc[:20]}... (Masked: {mask_api_key(enc)})")
        elif openai_raw:
            print(f"[OpenAI] Already encrypted -> {openai_raw[:20]}... (Masked: {mask_api_key(openai_raw)})")

        # 3. Migrate legacy Mistral key
        mistral_raw = current_settings.get("mistral_api_key") or settings.MISTRAL_API_KEY
        if mistral_raw and not mistral_raw.startswith("enc:v1:"):
            enc = encrypt_api_key(mistral_raw)
            current_settings["mistral_api_key"] = enc
            print(f"[Mistral] Plain key migrated -> {enc[:20]}... (Masked: {mask_api_key(enc)})")
        elif mistral_raw:
            print(f"[Mistral] Already encrypted -> {mistral_raw[:20]}... (Masked: {mask_api_key(mistral_raw)})")

        # 4. Migrate custom providers list
        providers = current_settings.get("custom_providers") or DEFAULT_CUSTOM_PROVIDERS
        migrated_providers = []
        for p in providers:
            p_copy = dict(p)
            raw_k = p_copy.get("api_key", "").strip()
            if raw_k and not raw_k.startswith("enc:v1:") and "•••" not in raw_k and "***" not in raw_k:
                enc = encrypt_api_key(raw_k)
                p_copy["api_key"] = enc
                print(f"[Custom Provider: {p_copy.get('name')}] Key migrated -> {enc[:20]}...")
            elif raw_k and raw_k.startswith("enc:v1:"):
                print(f"[Custom Provider: {p_copy.get('name')}] Key already encrypted -> {raw_k[:20]}...")
            
            # If Anthropic provider has no key, inject the encrypted anthropic key
            if p_copy.get("id") == "anthropic" and not p_copy.get("api_key") and current_settings.get("anthropic_api_key"):
                p_copy["api_key"] = current_settings["anthropic_api_key"]
                print(f"[Custom Provider: Anthropic] Injected encrypted master Anthropic key.")

            migrated_providers.append(p_copy)

        current_settings["custom_providers"] = migrated_providers
        current_settings["encryption_status"] = "AES-256-GCM Chiffré au repos"

        if ps:
            ps.settings = dict(current_settings)
            ps.updated_at = now
            flag_modified(ps, "settings")
        else:
            ps = PlatformSettings(id="global", settings=dict(current_settings), updated_at=now)
            db.add(ps)

        await db.commit()
        print("=== MIGRATION COMPLETED & COMMITTED TO POSTGRESQL ===")


if __name__ == "__main__":
    asyncio.run(migrate())
