#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 4 — pinpoints and fixes the "design pas dans la charte / ne s'integre pas bien"
complaint: the "Donnees & Choix Conducteur de Travaux" screen (Go/No-Go decisions form,
routed at /projects/{id}/decisions) is the culprit.

Evidence gathered live from the running app before writing this patch:
- apps/web/src/app/layout.tsx sets `darkMode: ["class"]` (tailwind.config) and the body uses
  dual-theme tokens (`bg-[#F8FAFC] dark:bg-[#0C0F17]`, `selection:bg-amber-600`) -- i.e. the
  REAL app charte is light-by-default/dark-toggleable, with AMBER as the brand accent (matching
  apps/web/src/app/dashboard/company/page.tsx's `bg-amber-500/10 text-amber-600 dark:text-amber-400`
  badge, already used this session for the new "Assistant Q&A" button).
- decisions/page.tsx and components/decisions/decision-form.tsx hardcode a dark-only navy panel
  (bg-slate-900/90, bg-slate-950 inputs, text-white / text-slate-300/400 with NO light variants)
  accented in sky-blue (bg-sky-600, text-sky-400/300) instead of the site's amber accent. In light
  mode (the app's default) this renders as a solid dark rectangle with mismatched accent color
  sitting inside an otherwise light page shell -- precisely "ne s'integre pas bien".

Fix: add light-mode tokens alongside every dark: variant (Tailwind `darkMode: ["class"]` means
bare classes ARE the light/default appearance and `dark:`-prefixed classes only apply when the
`dark` class is present) and swap the sky-blue accent to the site's amber accent, matching
company/page.tsx. Semantic colors (emerald success, red delete) are left untouched.

Every block's expected occurrence count was verified live against the running file via grep
immediately before writing this script (protects against drift from the other AI's concurrent
edits, exactly like prior batches). apply_patch aborts per-file with zero writes on any mismatch.
"""
import sys

def apply_patch(path, replacements):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for label, old, new, expected_count in replacements:
        count = content.count(old)
        if count != expected_count:
            print(f"ABORT [{path}] block '{label}': found {count} occurrences (expected {expected_count}). No changes written.")
            return False
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: {path} patched ({len(replacements)} block(s)).")
    return True


if len(sys.argv) != 2:
    print("Usage: patch_batch4_decisions_charte.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
PAGE_TSX = f"{REPO_ROOT}/apps/web/src/app/projects/[id]/decisions/page.tsx"
FORM_TSX = f"{REPO_ROOT}/apps/web/src/components/decisions/decision-form.tsx"

results = []

# ─────────────────────────────────────────────────────────────────────────
# 1. decisions/page.tsx — page-level heading/subtitle
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(PAGE_TSX, [
    ("h1 dual-theme", 'text-2xl font-extrabold text-white', 'text-2xl font-extrabold text-slate-900 dark:text-white', 1),
    ("subtitle dual-theme", 'text-sm text-slate-400 mt-1', 'text-sm text-slate-500 dark:text-slate-400 mt-1', 1),
]))

# ─────────────────────────────────────────────────────────────────────────
# 2. decision-form.tsx — full dual-theme + amber accent pass
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(FORM_TSX, [
    ("outer container", 'bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-6',
     'bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-lg dark:shadow-2xl space-y-6', 1),
    ("header row border", 'flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800',
     'flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800', 1),
    ("h2 heading", 'text-base font-bold text-white flex items-center gap-2',
     'text-base font-bold text-slate-900 dark:text-white flex items-center gap-2', 1),
    ("h2 icon accent", 'w-5 h-5 text-sky-400', 'w-5 h-5 text-amber-500 dark:text-amber-400', 1),
    ("save button accent", 'flex items-center gap-2 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-glow disabled:opacity-50 transition-all',
     'flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-glow disabled:opacity-50 transition-all', 1),
    ("tabs row border", 'flex flex-wrap gap-2 border-b border-slate-800 pb-3',
     'flex flex-wrap gap-2 border-b border-slate-200 dark:border-slate-800 pb-3', 1),
    ("active tab accent", "bg-sky-500/20 text-sky-300 border border-sky-500/40",
     "bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/40", 1),
    ("inactive tab dual-theme", "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60",
     "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60", 1),
    ("date/number inputs (delai + date_demarrage)",
     'w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500',
     'w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-200 focus:outline-none focus:border-amber-500', 2),
    ("materiel textarea (leading-relaxed variant)",
     'w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 focus:outline-none focus:border-sky-500 leading-relaxed',
     'w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 rounded-lg p-3 text-xs text-slate-900 dark:text-slate-200 focus:outline-none focus:border-amber-500 leading-relaxed', 1),
    ("rse x2 + securite x1 textareas",
     'w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 focus:outline-none focus:border-sky-500"',
     'w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 rounded-lg p-3 text-xs text-slate-900 dark:text-slate-200 focus:outline-none focus:border-amber-500"', 3),
    ("checkbox row bg", 'flex items-center gap-3 p-3 rounded-lg bg-slate-950/60 border border-slate-800',
     'flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800', 1),
    ("checkbox control accent", 'rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-0 w-4 h-4',
     'rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-amber-500 focus:ring-0 w-4 h-4', 1),
    ("checkbox label", 'text-xs text-slate-300 cursor-pointer', 'text-xs text-slate-700 dark:text-slate-300 cursor-pointer', 1),
    ("tab section labels x8", 'text-xs font-semibold text-slate-300',
     'text-xs font-semibold text-slate-700 dark:text-slate-300', 8),
    ("helper text", 'text-[11px] text-slate-400', 'text-[11px] text-slate-500 dark:text-slate-400', 1),
    ("add cadre/phase buttons x2 accent",
     'flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300 font-semibold',
     'flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300 font-semibold', 2),
    ("cadre row container", 'p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 grid grid-cols-1 md:grid-cols-4 gap-3 items-center',
     'p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800/80 grid grid-cols-1 md:grid-cols-4 gap-3 items-center', 1),
    ("field labels x5", 'text-[10px] text-slate-400 uppercase font-semibold',
     'text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold', 5),
    ("small inputs x8 (cadres + phasage)",
     'w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-200',
     'w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded p-1.5 text-xs text-slate-900 dark:text-slate-200', 8),
    ("delete cadre button", 'text-slate-500 hover:text-red-400 p-1.5 rounded self-end mb-0.5',
     'text-slate-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400 p-1.5 rounded self-end mb-0.5', 1),
    ("phasage row container",
     'p-3 rounded-lg bg-slate-950 border border-slate-800 grid grid-cols-1 md:grid-cols-12 gap-3 items-center',
     'p-3 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 grid grid-cols-1 md:grid-cols-12 gap-3 items-center', 1),
    ("delete phase button", 'text-slate-500 hover:text-red-400 p-1"',
     'text-slate-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400 p-1"', 1),
]))

if not all(results):
    print("\nFAILED — see ABORT lines above. Each file's patch is atomic (all-or-nothing per file).")
    sys.exit(1)

print("\nALL BATCH-4 CHARTE PATCHES APPLIED SUCCESSFULLY.")
