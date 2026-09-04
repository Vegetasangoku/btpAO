"""
Backfill ponctuel (30/08) : indexe par fragments (chunking + embedding) le texte
COMPLET de chaque company_assets existant dans knowledge_vectors.

Contexte : avant ce correctif, app/api/knowledge.py ne calculait un embedding que
sur extracted_text[:4000] -- les ~4000 premiers caracteres de tout document depose,
soit environ 2 pages, quelle que soit sa longueur reelle. Les mémoires techniques et
réponses à appels d'offres passés (le cas d'usage prioritaire signalé par
l'utilisateur : "le plus important sera la qualité de l'analyse des anciens
dossiers") étaient donc seulement partiellement indexés en recherche sémantique.

Ce script est idempotent (sûr à relancer) : il ignore tout asset qui a déjà des
fragments dans knowledge_vectors. Pour chaque asset sans fragment :
  1. Si un fichier source est encore en stockage (s3_url), le retélécharge et
     ré-extrait son texte intégral (même logique que l'upload direct).
  2. Sinon, se rabat sur la description stockée (jusqu'à 12000 caractères) --
     déjà 3x mieux que l'ancien plafond de 4000, même si ce n'est pas le texte
     intégral d'origine pour un document qui dépasserait 12000 caractères.
  3. Découpe le texte obtenu en fragments (~1200c) et calcule un embedding par
     fragment, exactement comme le fait désormais l'upload direct.

Usage : depuis apps/api/, `python3 scripts/backfill_knowledge_vectors.py`
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, func

from app.core.db import AsyncSessionLocal
from app.models.entities import CompanyAsset, KnowledgeVector
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service
from app.core.storage import storage_service
from app.api.knowledge import extract_text_from_upload


async def backfill():
    print("=== BACKFILL knowledge_vectors : demarrage ===")
    async with AsyncSessionLocal() as db:
        await embedding_service.sync_platform_key(db)

        assets_stmt = (
            select(CompanyAsset)
            .where(CompanyAsset.status != "obsolete")
            .order_by(CompanyAsset.created_at.asc())
        )
        res = await db.execute(assets_stmt)
        assets = res.scalars().all()
        print(f"{len(assets)} company_assets actifs trouves.")

        processed, skipped, errors = 0, 0, 0
        for asset in assets:
            existing_stmt = (
                select(func.count())
                .select_from(KnowledgeVector)
                .where(KnowledgeVector.asset_id == asset.id)
            )
            existing_count = (await db.execute(existing_stmt)).scalar_one()
            if existing_count > 0:
                print(f"SKIP  [{asset.id}] '{asset.title[:60]}' -- {existing_count} fragment(s) deja indexe(s)")
                skipped += 1
                continue

            full_text = None
            source = None
            if asset.s3_url:
                try:
                    file_bytes = storage_service.download_file(str(asset.tenant_id), asset.s3_url)
                    filename = asset.s3_url.rsplit("/", 1)[-1]
                    extracted_text, status_state, error_msg = extract_text_from_upload(filename, file_bytes)
                    if extracted_text and status_state == "indexed":
                        full_text = extracted_text
                        source = "fichier source re-extrait"
                    else:
                        print(f"      notice extraction pour {asset.id}: status={status_state} error={error_msg}")
                except Exception as e:
                    print(f"      notice telechargement/extraction pour {asset.id}: {e}")

            if not full_text:
                full_text = asset.description or ""
                source = "description stockee (fichier source indisponible ou echec d'extraction)"

            if not full_text.strip():
                print(f"SKIP  [{asset.id}] '{asset.title[:60]}' -- aucun texte disponible")
                skipped += 1
                continue

            try:
                pages = [{"page_number": 1, "text": full_text}]
                chunks = chunking_service.chunk_document_pages(pages)
                if not chunks:
                    print(f"SKIP  [{asset.id}] '{asset.title[:60]}' -- 0 fragment genere")
                    skipped += 1
                    continue
                vectors = embedding_service.generate_batch_embeddings([c["content"] for c in chunks])
                for c, vec in zip(chunks, vectors):
                    db.add(KnowledgeVector(
                        id=uuid.uuid4(),
                        tenant_id=asset.tenant_id,
                        asset_id=asset.id,
                        category=asset.category,
                        content=c["content"],
                        embedding=vec,
                        metadata_json={
                            "asset_title": asset.title,
                            "chunk_index": c["chunk_index"],
                            "section_title": c.get("section_title"),
                            "char_count": len(c["content"]),
                            "backfill_source": source,
                        },
                        created_at=datetime.now(timezone.utc),
                    ))
                await db.commit()
                print(f"OK    [{asset.id}] '{asset.title[:60]}' -- {len(chunks)} fragment(s) indexe(s) ({source}, {len(full_text)} caracteres)")
                processed += 1
            except Exception as e:
                await db.rollback()
                print(f"ERROR [{asset.id}] '{asset.title[:60]}' -- {e}")
                errors += 1

        print(f"=== BACKFILL termine : {processed} indexes, {skipped} ignores, {errors} erreurs (sur {len(assets)} actifs) ===")


if __name__ == "__main__":
    asyncio.run(backfill())
