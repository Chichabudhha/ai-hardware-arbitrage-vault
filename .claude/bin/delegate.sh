#!/usr/bin/env bash
# Delegira jedan zadatak eksternom AI CLI-ju i loguje poziv sa provenance-om.
#
# Delegat radi READ-ONLY: dobija samo alate za citanje (view, glob, grep) i
# nikad ne pise u repo. Rezultat je savet koji Claude Code proverava pre
# primene - eksterni model nikad ne commit-uje i nikad ne racuna novac
# (CLAUDE.md princip 4, odluka D-005).
#
# Upotreba:
#   delegate.sh --role review   --task "Proveri risk scoring" --files src/deal_engine/risk.py
#   delegate.sh --role research --task @pitanje.md --provider copilot
#
# Uloge: review | tests | research | docs

set -euo pipefail

ROLE=""
TASK=""
FILES=""
PROVIDER="auto"
OUT_DIR=".claude/delegation-out"
LOG_FILE="operations/ai-delegacija-log.jsonl"

while [ $# -gt 0 ]; do
  case "$1" in
    --role)     ROLE="$2"; shift 2 ;;
    --task)     TASK="$2"; shift 2 ;;
    --files)    FILES="$2"; shift 2 ;;
    --provider) PROVIDER="$2"; shift 2 ;;
    *) echo "Nepoznat argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "$ROLE" ] || { echo "Nedostaje --role" >&2; exit 2; }
[ -n "$TASK" ] || { echo "Nedostaje --task" >&2; exit 2; }

# Alati su read-only. Imena se razlikuju po provajderu: copilot koristi
# view/glob/grep, grok interne ID-jeve (read_file/grep/list_dir).
CP_READ="view,glob,grep"
GROK_READ="read_file,grep,list_dir"

case "$ROLE" in
  review)   ROLE_BRIEF='Uradi code review. Trazi konkretne greske: netacna logika, izgubljena preciznost kod novca, tiho gutanje gresaka, nedostajuci edge case. Za svaki nalaz navedi fajl, liniju i konkretan scenario pada. Ne predlazi kozmeticke izmene.' ; CP_TOOLS="$CP_READ" ; GROK_TOOLS="$GROK_READ" ;;
  tests)    ROLE_BRIEF='Predlozi test slucajeve koji nedostaju. Za svaki: sta se testira, ulaz, ocekivani izlaz i zasto je bitan. Ne pisi ceo fajl, samo slucajeve.' ; CP_TOOLS="$CP_READ" ; GROK_TOOLS="$GROK_READ" ;;
  research) ROLE_BRIEF='Istrazi pitanje i navedi izvore sa URL-om i datumom. Jasno razdvoj sta je potvrdjeno od onoga sto je pretpostavka.' ; CP_TOOLS="$CP_READ,web_fetch" ; GROK_TOOLS="$GROK_READ,web_search,web_fetch" ;;
  docs)     ROLE_BRIEF='Napisi ili doradi dokumentaciju na srpskom (ekavica). Bez marketinskog tona, bez ponavljanja.' ; CP_TOOLS="$CP_READ" ; GROK_TOOLS="$GROK_READ" ;;
esac

# Delegat nema shell pristup. Ako mu zatreba provera, mora da je opise, ne izvrsi.
ROLE_BRIEF="$ROLE_BRIEF Nemas shell ni mogucnost pokretanja koda. Ne pokusavaj da izvrsis testove; ako ti treba provera, opisi tacan slucaj koji orkestrator treba da pokrene."

# --- Zadatak iz fajla ------------------------------------------------------
if [ "${TASK:0:1}" = "@" ]; then
  TASK_FILE="${TASK:1}"
  [ -f "$TASK_FILE" ] || { echo "Nema fajla: $TASK_FILE" >&2; exit 2; }
  TASK="$(cat "$TASK_FILE")"
fi

# --- Zastita tajni (CLAUDE.md sekcija 6) -----------------------------------
# Sve sto se posalje eksternom servisu je objavljeno. Blokiraj kredencijale.
# Kljucevi cesto sadrze '-' i '_' (npr. sk-ant-api03-...), pa klasa mora da ih ukljuci.
SECRET_PATTERN='(sk-[A-Za-z0-9_-]{16,}|xai-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(ANTHROPIC|GEMINI|GOOGLE|OPENAI|XAI|GROK|GITHUB)_(API_)?(KEY|TOKEN)=[^[:space:]]+)'

deny_secret() {
  echo "ODBIJENO: sadrzaj lici na kredencijal ($1). Nista nije poslato." >&2
  exit 3
}

if printf '%s' "$TASK" | grep -qE "$SECRET_PATTERN"; then
  deny_secret "--task"
fi

PAYLOAD=""
if [ -n "$FILES" ]; then
  IFS=',' read -ra FILE_LIST <<< "$FILES"
  for f in "${FILE_LIST[@]}"; do
    [ -f "$f" ] || { echo "Nema fajla: $f" >&2; exit 2; }
    case "$f" in
      *.env|*.env.*|*/secrets/*|secrets/*|*.pem|*.key)
        echo "ODBIJENO: '$f' je fajl sa tajnama. Nista nije poslato." >&2; exit 3 ;;
    esac
    if grep -qE "$SECRET_PATTERN" "$f"; then
      deny_secret "$f"
    fi
    PAYLOAD="${PAYLOAD}
--- $f ---
$(cat "$f")
"
  done
fi

# --- Pravila koja delegat mora da postuje ----------------------------------
RULES='Ti si pomocni agent na projektu AI Hardware Arbitrage Serbia. Pravila:
1. Ne izmisljaj podatke, cene, kurseve, poreze, troskove ni dostupnost. Ako ne znas, reci "NE ZNAM".
2. UNKNOWN nije isto sto i 0.
3. Ne racunaj novac, profit, ROI ni score - to radi deterministicki Python kod, ne ti.
4. Ne predlazi zaobilazenje ToS-a, rate limita, robots.txt-a ni anti-bot mera.
5. Ne menjaj fajlove. Samo analiziraj i predlozi; odluku donosi orkestrator.
6. Odgovaraj na srpskom (ekavica), kratko i operativno. Kod i identifikatori na engleskom.'

case "$ROLE" in
  review)   ROLE_BRIEF='Uradi code review. Trazi konkretne greske: netacna logika, izgubljena preciznost kod novca, tiho gutanje gresaka, nedostajuci edge case. Za svaki nalaz navedi fajl, liniju i konkretan scenario pada. Ne predlazi kozmeticke izmene.' ; TOOLS="view,glob,grep" ;;
  tests)    ROLE_BRIEF='Predlozi test slucajeve koji nedostaju. Za svaki: sta se testira, ulaz, ocekivani izlaz i zasto je bitan. Ne pisi ceo fajl, samo slucajeve.' ; TOOLS="view,glob,grep" ;;
  research) ROLE_BRIEF='Istrazi pitanje i navedi izvore sa URL-om i datumom. Jasno razdvoj sta je potvrdjeno od onoga sto je pretpostavka.' ; TOOLS="view,glob,grep,web_fetch" ;;
  docs)     ROLE_BRIEF='Napisi ili doradi dokumentaciju na srpskom (ekavica). Bez marketinskog tona, bez ponavljanja.' ; TOOLS="view,glob,grep" ;;
esac

PROMPT="$RULES

ZADATAK ($ROLE): $ROLE_BRIEF

$TASK
$PAYLOAD"

# --- Izbor provajdera ------------------------------------------------------
have_copilot() { command -v copilot >/dev/null 2>&1; }
have_grok()    { command -v grok >/dev/null 2>&1 && { [ -s "$HOME/.grok/auth.json" ] || [ -n "${XAI_API_KEY:-}" ]; }; }
have_gemini()  { command -v gemini >/dev/null 2>&1 && [ -n "${GEMINI_API_KEY:-}" ]; }
have_ollama()  { command -v ollama >/dev/null 2>&1 && ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL:-qwen3:4b}"; }

# Redosled u 'auto': prvo besplatno i lokalno (ollama), pa besplatna kvota
# (gemini), pa naplatno (copilot, grok). Lokalni model ne salje nista van.
if [ "$PROVIDER" = "auto" ]; then
  if   have_ollama;  then PROVIDER="ollama"
  elif have_gemini;  then PROVIDER="gemini"
  elif have_copilot; then PROVIDER="copilot"
  elif have_grok;    then PROVIDER="grok"
  else echo "Nema dostupnog provajdera. Pokreni .claude/bin/ai-status.sh" >&2; exit 4; fi
fi

# Ollama i gemini -p nemaju repo alate: vide samo ono sto im posaljemo kroz
# --files. Bez toga bi odgovarali napamet, pa je prazan --files greska.
case "$PROVIDER" in
  ollama|gemini)
    if [ -z "$FILES" ] && [ "$ROLE" != "research" ]; then
      echo "Provajder '$PROVIDER' nema pristup repou; navedi --files sa sadrzajem za analizu." >&2
      exit 2
    fi
    ;;
esac

mkdir -p "$OUT_DIR" "$(dirname "$LOG_FILE")"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$OUT_DIR/${STAMP}-${ROLE}-${PROVIDER}.md"

# Ogranicenje trajanja mora da bude UNUTAR skripte. Ako spoljni `timeout` ubije
# ceo proces, log se nikad ne upise, a zapis koji nedostaje se ne razlikuje od
# poziva koji se nikad nije desio.
DELEGATE_TIMEOUT="${DELEGATE_TIMEOUT:-600}"
MAX_TURNS="${DELEGATE_MAX_TURNS:-12}"

case "$PROVIDER" in
  copilot)
    set +e
    timeout "$DELEGATE_TIMEOUT"       copilot -p "$PROMPT" --available-tools "$CP_TOOLS" --allow-all-tools               --no-ask-user --no-color --log-level none > "$OUT_FILE" 2>&1
    STATUS=$?
    set -e
    ;;
  grok)
    have_grok || { echo "grok nije autentikovan (grok login --device-code)" >&2; exit 4; }
    # Bez --permission-mode plan: u plan rezimu grok trazi shell, biva blokiran
    # i vrti se u prazno umesto da odgovori. Read-only se postize allowlistom.
    set +e
    timeout "$DELEGATE_TIMEOUT"       grok -p "$PROMPT" --output-format plain --tools "$GROK_TOOLS"            --max-turns "$MAX_TURNS" --disallowed-tools "Agent" > "$OUT_FILE" 2>&1
    STATUS=$?
    set -e
    ;;
  ollama)
    have_ollama || { echo "ollama nema model ${OLLAMA_MODEL:-qwen3:4b} (ollama pull)" >&2; exit 4; }
    set +e
    printf '%s' "$PROMPT" | timeout "$DELEGATE_TIMEOUT"       ollama run "${OLLAMA_MODEL:-qwen3:4b}" > "$OUT_FILE" 2>&1
    STATUS=$?
    set -e
    ;;
  gemini)
    have_gemini || { echo "gemini nije instaliran ili nema GEMINI_API_KEY" >&2; exit 4; }
    set +e
    timeout "$DELEGATE_TIMEOUT"       gemini -p "$PROMPT" > "$OUT_FILE" 2>&1
    STATUS=$?
    set -e
    ;;
  *) echo "Nepoznat provajder: $PROVIDER" >&2; exit 2 ;;
esac

if [ "$STATUS" -eq 124 ]; then
  echo "UPOZORENJE: prekinuto posle ${DELEGATE_TIMEOUT}s (exit 124)." >> "$OUT_FILE"
fi

# --- Provenance (CLAUDE.md princip 5) --------------------------------------
TASK_HASH="$(printf '%s' "$PROMPT" | sha256sum | cut -c1-16)"
printf '{"timestamp":"%s","provider":"%s","role":"%s","files":"%s","prompt_sha256_16":"%s","exit_code":%d,"output":"%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$PROVIDER" "$ROLE" "$FILES" "$TASK_HASH" "$STATUS" "$OUT_FILE" \
  >> "$LOG_FILE"

echo "provajder: $PROVIDER | uloga: $ROLE | exit: $STATUS"
echo "izlaz: $OUT_FILE"
echo "---"
cat "$OUT_FILE"
