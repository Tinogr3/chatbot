#!/usr/bin/env bash
# Reproduce escenarios PR-01 a PR-12 contra la API local y recoge resultados.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
SUFFIX="${SUFFIX:-$(date +%s)}"
PASS="TestPass123!"
LOG_DIR="/tmp/cotutor-pr-tests-${SUFFIX}"
mkdir -p "$LOG_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; RESET='\033[0m'

pass() { echo -e "${GREEN}[PASS]${RESET} $*"; }
fail() { echo -e "${RED}[FAIL]${RESET} $*"; }
info() { echo -e "${CYAN}[INFO]${RESET} $*"; }
warn() { echo -e "${YELLOW}[WARN]${RESET} $*"; }

# ── Usuarios de prueba ───────────────────────────────────────────────────────
F1="prf1_${SUFFIX}"
F2="prf2_${SUFFIX}"
A1="pra1_${SUFFIX}"
SESSION_F1="${F1}__proyecto_pr"
SESSION_F2="${F2}__proyecto_pr"
SESSION_A1="${A1}__proyecto_pr"

register() {
  local user="$1" role="$2"
  curl -s -o "$LOG_DIR/reg_${user}.json" -w "%{http_code}" \
    -X POST "$BASE_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$user\",\"password\":\"$PASS\",\"role\":\"$role\"}"
}

login() {
  local user="$1"
  curl -s "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$user\",\"password\":\"$PASS\"}"
}

token_of() {
  python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])" < "$1"
}

chat() {
  local token="$1" session="$2" msg="$3"
  local extra="${4:-}"
  curl -s -w "\n__HTTP__%{http_code}" \
    -X POST "$BASE_URL/chat" \
    -H "Authorization: Bearer $token" \
    -H "X-Session-Id: $session" \
    -H "Content-Type: application/json" \
    -d "{\"message\":$(python3 -c "import json; print(json.dumps('$msg'))")${extra}}"
}

make_min_pdf() {
  local out="$1" text="$2"
  python3 - "$out" "$text" <<'PY'
import sys
from pathlib import Path
out, text = sys.argv[1], sys.argv[2]
# PDF mínimo con stream de texto embebido
content = f"""BT /F1 12 Tf 50 700 Td ({text}) Tj ET"""
stream = content.encode("latin-1", errors="replace")
parts = []
parts.append(b"%PDF-1.4\n")
offsets = [0]
def add(s: bytes):
    offsets.append(len(b"".join(parts)))
    parts.append(s)
add(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
add(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
add(b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n")
add(f"4 0 obj<< /Length {len(stream)} >>stream\n".encode() + stream + b"\nendstream\nendobj\n")
add(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
body = b"".join(parts)
xref_pos = len(body)
xref = b"xref\n0 6\n0000000000 65535 f \n"
for off in offsets[1:]:
    xref += f"{off:010d} 00000 n \n".encode()
trailer = b"trailer<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
Path(out).write_bytes(body + xref + trailer)
PY
}

make_fake_pdf() {
  echo "esto no es un pdf valido" > "$1"
}

upload_pdf() {
  local token="$1" session="$2" file="$3"
  curl -s -w "\n__HTTP__%{http_code}" \
    -X POST "$BASE_URL/upload" \
    -H "Authorization: Bearer $token" \
    -H "X-Session-Id: $session" \
    -F "file=@${file};type=application/pdf"
}

poll_task() {
  local token="$1" task_id="$2" max="${3:-60}"
  local i=0 status=""
  while [[ $i -lt $max ]]; do
    local resp
    resp=$(curl -s "$BASE_URL/status/$task_id" -H "Authorization: Bearer $token")
    status=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status',''))" <<<"$resp")
    echo "$resp" > "$LOG_DIR/task_${task_id}.json"
    [[ "$status" == "SUCCESS" || "$status" == "FAILURE" ]] && { echo "$resp"; return 0; }
    sleep 2
    ((i++))
  done
  echo "{\"status\":\"TIMEOUT\"}"
}

capture_logs() {
  local tag="$1"
  docker compose --env-file /home/tino/projectos/cotutor-ia/.env logs --tail=40 backend worker 2>/dev/null \
    > "$LOG_DIR/logs_${tag}.txt" || true
}

echo "═══════════════════════════════════════════════════════════════"
echo " PRUEBAS PR-01 … PR-12  |  suffix=$SUFFIX  |  logs=$LOG_DIR"
echo "═══════════════════════════════════════════════════════════════"

# Setup usuarios
for u in "$F1:formador" "$F2:formador" "$A1:alumno"; do
  name="${u%%:*}"; role="${u##*:}"
  code=$(register "$name" "$role")
  if [[ "$code" != "201" && "$code" != "200" ]]; then
    warn "Registro $name devolvió HTTP $code (puede existir); intentando login"
  fi
done

login "$F1" > "$LOG_DIR/login_f1.json"
login "$F2" > "$LOG_DIR/login_f2.json"
login "$A1" > "$LOG_DIR/login_a1.json"
TOK_F1=$(token_of "$LOG_DIR/login_f1.json")
TOK_F2=$(token_of "$LOG_DIR/login_f2.json")
TOK_A1=$(token_of "$LOG_DIR/login_a1.json")
info "Usuarios listos: $F1, $F2, $A1"

# PDFs de prueba
PDF_BIO="$LOG_DIR/biologia.pdf"
PDF_HIST="$LOG_DIR/historia.pdf"
FAKE_PDF="$LOG_DIR/fake.pdf"
make_min_pdf "$PDF_BIO" "La fotosintesis convierte luz solar en energia quimica en las plantas."
make_min_pdf "$PDF_HIST" "La Revolucion Francesa comenzo en 1789 con la toma de la Bastilla."
make_fake_pdf "$FAKE_PDF"

RESULTS=()

# ── PR-01 Ingesta concurrente ─────────────────────────────────────────────────
info "PR-01: ingesta concurrente masiva"
START=$(date +%s%N)
upload_pdf "$TOK_F1" "$SESSION_F1" "$PDF_BIO" > "$LOG_DIR/pr01_f1.txt" &
upload_pdf "$TOK_F2" "$SESSION_F2" "$PDF_HIST" > "$LOG_DIR/pr01_f2.txt" &
upload_pdf "$TOK_F1" "$SESSION_F1" "$PDF_BIO" > "$LOG_DIR/pr01_f1b.txt" &
wait
END=$(date +%s%N)
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
T1=$(grep -oP '__HTTP__\K\d+' "$LOG_DIR/pr01_f1.txt" || echo 0)
T2=$(grep -oP '__HTTP__\K\d+' "$LOG_DIR/pr01_f2.txt" || echo 0)
ELAPSED_MS=$(( (END - START) / 1000000 ))
if [[ "$HEALTH" == "200" && "$T1" == "200" && "$T2" == "200" ]]; then
  pass "PR-01: uploads encolados ($ELAPSED_MS ms), health=$HEALTH"
  RESULTS+=("PR-01: ÉXITO")
else
  fail "PR-01: health=$HEALTH uploads=$T1/$T2"
  RESULTS+=("PR-01: FALLO")
fi
capture_logs "pr01"

# ── PR-02 Acceso cruzado ──────────────────────────────────────────────────────
info "PR-02: acceso cruzado horizontal"
CODE=$(curl -s -o "$LOG_DIR/pr02.json" -w "%{http_code}" \
  -X POST "$BASE_URL/chat" \
  -H "Authorization: Bearer $TOK_F2" \
  -H "X-Session-Id: $SESSION_F1" \
  -H "Content-Type: application/json" \
  -d '{"message":"¿Qué documentos hay?"}')
if [[ "$CODE" == "403" ]]; then
  pass "PR-02: HTTP 403 al acceder a sesión ajena"
  RESULTS+=("PR-02: ÉXITO")
else
  fail "PR-02: esperaba 403, obtuvo $CODE"
  RESULTS+=("PR-02: FALLO ($CODE)")
fi
capture_logs "pr02"

# Esperar ingesta PR-01 para pruebas RAG
info "Esperando tareas de ingesta..."
for f in pr01_f1.txt pr01_f2.txt; do
  tid=$(python3 -c "import re,sys; m=re.search(r'\"task_id\":\"([^\"]+)\"', open(sys.argv[1]).read()); print(m.group(1) if m else '')" "$LOG_DIR/$f")
  [[ -n "$tid" ]] && poll_task "$TOK_F1" "$tid" 90 > /dev/null || true
done

# ── PR-03 Mitigación alucinaciones ────────────────────────────────────────────
info "PR-03: tema fuera del temario"
chat "$TOK_F1" "$SESSION_F1" "Explica en detalle la teoría de cuerdas en física cuántica y sus 11 dimensiones" \
  > "$LOG_DIR/pr03.txt" || true
ANSWER=$(sed '/__HTTP__/d' "$LOG_DIR/pr03.txt")
HTTP3=$(grep -oP '__HTTP__\K\d+' "$LOG_DIR/pr03.txt" || echo 0)
# Heurística: admite desconocimiento o no inventa con seguridad
if python3 - "$ANSWER" <<'PY'
import sys, re
t = sys.argv[1].lower()
signals = [
    r"no (est[aá]|tengo|encuentro|hay|disponible|puedo)",
    r"no (est[aá]|se) (en|mencion|inclu)",
    r"desconoc",
    r"no (aparece|figura)",
    r"fuera del (material|temario|contenido)",
    r"no tengo informaci",
    r"no hay (informaci|document|material)",
    r"no est[aá] disponible",
    r"no (puedo|soy capaz)",
    r"sube|carga.*document",
]
if any(re.search(p, t) for p in signals):
    sys.exit(0)
# Si la respuesta es muy corta o evasiva también vale
if len(t) < 400 and ("?" in t or "document" in t):
    sys.exit(0)
sys.exit(1)
PY
then
  pass "PR-03: respuesta admite límites del material"
  RESULTS+=("PR-03: ÉXITO")
else
  warn "PR-03: respuesta no clara; revisar manualmente (HTTP $HTTP3)"
  echo "$ANSWER" | head -c 500 > "$LOG_DIR/pr03_snippet.txt"
  RESULTS+=("PR-03: REVISAR")
fi
capture_logs "pr03"

# ── PR-04 Control de roles ────────────────────────────────────────────────────
info "PR-04: alumno en rutas de formador"
CODE=$(curl -s -o "$LOG_DIR/pr04.json" -w "%{http_code}" \
  -H "Authorization: Bearer $TOK_A1" \
  -H "X-Session-Id: $SESSION_A1" \
  "$BASE_URL/trainer/learning-outcomes")
if [[ "$CODE" == "403" ]]; then
  pass "PR-04: HTTP 403 en /trainer/learning-outcomes"
  RESULTS+=("PR-04: ÉXITO")
else
  fail "PR-04: esperaba 403, obtuvo $CODE"
  RESULTS+=("PR-04: FALLO ($CODE)")
fi
capture_logs "pr04"

# ── PR-05 Smart Router saludo ─────────────────────────────────────────────────
info "PR-05: saludo genérico → CONVERSACION"
START5=$(date +%s%N)
chat "$TOK_A1" "$SESSION_A1" "Hola, buenos días" > "$LOG_DIR/pr05.txt" || true
END5=$(date +%s%N)
LAT5=$(( (END5 - START5) / 1000000 ))
HTTP5=$(grep -oP '__HTTP__\K\d+' "$LOG_DIR/pr05.txt" || echo 0)
docker compose --env-file /home/tino/projectos/cotutor-ia/.env logs --tail=30 backend 2>/dev/null \
  | tee "$LOG_DIR/logs_pr05.txt" | grep -qi "CONVERSACION\|category=CONVERSACION" && ROUTED=1 || ROUTED=0
if [[ "$HTTP5" == "200" && "$LAT5" -lt 30000 ]]; then
  if [[ "$ROUTED" == "1" ]]; then
    pass "PR-05: respuesta rápida (${LAT5}ms) y router CONVERSACION en logs"
    RESULTS+=("PR-05: ÉXITO")
  else
    warn "PR-05: HTTP 200 (${LAT5}ms) pero sin log CONVERSACION explícito"
    RESULTS+=("PR-05: PARCIAL")
  fi
else
  fail "PR-05: HTTP=$HTTP5 lat=${LAT5}ms"
  RESULTS+=("PR-05: FALLO")
fi

# ── PR-06 Andamiaje socrático ───────────────────────────────────────────────────
info "PR-06: petición de solución directa"
chat "$TOK_F1" "$SESSION_F1" "Quiero aprender sobre la fotosíntesis" \
  '{"learning_mode":false}' > "$LOG_DIR/pr06a.txt" || true
chat "$TOK_F1" "$SESSION_F1" "Dame directamente la respuesta completa y la solución final sin preguntas" \
  '{"learning_mode":true,"learning_topic":"fotosíntesis","last_learning_content":"intro fotosíntesis"}' \
  > "$LOG_DIR/pr06.txt" || true
ANS6=$(sed '/__HTTP__/d' "$LOG_DIR/pr06.txt")
if python3 - "$ANS6" <<'PY'
import sys, re
t = sys.argv[1]
# No debe ser una solución magistral larga sin pregunta
has_question = "?" in t
forbidden = len(t) > 1200 and not has_question
guide_words = re.search(r"(piensa|reflexi|intenta|qué opinas|cómo|crees|pregunta|pista|guía)", t, re.I)
if has_question or guide_words:
    sys.exit(0)
if forbidden:
    sys.exit(1)
sys.exit(0)
PY
then
  pass "PR-06: respuesta con pregunta guía / sin solución directa"
  RESULTS+=("PR-06: ÉXITO")
else
  warn "PR-06: posible solución directa; revisar logs"
  RESULTS+=("PR-06: REVISAR")
fi
capture_logs "pr06"

# ── PR-07 Aislamiento vectorial ───────────────────────────────────────────────
info "PR-07: aislamiento entre proyectos"
# F2 pregunta por contenido solo en F1
chat "$TOK_F2" "$SESSION_F2" "¿Qué puedes decirme sobre la fotosíntesis y la luz solar en plantas?" \
  > "$LOG_DIR/pr07.txt" || true
ANS7=$(sed '/__HTTP__/d' "$LOG_DIR/pr07.txt")
if python3 - "$ANS7" <<'PY'
import sys, re
t = sys.argv[1].lower()
# No debería hablar con detalle de biología del otro proyecto
if re.search(r"fotos[ií]ntesis", t) and re.search(r"luz solar|energ[ií]a qu[ií]mica|plantas", t):
    sys.exit(1)
sys.exit(0)
PY
then
  pass "PR-07: sesión F2 no recuperó contenido biología de F1"
  RESULTS+=("PR-07: ÉXITO")
else
  warn "PR-07: posible fuga vectorial; revisar respuesta"
  RESULTS+=("PR-07: REVISAR")
fi
# Acceso cruzado alumno a curso no matriculado
CODE7=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOK_A1" \
  -H "X-Session-Id: $SESSION_F1" \
  "$BASE_URL/history")
[[ "$CODE7" == "403" ]] && info "PR-07 extra: alumno sin matrícula → 403 en history"
capture_logs "pr07"

# ── PR-08 Tolerancia fallos worker ────────────────────────────────────────────
info "PR-08: reinicio worker durante ingesta"
UPLOAD=$(upload_pdf "$TOK_F1" "$SESSION_F1" "$PDF_BIO")
TID8=$(python3 -c "import re,sys; m=re.search(r'\"task_id\":\"([^\"]+)\"', sys.stdin.read()); print(m.group(1) if m else '')" <<<"$UPLOAD")
sleep 2
docker compose --env-file /home/tino/projectos/cotutor-ia/.env restart worker >/dev/null
sleep 5
RES8=$(poll_task "$TOK_F1" "$TID8" 120)
ST8=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" <<<"$RES8")
if [[ "$ST8" == "SUCCESS" ]]; then
  pass "PR-08: tarea $TID8 completada tras reinicio worker"
  RESULTS+=("PR-08: ÉXITO")
else
  warn "PR-08: estado final=$ST8 (puede ser SUCCESS si ya estaba hecha)"
  RESULTS+=("PR-08: $ST8")
fi
capture_logs "pr08"

# ── PR-09 YouTube ─────────────────────────────────────────────────────────────
info "PR-09: transcripción YouTube (puede tardar varios minutos)"
YT_URL="https://www.youtube.com/watch?v=eIho2S0ZahI"  # TED-Ed corto
RESP9=$(curl -s -w "\n__HTTP__%{http_code}" \
  -X POST "$BASE_URL/process_video" \
  -H "Authorization: Bearer $TOK_F1" \
  -H "X-Session-Id: $SESSION_F1" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"$YT_URL\"}")
HTTP9=$(echo "$RESP9" | grep -oP '__HTTP__\K\d+' || echo 0)
TID9=$(python3 -c "import re,sys; m=re.search(r'\"task_id\":\"([^\"]+)\"', sys.stdin.read()); print(m.group(1) if m else '')" <<<"$RESP9")
if [[ "$HTTP9" == "200" && -n "$TID9" ]]; then
  RES9=$(poll_task "$TOK_F1" "$TID9" 180)
  ST9=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status',''), d.get('result',{}).get('success',''))" <<<"$RES9")
  if echo "$ST9" | grep -q "SUCCESS True"; then
    pass "PR-09: vídeo procesado e indexado"
    RESULTS+=("PR-09: ÉXITO")
  else
    warn "PR-09: tarea finalizó como $ST9"
    RESULTS+=("PR-09: $ST9")
  fi
else
  fail "PR-09: no se encoló (HTTP $HTTP9)"
  RESULTS+=("PR-09: FALLO")
fi
capture_logs "pr09"

# ── PR-10 JWT expirado ────────────────────────────────────────────────────────
info "PR-10: token JWT caducado"
EXPIRED=$(docker compose --env-file /home/tino/projectos/cotutor-ia/.env exec -T backend python3 -c "
import os, time
from jose import jwt
secret = os.environ['JWT_SECRET_KEY']
payload = {'sub': '$F1', 'iat': int(time.time())-3600, 'exp': int(time.time())-60, 'type': 'access'}
print(jwt.encode(payload, secret, algorithm='HS256'))
")
CODE10=$(curl -s -o "$LOG_DIR/pr10.json" -w "%{http_code}" \
  -H "Authorization: Bearer $EXPIRED" \
  -H "X-Session-Id: $SESSION_F1" \
  "$BASE_URL/auth/me")
if [[ "$CODE10" == "401" ]]; then
  pass "PR-10: HTTP 401 con token expirado"
  RESULTS+=("PR-10: ÉXITO")
else
  fail "PR-10: esperaba 401, obtuvo $CODE10"
  RESULTS+=("PR-10: FALLO ($CODE10)")
fi
capture_logs "pr10"

# ── PR-11 PDF corrupto ────────────────────────────────────────────────────────
info "PR-11: archivo .pdf inválido"
RESP11=$(upload_pdf "$TOK_F1" "$SESSION_F1" "$FAKE_PDF")
HTTP11=$(echo "$RESP11" | grep -oP '__HTTP__\K\d+' || echo 0)
TID11=$(python3 -c "import re,sys; m=re.search(r'\"task_id\":\"([^\"]+)\"', sys.stdin.read()); print(m.group(1) if m else '')" <<<"$RESP11")
FAIL11=0
if [[ "$HTTP11" == "400" ]]; then
  pass "PR-11: rechazo inmediato HTTP 400"
  RESULTS+=("PR-11: ÉXITO (400)")
elif [[ -n "$TID11" ]]; then
  RES11=$(poll_task "$TOK_F1" "$TID11" 60)
  ST11=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status'), d.get('error',''), d.get('result',{}))" <<<"$RES11")
  if echo "$ST11" | grep -qiE "FAILURE|success.*False|error"; then
    pass "PR-11: tarea falló controladamente: $ST11"
    RESULTS+=("PR-11: ÉXITO (task failure)")
  else
    fail "PR-11: tarea no falló como esperado: $ST11"
    RESULTS+=("PR-11: FALLO")
  fi
else
  fail "PR-11: HTTP $HTTP11 sin error claro"
  RESULTS+=("PR-11: FALLO")
fi
capture_logs "pr11"

# ── PR-12 Podcast Flash ───────────────────────────────────────────────────────
info "PR-12: Podcast Flash (resumen + TTS)"
chat "$TOK_F1" "$SESSION_F1" "Hazme un resumen breve del material sobre biología y fotosíntesis" \
  > "$LOG_DIR/pr12_chat.txt" || true
CODE12=$(curl -s -o "$LOG_DIR/pr12.mp3" -w "%{http_code}" \
  -X POST "$BASE_URL/discovery/podcast-audio" \
  -H "Authorization: Bearer $TOK_F1" \
  -H "X-Session-Id: $SESSION_F1" \
  -H "Content-Type: application/json" \
  -d '{}')
SIZE12=$(wc -c < "$LOG_DIR/pr12.mp3" 2>/dev/null || echo 0)
if [[ "$CODE12" == "200" && "$SIZE12" -gt 1000 ]]; then
  pass "PR-12: MP3 generado (${SIZE12} bytes)"
  RESULTS+=("PR-12: ÉXITO")
elif [[ "$CODE12" == "400" ]]; then
  warn "PR-12: sin resúmenes previos (HTTP 400) — chat quizá no guardó resumen"
  RESULTS+=("PR-12: PARCIAL (sin resúmenes)")
else
  fail "PR-12: HTTP $CODE12 size=$SIZE12"
  RESULTS+=("PR-12: FALLO")
fi
capture_logs "pr12"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo " RESUMEN"
echo "═══════════════════════════════════════════════════════════════"
for r in "${RESULTS[@]}"; do echo "  • $r"; done
echo ""
echo "Logs detallados: $LOG_DIR"
echo "  docker compose logs backend worker  # para trazas completas"
