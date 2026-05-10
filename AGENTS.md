# content-stack agent notes

## TPF Token Proxy Filter

Prefix shell commands with `TPF_LLM_TOOL=codex tpf` unless the command is one of:
`cd`, `echo`, `cat`, `head`, `tail`, `mkdir`, `rm`, `mv`, `cp`, `chmod`,
`pwd`, `export`, `source`, `set`, `unset`, `alias`, `read`, `printf`,
`test`, `true`, `false`, `which`, `touch`.

For piped commands, put the pipe in `TPF_PIPE`:

```bash
TPF_PIPE='head -20' TPF_LLM_TOOL=codex tpf git log --oneline
```

Do not wrap redirections, logical OR, background jobs, or subshells.

## Serena MCP

Use this project's dedicated Serena MCP server, not the shared/global `serena`
server:

- Codex MCP name: `serena-content-stack`
- URL: `http://localhost:9123/mcp`
- launchd label: `com.oraios.serena-mcp.content-stack`
- launchd plist: `~/Library/LaunchAgents/com.oraios.serena-mcp-content-stack.plist`
- project: `/Users/sergeyrura/Bin/content-stack`
- log: `~/Library/Logs/serena-mcp-content-stack.log`

Do not call `activate_project` on the shared `serena` MCP to switch it to
content-stack. That server is used by other projects and can expose stale
project memory. Do not write, rename, edit, or delete Serena memories unless
the user explicitly asks.
