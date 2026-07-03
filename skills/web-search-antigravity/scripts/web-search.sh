#!/bin/bash

set -euo pipefail

print_usage() {
    cat <<'USAGE'
Usage:
  web-search.sh -q "<query>" [options]
  web-search.sh "<query>" [options]
  echo "<query>" | web-search.sh [options]

Options:
  -q, --query <text>     Search query in natural language (repeatable)
  -l, --lang <code>      Response language (default: ja)
  -s, --site <domain>    Preferred domain (repeatable)
  -r, --recency <days>   Prefer recent info within N days
  -f, --format <format>  Requested response format in the prompt: text|json|markdown (default: text)
  -D, --depth <level>    Research depth: light|standard|deep (default: standard)
  -t, --timeout <secs>   Timeout in seconds per attempt (default: 600; deep=3600)
  -R, --retries <count>  Retry on timeout/capacity/network issues (default: 0)
  -j, --jobs <count>     Max parallel jobs (default: 0=auto, multi-query=2)
  -m, --model <name>     Antigravity model name (default: Claude Sonnet 4.6 (Thinking))
  -x, --rpm <count>      Rate limit: requests per minute (default: 0=unlimited)
      --progress         Enable progress logs ([info]) on stderr
  -v, --verbose          Enable extra debug logs ([log]) on stderr
  -P, --print-prompt     Print the exact prompt and exit (no request)
  -T, --timing           Print elapsed seconds to stderr
  -h, --help             Show this help

Example:
  web-search.sh -q "Next.js 15の新機能について教えて" -s nextjs.org -r 365
USAGE
}

QUERIES=()
QUERY=""
SAW_Q="0"
LANG="ja"
OUTPUT_FORMAT="text"
RECENCY_DAYS=""
SITES=()
PRINT_PROMPT="0"
TIMING="0"
DEPTH="standard"
TIMEOUT_SECS="600"
RETRIES="0"
MAX_JOBS="0"
JOBS_SET="0"
MODEL_NAME="Claude Sonnet 4.6 (Thinking)"
VERBOSE="0"
SHOW_PROGRESS="0"
TIMEOUT_SET="0"
RPM_LIMIT="0"
RPM_LOCK_FILE=""

is_uint() {
    [[ "$1" =~ ^[0-9]+$ ]]
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -q|--query)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --query requires a value." >&2
                exit 2
            fi
            QUERIES+=("$2")
            SAW_Q="1"
            shift 2
            ;;
        -l|--lang)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --lang requires a value." >&2
                exit 2
            fi
            LANG="$2"
            shift 2
            ;;
        -s|--site)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --site requires a value." >&2
                exit 2
            fi
            SITES+=("$2")
            shift 2
            ;;
        -r|--recency)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --recency requires a value." >&2
                exit 2
            fi
            if ! is_uint "$2"; then
                echo "Error: --recency must be a non-negative integer (days)." >&2
                exit 2
            fi
            RECENCY_DAYS="$2"
            shift 2
            ;;
        -f|--format)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --format requires a value." >&2
                exit 2
            fi
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        -D|--depth)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --depth requires a value." >&2
                exit 2
            fi
            if [[ "$2" != "light" && "$2" != "standard" && "$2" != "deep" ]]; then
                echo "Error: --depth must be one of: light, standard, deep." >&2
                exit 2
            fi
            DEPTH="$2"
            shift 2
            ;;
        -t|--timeout)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --timeout requires a value." >&2
                exit 2
            fi
            if ! is_uint "$2"; then
                echo "Error: --timeout must be a non-negative integer (seconds)." >&2
                exit 2
            fi
            TIMEOUT_SECS="$2"
            TIMEOUT_SET="1"
            shift 2
            ;;
        -R|--retries)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --retries requires a value." >&2
                exit 2
            fi
            if ! is_uint "$2"; then
                echo "Error: --retries must be a non-negative integer." >&2
                exit 2
            fi
            RETRIES="$2"
            shift 2
            ;;
        -j|--jobs)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --jobs requires a value." >&2
                exit 2
            fi
            if ! is_uint "$2"; then
                echo "Error: --jobs must be a non-negative integer." >&2
                exit 2
            fi
            MAX_JOBS="$2"
            JOBS_SET="1"
            shift 2
            ;;
        -m|--model)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --model requires a value." >&2
                exit 2
            fi
            MODEL_NAME="$2"
            shift 2
            ;;
        -x|--rpm)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --rpm requires a value." >&2
                exit 2
            fi
            if ! is_uint "$2"; then
                echo "Error: --rpm must be a non-negative integer." >&2
                exit 2
            fi
            RPM_LIMIT="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="1"
            shift
            ;;
        --progress)
            SHOW_PROGRESS="1"
            shift
            ;;
        -P|--print-prompt)
            PRINT_PROMPT="1"
            shift
            ;;
        -T|--timing)
            TIMING="1"
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        *)
            if [[ "$SAW_Q" = "0" && -z "$QUERY" ]]; then
                QUERY="$1"
                shift
            else
                echo "Error: unexpected argument: $1" >&2
                exit 2
            fi
            ;;
    esac
done

if [[ ${#QUERIES[@]} -eq 0 ]]; then
    if [[ -z "$QUERY" ]]; then
        if [ -t 0 ]; then
            print_usage
            exit 1
        fi
        QUERY="$(cat)"
    fi
    QUERIES=("$QUERY")
fi

if ! command -v agy >/dev/null 2>&1; then
    echo "Error: agy command not found. Install Antigravity CLI first." >&2
    exit 127
fi

# Set deep mode defaults
if [[ "$DEPTH" = "deep" ]]; then
    if [[ "$TIMEOUT_SET" = "0" ]]; then
        TIMEOUT_SECS="3600"
    fi
    if [[ "$MAX_JOBS" = "0" && "${#QUERIES[@]}" -gt 1 ]]; then
        # Deep multi-query runs benefit from limited parallelism more than full serialization.
        MAX_JOBS="2"
    fi
fi

# Auto mode: determine parallelism based on query count and depth
if [[ "$MAX_JOBS" = "0" ]]; then
    if [[ ${#QUERIES[@]} -le 1 ]]; then
        MAX_JOBS="1"
    else
        MAX_JOBS="2"
    fi
fi

log() {
    if [[ "$VERBOSE" = "1" ]]; then
        echo "[log] $*" >&2
    fi
}

ts() {
    date '+%H:%M:%S'
}

info() {
    if [[ "$SHOW_PROGRESS" = "1" || "$VERBOSE" = "1" ]]; then
        echo "[info $(ts)] $*" >&2
    fi
}

err() {
    echo "[error $(ts)] $*" >&2
}

query_preview() {
    local q="$1"
    q="${q//$'\n'/ }"
    if [[ ${#q} -gt 72 ]]; then
        printf '%s...' "${q:0:72}"
    else
        printf '%s' "$q"
    fi
}

# RPM tracking
append_rpm_timestamp() {
    local now_ts="$1"
    if command -v flock >/dev/null 2>&1; then
        (
            flock -x 200
            echo "$now_ts" >> "$TMP_DIR/rpm_timestamps"
        ) 200>"$RPM_LOCK_FILE"
    else
        # flock is not available by default on some macOS environments.
        echo "$now_ts" >> "$TMP_DIR/rpm_timestamps"
    fi
}

record_request_time() {
    local now_ts=$(date +%s)
    append_rpm_timestamp "$now_ts"
}

reserve_rpm_slot() {
    if [[ "$RPM_LIMIT" -le 0 ]]; then
        return 0
    fi

    local now_ts
    local window_start
    local count=0
    local lock_dir="${RPM_LOCK_FILE}.dir"

    now_ts=$(date +%s)
    window_start=$((now_ts - 60))

    if command -v flock >/dev/null 2>&1; then
        (
            flock -x 200
            count="$(prune_rpm_timestamps_and_count "$window_start")"
            if [[ -z "$count" ]]; then
                count=0
            fi
            log "rpm reserve: current=${count} limit=${RPM_LIMIT}"
            if [[ "$count" -ge "$RPM_LIMIT" ]]; then
                exit 1
            fi
            printf '%s\n' "$now_ts" >> "$TMP_DIR/rpm_timestamps"
        ) 200>"$RPM_LOCK_FILE"
        return $?
    fi

    (
        trap 'rmdir "$lock_dir" >/dev/null 2>&1 || true' EXIT
        while ! mkdir "$lock_dir" 2>/dev/null; do
            sleep 0.05
        done

        count="$(prune_rpm_timestamps_and_count "$window_start")"
        if [[ -z "$count" ]]; then
            count=0
        fi
        log "rpm reserve: current=${count} limit=${RPM_LIMIT}"
        if [[ "$count" -ge "$RPM_LIMIT" ]]; then
            exit 1
        fi
        printf '%s\n' "$now_ts" >> "$TMP_DIR/rpm_timestamps"
    )
    return $?
}

prune_rpm_timestamps_and_count() {
    local window_start="$1"
    local src="$TMP_DIR/rpm_timestamps"
    local tmp="$TMP_DIR/rpm_timestamps.pruned.$$"
    local ts=""
    local count=0

    : > "$tmp"
    if [[ -f "$src" ]]; then
        while IFS= read -r ts; do
            if [[ "$ts" =~ ^[0-9]+$ ]] && [[ "$ts" -ge "$window_start" ]]; then
                echo "$ts" >> "$tmp"
                count=$((count + 1))
            fi
        done < "$src"
    fi
    mv "$tmp" "$src"
    echo "$count"
}

can_make_request() {
    if [[ "$RPM_LIMIT" -le 0 ]]; then
        return 0
    fi
    local now_ts=$(date +%s)
    local window_start=$((now_ts - 60))
    local count=0

    if command -v flock >/dev/null 2>&1; then
        count="$(
            (
                flock -x 200
                prune_rpm_timestamps_and_count "$window_start"
            ) 200>"$RPM_LOCK_FILE"
        )"
    else
        count="$(prune_rpm_timestamps_and_count "$window_start")"
    fi
    if [[ -z "$count" ]]; then
        count=0
    fi
    log "rpm: current=${count} limit=${RPM_LIMIT}"
    [[ "$count" -lt "$RPM_LIMIT" ]]
}

set_throttle() {
    local until_ts="$1"
    local jobs="$2"
    if [[ -z "${TMP_DIR:-}" ]]; then
        return 0
    fi
    printf '%s %s\n' "$until_ts" "$jobs" > "$TMP_DIR/throttle"
}

get_throttle() {
    if [[ -z "${TMP_DIR:-}" || ! -f "$TMP_DIR/throttle" ]]; then
        echo ""
        return 0
    fi
    cat "$TMP_DIR/throttle"
}

count_running_queries() {
    local exclude_idx="${1:-}"
    local count=0
    local marker=""
    local marker_idx=""
    local marker_pid=""

    shopt -s nullglob
    for marker in "$TMP_DIR"/running_*.pid; do
        marker_idx="${marker##*/running_}"
        marker_idx="${marker_idx%.pid}"
        if [[ -n "$exclude_idx" && "$marker_idx" = "$exclude_idx" ]]; then
            continue
        fi
        marker_pid="$(cat "$marker" 2>/dev/null || true)"
        if [[ -n "$marker_pid" && "$marker_pid" =~ ^[0-9]+$ ]] && kill -0 "$marker_pid" >/dev/null 2>&1; then
            count=$((count + 1))
        else
            rm -f "$marker"
        fi
    done
    shopt -u nullglob

    echo "$count"
}

wait_for_quiet_retry_window() {
    local idx="$1"
    local reason="$2"
    local other_running=0

    if [[ ${#QUERIES[@]} -le 1 ]]; then
        return 0
    fi

    while :; do
        other_running="$(count_running_queries "$idx")"
        if [[ "$other_running" -le 0 ]]; then
            break
        fi
        log "query${idx} waiting_for_quiet_retry reason=${reason} other_running=${other_running}"
        sleep 1
    done
}

build_prompt() {
    local q="$1"
    local extra=()

    if [[ ${#SITES[@]} -gt 0 ]]; then
    extra+=("- 検索対象は以下のドメインを優先: ${SITES[*]}")
    fi
    if [[ -n "$RECENCY_DAYS" ]]; then
        extra+=("- 可能であれば直近${RECENCY_DAYS}日以内の情報を優先")
    fi

    local qlen=${#q}
    if [[ "$qlen" -lt 20 ]]; then
        extra+=("- 依頼内容が短い場合は、意図を推測して調査範囲・観点・前提を補い、検索クエリを展開すること。")
    fi

    local depth_hint=""
    case "$DEPTH" in
        light)
            depth_hint="短時間で要点を把握するため、少数の高信頼ソースに絞って検索すること（目安2〜3件）。"
            ;;
        deep)
            depth_hint="大規模な調査として扱い、必要に応じて複数回の検索と比較検証を行うこと。目安として6件以上の独立ソースを使い、公式一次情報を優先すること。"
            ;;
        *)
            depth_hint="必要に応じて検索を補完し、目安として4件以上の独立ソースに基づいて要約すること。"
            ;;
    esac
    extra+=("- ${depth_hint}")

    extra+=("- 調査内容の前に『調査理由』を1〜3文で記述すること。")
    extra+=("- 出力は『調査理由』『調査結果』『追加調査』『出典一覧』の見出しを使用すること。")
    extra+=("- 公式/一次情報を最優先し、二次情報は補助として扱い、出典ごとに種別（一次/二次/ブログ等）を明記すること。")
    extra+=("- 重要な主張や数値は必ず一次情報に紐づけ、一次情報が見つからない場合は断定を避けること。")
    extra+=("- 主張ごとに根拠となる出典を明示し、相互に矛盾がある場合は差異を説明すること。")
    extra+=("- 出典URLは全文URLを記載し、取得できない場合は『URL不明』と明記して主張には使わないこと。")
    extra+=("- 重要な段落・箇条書き・表には出典を明記すること。全ての文に機械的に出典を付ける必要はない。")
    extra+=("- 初回結果で重要な不明点や矛盾が残る場合のみ、追加検索を行い、『追加調査』に要点をまとめること。")
    extra+=("- 詳細さは保ちつつ、同じ事実や結論を繰り返さないこと。前に書いた内容を言い換えて重複しないこと。")
    extra+=("- 主要な観点を優先して整理し、不要なケーススタディや冗長な比較は省略してよい。")
    extra+=("- 断定できない情報は『未確認/推測』と明示し、推測を結論に混ぜないこと。")
    extra+=("- 事実と主張は必ずURLで裏付け、裏付けできない内容は「未確認」として別扱いにすること。")

    case "$OUTPUT_FORMAT" in
        json)
            extra+=("- 出力は有効なJSONのみとし、Markdownのコードフェンスや説明文を付けないこと。")
            ;;
        markdown|md|text)
            extra+=("- 出力形式の指定: ${OUTPUT_FORMAT}")
            ;;
        *)
            extra+=("- ユーザー指定の出力形式 '${OUTPUT_FORMAT}' に従うこと。")
            ;;
    esac

    local extra_text=""
    if [[ ${#extra[@]} -gt 0 ]]; then
        extra_text="$(printf '%s\n' "${extra[@]}")"
    fi

    cat <<EOF
## タスク
「依頼内容」を達成するために、ウェブ検索を行い、できるだけ詳細に回答してください。

## 依頼内容
${q}

## 追加条件
- 回答言語: ${LANG}
${extra_text}

## 結果のフォーマット
- 回答はMarkdown形式で記述すること
- 検索結果はファイルなどに書き出さず、レスポンスとして返すこと
- 回答には参考にしたURLを全て一覧として含めること
- 重要な主張には出典URLを併記すること
- 出典は「タイトル / 公開日(不明なら不明) / URL / 要点」で列挙すること
EOF
}

if [[ "$PRINT_PROMPT" = "1" ]]; then
    if [[ ${#QUERIES[@]} -gt 1 ]]; then
        for i in "${!QUERIES[@]}"; do
            echo "===== Prompt $((i + 1))/${#QUERIES[@]} ====="
            build_prompt "${QUERIES[$i]}"
            echo
        done
    else
        build_prompt "${QUERIES[0]}"
    fi
    exit 0
fi

RUN_START_TS="$(date +%s)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
RPM_LOCK_FILE="$TMP_DIR/rpm_lock"
info "start queries=${#QUERIES[@]} depth=${DEPTH} jobs=${MAX_JOBS} timeout=${TIMEOUT_SECS}s retries=${RETRIES} lang=${LANG} format=${OUTPUT_FORMAT}"

run_prompt() {
    local timeout_val="$1"
    local prompt_file="$2"
    local out_file="$3"
    local err_file="$4"
    local out_format="$5"
    local model_name="$6"

    python3 - "$timeout_val" "$prompt_file" "$out_file" "$err_file" "$out_format" "$model_name" <<'PY'
import re
import subprocess
import sys

timeout_raw = sys.argv[1]
prompt_path = sys.argv[2]
out_path = sys.argv[3]
err_path = sys.argv[4]
output_format = sys.argv[5]
model_name = sys.argv[6] if len(sys.argv) > 6 else ""

with open(prompt_path, 'r', encoding='utf-8') as f:
    prompt = f.read()

filters = [
    re.compile(r"^YOLO mode is enabled\\.", re.I),
    re.compile(r"^Loaded cached credentials\\.", re.I),
    re.compile(r"^Server '.+' supports (tool|resource|prompt) updates\\. Listening for changes\\."),
    re.compile(r"^MCP issues detected\\. Run /mcp list for status\\.", re.I),
    re.compile(r"^Usage of agy:", re.I),
]
substring_filters = (
    "YOLO mode is enabled.",
    "Loaded cached credentials.",
    "supports tool updates. Listening for changes.",
    "supports resource updates. Listening for changes.",
    "supports prompt updates. Listening for changes.",
    "MCP issues detected. Run /mcp list for status.",
)
ansi_re = re.compile(r"\x1b\[[0-9;]*m")

def filter_lines(text: str) -> str:
    if not text:
        return text
    lines = []
    for line in text.splitlines():
        check = ansi_re.sub("", line).lstrip()
        if any(p.match(check) for p in filters):
            continue
        if any(token in check for token in substring_filters):
            continue
        lines.append(line)
    return "\n".join(lines)

timeout_secs = float(timeout_raw) if timeout_raw else None
agy_timeout = f"{int(timeout_secs)}s" if timeout_secs is not None else "600s"
subprocess_timeout = (timeout_secs + 30.0) if timeout_secs is not None else None

cmd = ["agy", "-p", prompt, "--print-timeout", agy_timeout, "--dangerously-skip-permissions"]
if model_name:
    cmd.extend(["--model", model_name])
try:
    if subprocess_timeout:
        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=subprocess_timeout)
    else:
        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
except subprocess.TimeoutExpired:
    # Ensure output files exist on timeout to avoid downstream failures.
    open(out_path, 'w', encoding='utf-8').close()
    open(err_path, 'w', encoding='utf-8').close()
    sys.exit(124)

out = filter_lines(result.stdout)
err = filter_lines(result.stderr)

returncode = result.returncode
if returncode == 0 and not out.strip():
    err = (err + "\n" if err else "") + "Error: agy returned empty output."
    returncode = 65

if out:
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(out)
        if not out.endswith("\n"):
            f.write("\n")
else:
    open(out_path, 'w', encoding='utf-8').close()

if err:
    with open(err_path, 'w', encoding='utf-8') as f:
        f.write(err)
        if not err.endswith("\n"):
            f.write("\n")
else:
    open(err_path, 'w', encoding='utf-8').close()

sys.exit(returncode)
PY
}

run_query() {
    local idx="$1"
    local q="$2"
    local pid="${BASHPID:-$$}"
    local prompt_file="$TMP_DIR/prompt_${idx}.txt"
    local out_file="$TMP_DIR/out_${idx}.txt"
    local err_file="$TMP_DIR/err_${idx}.txt"
    local status_file="$TMP_DIR/status_${idx}.txt"
    local timing_file="$TMP_DIR/timing_${idx}.txt"
    local running_marker="$TMP_DIR/running_${idx}.pid"
    local query_start_ts
    query_start_ts="$(date +%s)"

    build_prompt "$q" > "$prompt_file"
    log "query${idx} pid=${pid} prompt_bytes=$(wc -c < "$prompt_file" | tr -d ' ')"
    info "query${idx} started pid=${pid} text='$(query_preview "$q")'"

    local attempt=0
    local status=0
    local start_ts
    local end_ts
    local max_attempts=$((RETRIES + 1))
    local retry_reason=""
    local backoff=0
    local jitter_ms=0
    local jitter_sec=""
    local sleep_time=""
    local now_ts=0
    local throttle_for=0
    local query_elapsed=0
    local delay_ms=0
    local delay_sec=""

    if [[ ${#QUERIES[@]} -gt 1 ]]; then
        if [[ "$DEPTH" = "deep" && "$MAX_JOBS" -gt 1 ]]; then
            delay_ms=$((1000 + (RANDOM % 3001)))
        else
            delay_ms=$((200 + (RANDOM % 1001)))
        fi
        delay_sec="$(awk "BEGIN { printf \"%.3f\", ${delay_ms}/1000 }")"
        log "query${idx} startup_jitter=${delay_sec}s"
        sleep "$delay_sec"
    fi

    if [[ "$TIMING" = "1" ]]; then
        start_ts=$(date +%s)
    fi

    while :; do
        attempt=$((attempt + 1))
        log "query${idx} attempt=${attempt}/${max_attempts} timeout=${TIMEOUT_SECS}s"
        if [[ "$RPM_LIMIT" -gt 0 ]]; then
            while ! reserve_rpm_slot; do
                log "query${idx} waiting for rpm slot before attempt=${attempt}"
                sleep 1
            done
        fi
        printf '%s\n' "$pid" > "$running_marker"
        if run_prompt "$TIMEOUT_SECS" "$prompt_file" "$out_file" "$err_file" "$OUTPUT_FORMAT" "$MODEL_NAME"; then
            status=0
        else
            status=$?
        fi
        rm -f "$running_marker"
        if [[ "$status" -eq 0 ]]; then
            log "query${idx} attempt=${attempt} status=0"
            break
        fi

        retry_reason=""
        if [[ "$status" -eq 124 ]]; then
            retry_reason="timeout"
        elif [[ "$status" -eq 65 ]]; then
            retry_reason="empty"
        elif [[ -s "$err_file" ]]; then
            if grep -qiE "exhausted your capacity|rate limit|quota|429|too many requests" "$err_file"; then
                retry_reason="capacity"
            elif grep -qiE "AbortError: The user aborted a request\\.|loop detected|loop detector|possible loop" "$err_file"; then
                retry_reason="abort"
            elif grep -qiE "network|connection|temporarily unavailable|ENOTFOUND|ECONN|EAI_AGAIN|timed out" "$err_file"; then
                retry_reason="network"
            fi
        fi

        if [[ -n "$retry_reason" ]]; then
            log "query${idx} attempt=${attempt} status=${status} reason=${retry_reason}"
        else
            log "query${idx} attempt=${attempt} status=${status} reason=unknown"
        fi

        if [[ -z "$retry_reason" ]]; then
            break
        fi
        if [[ "$attempt" -ge "$max_attempts" ]]; then
            if [[ "$retry_reason" = "timeout" ]]; then
                echo "Error: agy timed out after ${TIMEOUT_SECS}s (attempts: ${attempt})." >> "$err_file"
            elif [[ "$retry_reason" = "abort" ]]; then
                echo "Error: agy aborted internally after repeated/loop-like output (attempts: ${attempt})." >> "$err_file"
            elif [[ "$retry_reason" = "empty" ]]; then
                echo "Error: agy returned empty output after ${attempt} attempts." >> "$err_file"
            else
                echo "Error: agy failed due to ${retry_reason} (attempts: ${attempt})." >> "$err_file"
            fi
            break
        fi

        backoff=$((2 ** (attempt - 1)))
        if [[ "$backoff" -gt 60 ]]; then
            backoff=60
        fi
        jitter_ms=$((RANDOM % 1000))
        jitter_sec=$(printf '0.%03d' "$jitter_ms")
        sleep_time="${backoff}${jitter_sec}"
        if [[ "$retry_reason" = "capacity" || "$retry_reason" = "abort" ]]; then
            now_ts=$(date +%s)
            throttle_for=$((backoff + 2))
            if [[ "$retry_reason" = "abort" && "$throttle_for" -lt 10 ]]; then
                throttle_for=10
            fi
            if [[ "$throttle_for" -lt 5 ]]; then
                throttle_for=5
            fi
            set_throttle $((now_ts + throttle_for)) "1"
            log "query${idx} ${retry_reason}_throttle=${throttle_for}s jobs=1"
        fi
        log "query${idx} backoff=${backoff}s jitter=${jitter_sec}s sleep=${sleep_time}s"
        sleep "$sleep_time"
        if [[ "$retry_reason" = "capacity" || "$retry_reason" = "abort" ]]; then
            wait_for_quiet_retry_window "$idx" "$retry_reason"
        fi
    done

    rm -f "$running_marker"
    if [[ "$TIMING" = "1" ]]; then
        end_ts=$(date +%s)
        echo "${end_ts}-${start_ts}" > "$timing_file"
    fi

    query_elapsed=$(( $(date +%s) - query_start_ts ))
    echo "$status" > "$status_file"
    if [[ "$status" -eq 0 ]]; then
        info "query${idx} completed status=0 elapsed=${query_elapsed}s"
    else
        err "query${idx} completed status=${status} elapsed=${query_elapsed}s"
    fi

}

prune_pids() {
    local -a live=()
    local pid
    for pid in "${active_pids[@]:-}"; do
        if kill -0 "$pid" >/dev/null 2>&1; then
            live+=("$pid")
        fi
    done
    if [[ "${#live[@]}" -gt 0 ]]; then
        active_pids=("${live[@]}")
    else
        active_pids=()
    fi
    log "scheduler live_jobs=${#active_pids[@]}"
}

wait_for_slot() {
    local throttle_line=""
    local throttle_until=""
    local throttle_jobs=""
    local effective_jobs=0
    while :; do
        # Check throttle
        throttle_line="$(get_throttle)"
        if [[ -n "$throttle_line" ]]; then
            throttle_until="${throttle_line%% *}"
            throttle_jobs="${throttle_line##* }"
            now_ts=$(date +%s)
            if [[ -n "$throttle_until" && "$now_ts" -lt "$throttle_until" ]]; then
                effective_jobs="$throttle_jobs"
                if [[ "$MAX_JOBS" -gt 0 && "$MAX_JOBS" -lt "$effective_jobs" ]]; then
                    effective_jobs="$MAX_JOBS"
                fi
                if [[ "$effective_jobs" -lt 1 ]]; then
                    effective_jobs=1
                fi
                prune_pids
                if [[ "${#active_pids[@]}" -ge "$effective_jobs" ]]; then
                    log "scheduler throttling jobs=${#active_pids[@]}/${effective_jobs} until=${throttle_until}"
                    sleep 0.2
                    continue
                fi
            fi
        fi
        prune_pids
        if [[ "$MAX_JOBS" -le 0 || "${#active_pids[@]}" -lt "$MAX_JOBS" ]]; then
            break
        fi
        log "scheduler waiting jobs=${#active_pids[@]}/${MAX_JOBS}"
        sleep 0.2
    done
}

emit_query_output() {
    local idx="$1"
    local status_val=""

    if [[ ${#QUERIES[@]} -gt 1 ]]; then
        echo "===== Query $((idx + 1))/${#QUERIES[@]} ====="
        echo "Query: ${QUERIES[$idx]}"
    fi

    if [[ -f "$TMP_DIR/out_${idx}.txt" ]]; then
        cat "$TMP_DIR/out_${idx}.txt"
    else
        err "missing output file for query $((idx + 1))."
        had_failure=1
    fi

    if [[ -f "$TMP_DIR/status_${idx}.txt" ]]; then
        status_val="$(cat "$TMP_DIR/status_${idx}.txt")"
        if [[ "$status_val" != "0" ]]; then
            had_failure=1
        fi
    else
        status_val="missing"
        had_failure=1
        err "missing status file for query $((idx + 1))."
    fi

    if [[ -s "$TMP_DIR/err_${idx}.txt" ]]; then
        if [[ "$status_val" != "0" || "$VERBOSE" = "1" ]]; then
            if [[ ${#QUERIES[@]} -gt 1 ]]; then
                echo "[stderr query $((idx + 1))]" >&2
            fi
            cat "$TMP_DIR/err_${idx}.txt" >&2
        fi
    fi

    if [[ "$TIMING" = "1" && -f "$TMP_DIR/timing_${idx}.txt" ]]; then
        IFS='-' read -r end_ts start_ts < "$TMP_DIR/timing_${idx}.txt"
        if [[ -n "${end_ts:-}" && -n "${start_ts:-}" ]]; then
            if [[ ${#QUERIES[@]} -gt 1 ]]; then
                echo "[timing] query${idx}_elapsed_sec=$((end_ts - start_ts))" >&2
            else
                echo "[timing] elapsed_sec=$((end_ts - start_ts))" >&2
            fi
        fi
    fi

    if [[ ${#QUERIES[@]} -gt 1 ]]; then
        echo
    fi
}

emit_query_completion_notice() {
    local idx="$1"
    local completed_count="$2"
    local total_queries="${#QUERIES[@]}"
    local status_val="unknown"

    if [[ "$total_queries" -le 1 ]]; then
        return 0
    fi

    if [[ -f "$TMP_DIR/status_${idx}.txt" ]]; then
        status_val="$(cat "$TMP_DIR/status_${idx}.txt")"
    fi

    if [[ "$status_val" = "0" ]]; then
        echo "[notice $(ts)] query $((idx + 1))/${total_queries} completed (${completed_count}/${total_queries}); final results will be printed after all queries finish." >&2
    else
        echo "[error $(ts)] query $((idx + 1))/${total_queries} failed (${completed_count}/${total_queries}); final results will be printed after all queries finish." >&2
    fi
}

emit_ready_workers() {
    local j=""
    local pid=""
    local idx=""

    for j in "${!worker_pids[@]}"; do
        if [[ "${emitted[$j]}" = "1" ]]; then
            continue
        fi
        pid="${worker_pids[$j]}"
        idx="${worker_query_indices[$j]}"
        if ! kill -0 "$pid" >/dev/null 2>&1; then
            wait "$pid" || true
            emitted[$j]="1"
            remaining=$((remaining - 1))
            completed_queries=$((completed_queries + 1))
            emit_query_completion_notice "$idx" "$completed_queries"
        fi
    done
}

active_pids=()
worker_pids=()
worker_query_indices=()
emitted=()
remaining=0
completed_queries=0
had_failure=0
for i in "${!QUERIES[@]}"; do
    local_bg_pid=""
    wait_for_slot
    emit_ready_workers
    run_query "$i" "${QUERIES[$i]}" &
    local_bg_pid="$!"
    active_pids+=("$local_bg_pid")
    worker_pids+=("$local_bg_pid")
    worker_query_indices+=("$i")
    emitted+=("0")
    remaining=$((remaining + 1))
    log "scheduler dispatched query${i} bg_pid=${local_bg_pid}"
done

while [[ "$remaining" -gt 0 ]]; do
    emit_ready_workers
    if [[ "$remaining" -gt 0 ]]; then
        sleep 0.1
    fi
done

for i in "${!QUERIES[@]}"; do
    emit_query_output "$i"
done

total_elapsed=$(( $(date +%s) - RUN_START_TS ))
if [[ "$had_failure" -ne 0 ]]; then
    err "finish total_queries=${#QUERIES[@]} failed=${had_failure} elapsed=${total_elapsed}s"
else
    info "finish total_queries=${#QUERIES[@]} failed=${had_failure} elapsed=${total_elapsed}s"
fi

if [[ "$DEPTH" = "deep" && "${#QUERIES[@]}" -gt 1 && "$JOBS_SET" = "0" ]]; then
    log "deep multi-query defaulted to jobs=${MAX_JOBS} for stability"
fi

if [[ "$had_failure" -ne 0 ]]; then
    exit 1
fi
