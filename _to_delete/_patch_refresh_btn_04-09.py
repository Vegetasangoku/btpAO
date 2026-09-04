import sys

def patch(path, replacements, label):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for old, new, expect in replacements:
        count = content.count(old)
        if count != expect:
            print(f"[{label}] MISMATCH: expected {expect}, found {count} for anchor:\n{old!r}")
            sys.exit(1)
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[{label}] OK: {len(replacements)} replacement(s) applied")

PAGE = "apps/web/src/app/dashboard/company/page.tsx"

patch(PAGE, [
    (
        "  Download,\n} from 'lucide-react';",
        "  Download,\n  RefreshCw,\n} from 'lucide-react';",
        1,
    ),
    (
        "  const [isAddingUrl, setIsAddingUrl] = useState(false);\n",
        "  const [isAddingUrl, setIsAddingUrl] = useState(false);\n  const [refreshingUrlId, setRefreshingUrlId] = useState<string | null>(null);\n",
        1,
    ),
    (
        """  async function handleDeleteUrl(id: string) {
    if (!confirm('Supprimer ce site de référence ?')) return;
    try {
      await api.deleteReferenceUrl(id);
      setReferenceUrls((prev) => prev.filter((u) => u.id !== id));
    } catch (err: any) {
      alert('Erreur: ' + err.message);
    }
  }
""",
        """  async function handleDeleteUrl(id: string) {
    if (!confirm('Supprimer ce site de référence ?')) return;
    try {
      await api.deleteReferenceUrl(id);
      setReferenceUrls((prev) => prev.filter((u) => u.id !== id));
    } catch (err: any) {
      alert('Erreur: ' + err.message);
    }
  }

  async function handleRefreshUrl(id: string) {
    setRefreshingUrlId(id);
    try {
      await api.refreshReferenceUrl(id);
      await loadUrls();
    } catch (err: any) {
      alert('Erreur actualisation: ' + err.message);
    } finally {
      setRefreshingUrlId(null);
    }
  }
""",
        1,
    ),
    (
        """                        <td className="py-3 px-4">
                          <span className="badge-pill-emerald text-[10px]">
                            Indexé
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => handleDeleteUrl(u.id)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                            title="Supprimer"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>""",
        """                        <td className="py-3 px-4">
                          <span
                            className={
                              u.status === 'broken'
                                ? 'badge-pill-red text-[10px]'
                                : u.status === 'fetching'
                                ? 'badge-pill-amber text-[10px]'
                                : u.status === 'active'
                                ? 'badge-pill-emerald text-[10px]'
                                : 'badge-pill-slate text-[10px]'
                            }
                          >
                            {u.status === 'broken'
                              ? 'Erreur'
                              : u.status === 'fetching'
                              ? 'Récupération…'
                              : u.status === 'active'
                              ? 'Indexé'
                              : u.status}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => handleRefreshUrl(u.id)}
                            disabled={refreshingUrlId === u.id}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-hl hover:bg-hl/10 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-wait mr-1"
                            title="Actualiser"
                          >
                            <RefreshCw className={`w-4 h-4 ${refreshingUrlId === u.id ? 'animate-spin' : ''}`} />
                          </button>
                          <button
                            onClick={() => handleDeleteUrl(u.id)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                            title="Supprimer"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>""",
        1,
    ),
], "company/page.tsx — bouton Actualiser + badge statut réel")
