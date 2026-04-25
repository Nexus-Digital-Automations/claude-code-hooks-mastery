#!/usr/bin/env bash
# claude-dashboard statusLine command
# Reads JSON from stdin and renders a rich dashboard status line

input=$(cat)

# --- Extract fields ---
model=$(echo "$input" | jq -r '.model.display_name // "Claude"')
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
dir=$(basename "$cwd")
session_name=$(echo "$input" | jq -r '.session_name // empty')
version=$(echo "$input" | jq -r '.version // ""')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
vim_mode=$(echo "$input" | jq -r '.vim.mode // empty')
output_style=$(echo "$input" | jq -r '.output_style.name // empty')
five_hr=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
seven_day=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
worktree_branch=$(echo "$input" | jq -r '.worktree.branch // empty')
agent_name=$(echo "$input" | jq -r '.agent.name // empty')

# --- ANSI colors ---
RESET='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
BLUE='\033[34m'
MAGENTA='\033[35m'
WHITE='\033[37m'

# --- Git branch (optional, skip lock) ---
git_branch=""
if [ -d "$cwd/.git" ] || git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
  git_branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
fi

# --- Build output segments ---
parts=""

# Directory
if [ -n "$dir" ]; then
  parts="${parts}$(printf "${BOLD}${CYAN}%s${RESET}" "$dir")"
fi

# Git branch or worktree branch
branch="${worktree_branch:-$git_branch}"
if [ -n "$branch" ]; then
  parts="${parts}$(printf " ${DIM}${WHITE}on${RESET} ${MAGENTA}%s${RESET}" "$branch")"
fi

# Session name
if [ -n "$session_name" ]; then
  parts="${parts}$(printf " ${DIM}[${RESET}${WHITE}%s${RESET}${DIM}]${RESET}" "$session_name")"
fi

# Model
if [ -n "$model" ]; then
  parts="${parts}$(printf " ${DIM}•${RESET} ${BLUE}%s${RESET}" "$model")"
fi

# Output style
if [ -n "$output_style" ] && [ "$output_style" != "default" ]; then
  parts="${parts}$(printf " ${DIM}(${RESET}${WHITE}%s${RESET}${DIM})${RESET}" "$output_style")"
fi

# Context usage
if [ -n "$used_pct" ]; then
  used_int=$(printf "%.0f" "$used_pct")
  if [ "$used_int" -ge 80 ]; then
    ctx_color="$RED"
  elif [ "$used_int" -ge 50 ]; then
    ctx_color="$YELLOW"
  else
    ctx_color="$GREEN"
  fi
  parts="${parts}$(printf " ${DIM}•${RESET} ctx:${ctx_color}%s%%${RESET}" "$used_int")"
fi

# Rate limits
limits=""
if [ -n "$five_hr" ]; then
  pct_int=$(printf "%.0f" "$five_hr")
  limits="${limits}5h:${pct_int}%"
fi
if [ -n "$seven_day" ]; then
  pct_int=$(printf "%.0f" "$seven_day")
  [ -n "$limits" ] && limits="${limits} "
  limits="${limits}7d:${pct_int}%"
fi
if [ -n "$limits" ]; then
  parts="${parts}$(printf " ${DIM}•${RESET} ${YELLOW}%s${RESET}" "$limits")"
fi

# Vim mode
if [ -n "$vim_mode" ]; then
  if [ "$vim_mode" = "NORMAL" ]; then
    vim_color="$GREEN"
  else
    vim_color="$YELLOW"
  fi
  parts="${parts}$(printf " ${DIM}•${RESET} ${vim_color}%s${RESET}" "$vim_mode")"
fi

# Agent
if [ -n "$agent_name" ]; then
  parts="${parts}$(printf " ${DIM}•${RESET} ${MAGENTA}agent:%s${RESET}" "$agent_name")"
fi

printf "%b" "$parts"
