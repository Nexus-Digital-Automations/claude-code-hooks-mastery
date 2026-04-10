---
name: "Playwright MCP Frontend Testing"
description: "Run frontend validation using the Playwright MCP server. Use when any change could affect what the user sees in the browser — API changes, auth, routing, config, data models, or direct UI work."
---

---
## ⚠️ Qwen Mode — Awareness Note

Read `~/.claude/data/agent_mode.json`.

**If `mode == "qwen"`:**
This skill handles non-code work (analysis / coordination / git ops / docs / validation) — safe to run directly.
However: if this skill leads to a code implementation step (writing/modifying files), that step
MUST use `mcp__qwen-agent__run` rather than direct code writing. You supervise; Qwen executes.

**If `mode == "claude"`:** No change — proceed normally with this skill.

---


# Playwright MCP Frontend Testing

Use `mcp__playwright__browser_*` tools to validate the app in a real browser.
Invoke this skill whenever a change **could surface in the browser** — not just direct UI work.

## When to Use

- UI/component changes (obviously)
- API response shape changes (the frontend consumes it)
- Auth or session logic changes
- Routing or redirect changes
- Environment/config changes that affect frontend behavior
- Data model changes visible in the UI
- Any backend change where you're not 100% sure it doesn't affect the UI

**Rule of thumb:** if in doubt, test it. Browser validation takes ~2 minutes and is proof.

---

## Complete Flow Rule (MANDATORY)

Every tested feature MUST be verified end-to-end — not just "the button fired an API call":

- **Create/Add**: After submitting, navigate to the result page (list, detail, dashboard) and assert the new item is visible there.
- **Edit**: Before editing, CREATE dummy test data first. Edit that data, then verify the changed value appears on the page. Never edit existing production-like data.
- **Delete**: Before deleting, CREATE dummy test data first. Delete it, then verify it is gone from the list/page. Never delete real data.
- **Multi-step workflows**: Complete each step in sequence. Don't stop at "modal opened" or "API returned 200" — continue until the final state is visible in the UI.

**Dummy data pattern:**
1. Use the UI (or a setup API call) to create a test item with a clearly fake name (e.g. `PLAYWRIGHT_TEST_item_DO_NOT_USE`)
2. Perform the edit/delete on that item
3. Verify the result in the UI
4. Clean up (delete the dummy item if it wasn't already deleted by the test)

---

## Step-by-Step Protocol

### 1. Install browser if needed
```
mcp__playwright__browser_install({ browser: "chromium" })
```
Only needed once — skip if already installed.

### 2. Navigate to the app
```
mcp__playwright__browser_navigate({ url: "http://localhost:<port>" })
```
Start the dev server first if it's not running (`npm run dev`, `python -m uvicorn ...`, etc).

### 3. Take initial screenshot
```
mcp__playwright__browser_take_screenshot({})
```
Verify the page loaded correctly. Include this in your validation report.

### 4. Check for console errors
```
mcp__playwright__browser_console_messages({})
```
**Zero errors required.** Warnings are acceptable; errors are not.

### 5. Exercise the changed feature
Walk through the user journey for whatever was changed:

```
# Click elements
mcp__playwright__browser_click({ selector: "button#submit" })

# Fill forms
mcp__playwright__browser_fill_form({ fields: { "#email": "test@example.com", "#password": "secret" } })

# Type in inputs
mcp__playwright__browser_type({ selector: "#search", text: "hello" })

# Navigate between pages
mcp__playwright__browser_navigate({ url: "http://localhost:<port>/dashboard" })

# Select dropdowns
mcp__playwright__browser_select_option({ selector: "select#role", value: "admin" })

# Wait for async content
mcp__playwright__browser_wait_for({ selector: ".loaded", timeout: 5000 })
```

### 6. Screenshot after each significant action
```
mcp__playwright__browser_take_screenshot({})
```
Take before/after screenshots for changed flows. These are your visual proof.

### 7. Check network requests for errors
```
mcp__playwright__browser_network_requests({})
```
Look for 4xx/5xx responses. Any API errors = investigate before stopping.

### 8. Re-check console after interactions
```
mcp__playwright__browser_console_messages({})
```
Errors triggered by user interaction are just as bad as load-time errors.

### 9. Close browser when done
```
mcp__playwright__browser_close({})
```

---

## Validation Report Format

Include in your stop validation report:

```
### Frontend Validation (Playwright MCP)
- App started: ✅ http://localhost:3000
- Initial load: ✅ [screenshot attached / no console errors]
- Feature tested: [describe what you clicked/submitted/navigated]
- Console errors: ✅ None (or list them)
- Network errors: ✅ None (or list them)
- Screenshots: [describe before/after]
```

---

## Useful Selectors Reference

| Goal | Selector pattern |
|------|-----------------|
| Button by text | `button:has-text("Submit")` |
| Input by label | `[aria-label="Email"]` or `#email` |
| Nav link | `nav a[href="/dashboard"]` |
| Form submission | `form button[type="submit"]` |
| Loading state gone | `.spinner` (wait for it to disappear) |
| Error message | `.error, [role="alert"]` |

---

## Common Troubleshooting

**Page blank / 404** — dev server not running, wrong port
**Console errors on load** — likely a JS bundle error or missing env var
**Network 401** — auth token not set, try logging in first
**Selector not found** — use `browser_snapshot()` to see current DOM state
**Timeout** — page slow or element never appeared, check network tab
