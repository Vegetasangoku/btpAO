"""
DÉPRÉCIÉ (01/09) — ce module n'est appelé nulle part dans le code (vérifié par grep sur
tout apps/api/app). Il contenait deux fonctions (search_dce_context, search_company_knowledge)
appelant des RPC Supabase via httpx, avec un repli codé en dur qui renvoyait un faux extrait
de règlement de consultation et une fausse certification QUALIBAT comme s'il s'agissait de
vraies données -- jamais exécuté en production, mais un piège pour quiconque le réactiverait
par erreur en pensant qu'il alimente la génération.

Le vrai mécanisme de recherche vectorielle (RAG) qui alimente réellement la génération de
mémoire est implémenté directement dans apps/api/app/workers/tasks.py::generate_section_task
(recherche pgvector directe sur DCEEmbedding et KnowledgeVector via SQLAlchemy, avec repli
sur les enregistrements les plus récents en cas d'échec de la recherche sémantique -- jamais
de contenu fabriqué).

Fichier volontairement vidé plutôt que supprimé (permissions d'écriture du pont appareil).
Si aucune référence n'apparaît plus dans une recherche future, ce fichier peut être supprimé
du dépôt.
"""
