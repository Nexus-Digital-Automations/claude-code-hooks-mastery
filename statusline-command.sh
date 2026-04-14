#!/bin/bash
# Claude Code statusline — multi-row comprehensive dashboard
# Rows: Identity | Context & Cost | 5h Rate | Weekly Rate + Time Budget | Flow

INPUT=$(cat)

# ---------------------------------------------------------------------------
# Helper: render_bar <pct> <width> <low_color> <mid_color> <hi_color>
# ---------------------------------------------------------------------------
render_bar() {
  local pct=$1 width=$2 c_low=$3 c_mid=$4 c_hi=$5
  local color
  if   [ "$pct" -lt 50 ]; then color="$c_low"
  elif [ "$pct" -lt 75 ]; then color="$c_mid"
  else                          color="$c_hi"
  fi
  local filled=$(( pct * width / 100 ))
  local empty=$(( width - filled ))
  printf "%b" "$color"
  local i=0
  while [ $i -lt $filled ]; do printf "█"; i=$(( i + 1 )); done
  printf "\033[90m"
  i=0
  while [ $i -lt $empty ]; do printf "░"; i=$(( i + 1 )); done
  printf "\033[0m"
}

# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------
MODEL=$(echo "$INPUT"        | jq -r '.model.display_name // "Claude"')
MODEL_ID=$(echo "$INPUT"     | jq -r '.model.id // ""')
CWD=$(echo "$INPUT"          | jq -r '.workspace.current_dir // .cwd // ""')
VIM_MODE=$(echo "$INPUT"     | jq -r '.vim.mode // empty')

CTX_USED=$(echo "$INPUT"     | jq -r '.context_window.used_percentage // empty')
INPUT_TOKENS=$(echo "$INPUT" | jq -r '.context_window.current_usage.input_tokens // empty')
OUTPUT_TOKENS=$(echo "$INPUT"| jq -r '.context_window.current_usage.output_tokens // empty')
CACHE_READ=$(echo "$INPUT"   | jq -r '.context_window.current_usage.cache_read_input_tokens // 0')
CACHE_WRITE=$(echo "$INPUT"  | jq -r '.context_window.current_usage.cache_creation_input_tokens // 0')
TOTAL_IN=$(echo "$INPUT"     | jq -r '.context_window.total_input_tokens // empty')
TOTAL_OUT=$(echo "$INPUT"    | jq -r '.context_window.total_output_tokens // empty')

RATE_5H=$(echo "$INPUT"      | jq -r '.rate_limits.five_hour.used_percentage // empty')
RATE_7D=$(echo "$INPUT"      | jq -r '.rate_limits.seven_day.used_percentage // empty')

# ---------------------------------------------------------------------------
# Derived values
# ---------------------------------------------------------------------------

# Model short name
MODEL_SHORT=$(echo "$MODEL" | sed 's/^Claude[[:space:]]*//')

# Abbreviated path — last 3 segments max
DISPLAY_PATH="~"
if [ -n "$CWD" ]; then
  DISPLAY_PATH="${CWD/#$HOME/\~}"
  SEG_COUNT=$(echo "$DISPLAY_PATH" | tr '/' '\n' | grep -c .)
  if [ "$SEG_COUNT" -gt 3 ]; then
    DISPLAY_PATH=$(echo "$DISPLAY_PATH" | awk -F'/' '{n=NF; print "…/" $(n-1) "/" $n}')
  fi
fi

# Git branch + dirty marker
BRANCH=""
GIT_DIRTY=""
if [ -n "$CWD" ]; then
  BRANCH=$(cd "$CWD" 2>/dev/null && GIT_OPTIONAL_LOCKS=0 git branch --show-current 2>/dev/null)
  if [ -n "$BRANCH" ]; then
    DIRTY_COUNT=$(cd "$CWD" 2>/dev/null && GIT_OPTIONAL_LOCKS=0 git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    [ "$DIRTY_COUNT" -gt 0 ] && GIT_DIRTY=" *${DIRTY_COUNT}"
  fi
fi

# Model-aware cost estimate
# Opus: $15/$75/M in/out, $18.75/$1.50 cache write/read
# Sonnet: $3/$15/M, $3.75/$0.30
# Haiku: $0.80/$4/M, $1.00/$0.08
COST=""
if [ -n "$INPUT_TOKENS" ] && [ -n "$OUTPUT_TOKENS" ]; then
  COST=$(printf "%s %s %s %s %s" "$INPUT_TOKENS" "$OUTPUT_TOKENS" "$CACHE_READ" "$CACHE_WRITE" "$MODEL_ID" | awk '{
    inp=$1; out=$2; cr=$3; cw=$4; model=$5;
    p_in=3.00; p_out=15.00; p_cr=0.30; p_cw=3.75;
    if (model ~ /opus/) { p_in=15.00; p_out=75.00; p_cr=1.50; p_cw=18.75; }
    else if (model ~ /haiku/) { p_in=0.80; p_out=4.00; p_cr=0.08; p_cw=1.00; }
    cost = (inp/1e6*p_in) + (out/1e6*p_out) + (cr/1e6*p_cr) + (cw/1e6*p_cw);
    if (cost < 0.01) printf "$%.4f", cost;
    else if (cost < 1) printf "$%.3f", cost;
    else if (cost < 10) printf "$%.2f", cost;
    else printf "$%.1f", cost;
  }')
fi

# Token totals
TOK_LABEL=""
if [ -n "$TOTAL_IN" ] && [ -n "$TOTAL_OUT" ]; then
  TOK_LABEL=$(printf "%s %s" "$TOTAL_IN" "$TOTAL_OUT" | awk '{
    t=$1+$2;
    if (t >= 1000000) printf "%.1fM", t/1000000;
    else if (t >= 1000) printf "%.0fk", t/1000;
    else printf "%d", t;
  }')
fi

# Calendar time: day name, current time, week position
DAY_NAME=$(date +%a)
TIME_NOW=$(date +%H:%M)
DOW=$(date +%u)    # 1=Mon, 7=Sun
HOUR=$(date +%H)

# Time remaining in the calendar week (until Sunday 23:59)
WEEK_REMAIN=$(echo "$DOW $HOUR" | awk '{
  dow=$1; h=$2;
  hours_left = (7 - dow) * 24 + (24 - h);
  d = int(hours_left / 24);
  hr = hours_left - d * 24;
  if (d > 0) printf "%dd %dh", d, hr;
  else printf "%dh", hr;
}')

# Week elapsed fraction (for burn rate): Mon 00:00 = 0.0, Sun 23:59 = ~1.0
WEEK_ELAPSED_DAYS=$(echo "$DOW $HOUR" | awk '{printf "%.2f", ($1-1) + $2/24.0}')

# Burn rate projection: at current 7d usage pace, how many days until limit?
PACE_LABEL=""
if [ -n "$RATE_7D" ]; then
  R7_VAL=$(printf "%.0f" "$RATE_7D")
  PACE_LABEL=$(echo "$R7_VAL $WEEK_ELAPSED_DAYS" | awk '{
    used=$1; elapsed=$2;
    if (elapsed > 0.2 && used > 1) {
      rate = used / elapsed;
      remaining = 100 - used;
      days = remaining / rate;
      if (days > 99) printf "sustainable";
      else if (days >= 1) printf "~%.1fd at pace", days;
      else printf "~%.0fh at pace", days * 24;
    } else if (used <= 1) {
      printf "minimal usage";
    }
  }')
fi

# Week % elapsed (for the "week progress" indicator)
WEEK_PCT=$(echo "$DOW $HOUR" | awk '{
  elapsed = (($1-1) * 24 + $2);
  total = 7 * 24;
  printf "%.0f", (elapsed / total) * 100;
}')

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RST="\033[0m"
BOLD="\033[1m"
DIM="\033[90m"
SEP="\033[90m │ \033[0m"

C_TEAL="\033[36m"
C_BLUE="\033[34m"
C_GOLD="\033[33m"
C_VIOLET="\033[35m"
C_CYAN="\033[96m"
C_GREEN="\033[32m"
C_ORANGE="\033[38;5;208m"
C_LIME="\033[38;5;118m"

WARN="\033[33m"
DANGER="\033[31m"

# Helper: color for "available %" — green when high, yellow mid, red low
avail_color() {
  local avail=$1
  if   [ "$avail" -gt 50 ]; then printf "${C_GREEN}"
  elif [ "$avail" -gt 25 ]; then printf "${WARN}"
  else                            printf "${DANGER}"
  fi
}

# ---------------------------------------------------------------------------
# ROW 1: Model + Location + Day/Time
# ---------------------------------------------------------------------------
printf "${BOLD}${C_TEAL}%s${RST}" "$MODEL_SHORT"

if [ -n "$VIM_MODE" ]; then
  case "$VIM_MODE" in
    NORMAL) printf " ${DIM}[N]${RST}" ;;
    INSERT) printf " \033[32m[I]${RST}" ;;
    *)      printf " ${DIM}[%s]${RST}" "$VIM_MODE" ;;
  esac
fi

printf "${SEP}${C_BLUE}%s${RST}" "$DISPLAY_PATH"

if [ -n "$BRANCH" ]; then
  printf " ${DIM}on${RST} ${C_GOLD}%s${RST}" "$BRANCH"
  [ -n "$GIT_DIRTY" ] && printf "${WARN}%s${RST}" "$GIT_DIRTY"
fi

printf "${SEP}${DIM}%s %s${RST}" "$DAY_NAME" "$TIME_NOW"

printf "\n"

# ---------------------------------------------------------------------------
# ROW 2: Context Window + Tokens + Cost
# ---------------------------------------------------------------------------
if [ -n "$CTX_USED" ]; then
  CTX_INT=$(printf "%.0f" "$CTX_USED")
  printf "${DIM}Context ${RST} "
  render_bar "$CTX_INT" 14 "${C_VIOLET}" "${WARN}" "${DANGER}"

  if   [ "$CTX_INT" -lt 50 ]; then PCT_C="${C_VIOLET}"
  elif [ "$CTX_INT" -lt 75 ]; then PCT_C="${WARN}"
  else                              PCT_C="${DANGER}"
  fi
  printf " ${PCT_C}%d%%${RST}" "$CTX_INT"
fi

if [ -n "$TOK_LABEL" ]; then
  printf "${SEP}${C_CYAN}%s tok${RST}" "$TOK_LABEL"
fi

if [ -n "$COST" ]; then
  printf "${SEP}${C_GREEN}%s${RST}" "$COST"
fi

printf "\n"

# ---------------------------------------------------------------------------
# ROW 3: 5-Hour Rate Limit
# ---------------------------------------------------------------------------
if [ -n "$RATE_5H" ]; then
  R5=$(printf "%.0f" "$RATE_5H")
  R5_FREE=$((100 - R5))

  printf "${DIM}5h Rate ${RST} "
  render_bar "$R5" 14 "${C_ORANGE}" "${WARN}" "${DANGER}"

  if   [ "$R5" -lt 50 ]; then RC="${C_ORANGE}"
  elif [ "$R5" -lt 75 ]; then RC="${WARN}"
  else                        RC="${DANGER}"
  fi
  printf " ${RC}%d%% used${RST}" "$R5"

  printf "${SEP}"
  printf "%b%d%% available${RST}" "$(avail_color $R5_FREE)" "$R5_FREE"

  printf "\n"
fi

# ---------------------------------------------------------------------------
# ROW 4: 7-Day Rate Limit + Weekly Time Budget
# ---------------------------------------------------------------------------
if [ -n "$RATE_7D" ]; then
  R7=$(printf "%.0f" "$RATE_7D")
  R7_FREE=$((100 - R7))

  printf "${DIM}Weekly  ${RST} "
  render_bar "$R7" 14 "${C_ORANGE}" "${WARN}" "${DANGER}"

  if   [ "$R7" -lt 50 ]; then RC="${C_ORANGE}"
  elif [ "$R7" -lt 75 ]; then RC="${WARN}"
  else                        RC="${DANGER}"
  fi
  printf " ${RC}%d%% used${RST}" "$R7"

  printf "${SEP}"
  printf "%b%d%% available${RST}" "$(avail_color $R7_FREE)" "$R7_FREE"

  printf "${SEP}${DIM}%s left${RST}" "$WEEK_REMAIN"

  if [ -n "$PACE_LABEL" ]; then
    printf "${SEP}${DIM}%s${RST}" "$PACE_LABEL"
  fi

  printf "\n"
fi

# ---------------------------------------------------------------------------
# ROW 5: Claude-Flow (only when .claude-flow dir is present)
# ---------------------------------------------------------------------------
FLOW_DIR="$CWD/.claude-flow"
if [ -d "$FLOW_DIR" ]; then
  printf "${DIM}Flow    ${RST} \033[35mactive${RST}"

  if [ -f "$FLOW_DIR/swarm-config.json" ]; then
    STRATEGY=$(jq -r '.defaultStrategy // empty' "$FLOW_DIR/swarm-config.json" 2>/dev/null)
    AGENT_COUNT=$(jq -r '.agentProfiles | length // 0' "$FLOW_DIR/swarm-config.json" 2>/dev/null)
    [ -n "$STRATEGY" ] && printf " ${DIM}%s${RST}" "$STRATEGY"
    if [ -n "$AGENT_COUNT" ] && [ "$AGENT_COUNT" != "null" ] && [ "$AGENT_COUNT" -gt 0 ]; then
      printf " ${DIM}\xC2\xB7${RST} \033[35m%s agents${RST}" "$AGENT_COUNT"
    fi
  fi

  if [ -f "$FLOW_DIR/metrics/system-metrics.json" ]; then
    LATEST=$(jq -r '.[-1]' "$FLOW_DIR/metrics/system-metrics.json" 2>/dev/null)
    if [ -n "$LATEST" ] && [ "$LATEST" != "null" ]; then
      MEM=$(echo "$LATEST" | jq -r '.memoryUsagePercent // empty' | awk '{printf "%.0f", $1}')
      CPU=$(echo "$LATEST" | jq -r '.cpuLoad // empty' | awk '{printf "%.0f", $1 * 100}')
      if [ -n "$MEM" ] && [ "$MEM" != "" ]; then
        printf "  ${DIM}mem${RST} "
        render_bar "$MEM" 6 "\033[35m" "${WARN}" "${DANGER}"
        printf " ${DIM}%d%%${RST}" "$MEM"
      fi
      if [ -n "$CPU" ] && [ "$CPU" != "" ]; then
        printf "  ${DIM}cpu${RST} "
        render_bar "$CPU" 6 "\033[35m" "${WARN}" "${DANGER}"
        printf " ${DIM}%d%%${RST}" "$CPU"
      fi
    fi
  fi

  if [ -f "$FLOW_DIR/metrics/task-metrics.json" ]; then
    METRICS=$(jq -r '
      (map(select(.success == true)) | length) as $ok |
      (length) as $n |
      if $n > 0 then ($ok | tostring) + "/" + ($n | tostring)
      else empty end
    ' "$FLOW_DIR/metrics/task-metrics.json" 2>/dev/null)
    if [ -n "$METRICS" ] && [ "$METRICS" != "null" ]; then
      printf "  ${DIM}tasks %s${RST}" "$METRICS"
    fi
  fi

  printf "\n"
fi
