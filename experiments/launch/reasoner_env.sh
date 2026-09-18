# Source before `openral deploy sim` to give the reasoner its LLM gateway (F38/F49).
# Without these the reasoner node stays UNCONFIGURED and deploy_e2e's lifecycle_autostart
# for /openral_reasoner fails after 300 s -- the "error" seen in every Nav2 smoke log.
#
#   source experiments/launch/reasoner_env.sh
#
# The key is NOT duplicated here: it is read from AGENT/VLM_provider.md (the user-supplied
# gateway doc), or taken from OPENRAL_REASONER_API_KEY if already exported.
_here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
_provider="$_here/../../AGENT/VLM_provider.md"

export OPENRAL_REASONER_ENDPOINT="${OPENRAL_REASONER_ENDPOINT:-https://api.deepseek.com}"
export OPENRAL_REASONER_DIALECT="${OPENRAL_REASONER_DIALECT:-openai}"
export OPENRAL_REASONER_MODEL="${OPENRAL_REASONER_MODEL:-deepseek-flash}"
# the gateway's thinking models reject tool_choice=required (F38)
export OPENRAL_REASONER_TOOL_CHOICE="${OPENRAL_REASONER_TOOL_CHOICE:-auto}"
# thinking models spend budget on reasoning_content before answering (F38)
export OPENRAL_REASONER_MAX_TOKENS="${OPENRAL_REASONER_MAX_TOKENS:-16384}"
if [ -z "${OPENRAL_REASONER_API_KEY:-}" ] && [ -f "$_provider" ]; then
    export OPENRAL_REASONER_API_KEY=$(grep -oE 'sk-[A-Za-z0-9_-]+' "$_provider" | tail -1)
fi
# httpx picks up this host's SOCKS proxy and dies without `socksio` (F38)
unset all_proxy ALL_PROXY
unset _here _provider
