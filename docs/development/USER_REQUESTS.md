# User Requests Log

Automatically tracked by Claude Code UserPromptSubmit hook.

## Categories
- **bug**: Bug reports and fixes
- **feature**: Feature requests
- **question**: Questions and clarifications
- **request**: General requests

---


### [FEATURE] 2025-11-29 19:58
**Session:** `87a65b56...`
**Request:** what other prompt injections and/or improvements we should make to the hooks system?
**Status:** [ ] Pending

### [FEATURE] 2025-11-29 20:15
**Session:** `87a65b56...`
**Request:** don't implement this. just have the prompt for pretool use tell it not to write secrets outside of .env and files ignored in .gitignore
**Status:** [ ] Pending

### [QUESTION] 2025-11-29 20:18
**Session:** `87a65b56...`
**Request:** why don't we have pretooluse or posttool use tools run linting checks on the files written/edited?
**Status:** [ ] Pending

### [BUG] 2025-11-29 20:19
**Session:** `5950c8d2...`
**Request:** ⏺ Updated plan
  ⎿  PreToolUse:Edit hook error


figure out why this is happening and fix it
**Status:** [ ] Pending

### [REQUEST] 2025-11-29 20:19
**Session:** `87a65b56...`
**Request:** c++ and c# should be supported too
**Status:** [ ] Pending

### [FEATURE] 2025-11-30 10:54
**Session:** `87a65b56...`
**Request:** okay now please add to the userprompt submit. I want the agent to make sure it knows and elaborates on any ambiguity in the user's requests so it can get it exactly right. It should ask questions to resolve anything important and provide a recommended for each in the answer it recommends.


it should also have a particular structure for the tasks in the file it stores it in. for example, each task could have "-----" before and after it
**Status:** [ ] Pending

### [FEATURE] 2025-11-30 10:56
**Session:** `87a65b56...`
**Request:** don't specify the format for the questioning. It will know how to do that. just have it add "[Recommended]" to one of the answers
**Status:** [ ] Pending

-----
### [BUG] 2025-11-30 10:59
**Session:** `87a65b56...`
**Request:** please describe the hook errors you were getting
**Status:** [ ] Pending
-----

-----
### [BUG] 2025-11-30 11:07
**Session:** `87a65b56...`
**Request:** Based on my investigation, here's what's happening with the UserPromptSubmit hook error:

  Summary

  The hook is configured at /Users/jeremyparker/.claude/settings.json (line 353-362):
  "UserPromptSubmit": [{
    "hooks": [{
      "type": "command",
      "command": "bash ~/.claude/hooks/run_hook.sh ~/.claude/hooks/user_prompt_submit.py --log-only --store-last-prompt --name-agent"
    }]
  }]

  What the hook does:

  1. Logs prompts - to logs/user_prompt_submit.json (this is working - I can ...
**Status:** [ ] Pending
-----

-----
### [BUG] 2025-11-30 13:25
**Session:** `13c65364...`
**Request:** Fix UserPromptSubmit hook errors - Ollama not working for agent naming
**Status:** [x] Complete - Pulled llama3.2:3b model, updated ollama.py default model
-----

-----
### [BUG] 2025-11-30 14:07
**Session:** `13c65364...`
**Request:** check that it doesn't give an error anymore
**Status:** [ ] Pending
-----
