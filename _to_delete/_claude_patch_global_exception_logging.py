#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnostic patch: registers a global FastAPI exception handler so that ANY
unhandled exception, on ANY route, is:
1. Written with its full traceback to apps/api/_debug_unhandled_errors.log
   (readable by Claude via the device bridge, since server-process stdout is
   not otherwise reachable).
2. Returned to the client as a clean JSON 500 with the real exception class
   and message, instead of whatever opaque failure was happening before.

Why: /api/export/compile, /api/generate/section, and
/api/knowledge/template/suggested all fail identically (browser sees
"Failed to fetch", DevTools network panel shows 503) with NO explanation
findable anywhere in the codebase (no generic exception handler existed
before this patch, confirmed by exhaustive grep). This is the fastest safe
way to get the real, authoritative error text without terminal access.

Exact-match-count-of-1 verified before writing; aborts with zero writes if
the expected block isn't found exactly once.
"""
import sys

def apply_patch(path, replacements):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for label, old, new in replacements:
        count = content.count(old)
        if count != 1:
            print(f"ABORT [{path}] block '{label}': found {count} occurrences (expected 1). No changes written.")
            sys.exit(1)
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: {path} patched ({len(replacements)} block(s)).")


if len(sys.argv) != 2:
    print("Usage: patch_global_exception_logging.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
MAIN_PY = f"{REPO_ROOT}/apps/api/app/main.py"

replacements = [
    (
        "global-exception-handler",
        '''from fastapi.responses import RedirectResponse, JSONResponse


app = FastAPI(''',
        '''from fastapi.responses import RedirectResponse, JSONResponse

import logging
import traceback
from pathlib import Path
from fastapi import Request

_DEBUG_LOG_PATH = Path(__file__).resolve().parent.parent / "_debug_unhandled_errors.log"


app = FastAPI(''',
    ),
    (
        "global-exception-handler-registration",
        '''@app.get("/docs", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/api/docs")''',
        '''@app.get("/docs", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/api/docs")


@app.exception_handler(Exception)
async def log_and_report_unhandled_exceptions(request: Request, exc: Exception):
    """
    DIAGNOSTIC (Claude, 23/08) — TEMPORARY. Catches any exception no route
    handler catches, logs the full traceback to a file Claude can read via
    the device bridge (server stdout is not otherwise reachable), and
    returns a clean, honest 500 instead of an opaque failure.
    """
    tb = traceback.format_exc()
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\\n\\n=== {request.method} {request.url.path} ===\\n{tb}")
    except Exception:
        pass
    logging.getLogger("uvicorn.error").error(
        "Unhandled exception on %s %s:\\n%s", request.method, request.url.path, tb
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erreur interne ({exc.__class__.__name__}) : {str(exc)[:300]}"},
    )''',
    ),
]

apply_patch(MAIN_PY, replacements)
print("ALL PATCHES APPLIED SUCCESSFULLY.")
