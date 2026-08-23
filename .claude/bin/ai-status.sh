#!/usr/bin/env bash
# Prikazuje koji su eksterni AI provajderi stvarno upotrebljivi.
# Ne pravi nijedan naplativ poziv - proverava samo prisustvo i autentikaciju.

set -u

check() {
  local name="$1" bin="$2" auth_cmd="$3"
  if ! command -v "$bin" >/dev/null 2>&1; then
    printf '%-10s NEDOSTAJE   (nije instaliran)\n' "$name"
    return
  fi
  if eval "$auth_cmd" >/dev/null 2>&1; then
    printf '%-10s SPREMAN     (%s)\n' "$name" "$(command -v "$bin")"
  else
    printf '%-10s NEAUTENTIKOVAN\n' "$name"
  fi
}

echo "Eksterni AI provajderi:"
check "copilot" "copilot" "timeout 15 copilot --version"
check "grok"    "grok"    "test -s \"$HOME/.grok/auth.json\" || test -n \"\${XAI_API_KEY:-}\""
check "gemini"  "gemini"  "test -n \"\${GEMINI_API_KEY:-}\""
check "ollama"  "ollama"  "timeout 10 ollama list | tail -n +2 | grep -q ."

echo
echo "Napomena: 'SPREMAN' znaci da CLI postoji i da je auth provera prosla,"
echo "ne garantuje kvotu ili kredite."
