# From Chat to MCP — Podcast Talk Track

**Format:** ~15–20 min spoken segment + live demo against a 4× Arista EOS lab
**Audience:** network engineers who already use ChatGPT-style chat, but haven't touched MCP
**One-sentence thesis:** *Chat can tell you the command; MCP lets the model run it for you — safely, against your own gear.*

> This is a **speaking script**, not slides. Each segment has a target time, the point to land,
> and talk-track you can read or paraphrase. The demo section is a runbook with exact prompts and
> the real output you'll see. Total ≈ 18 min (≈11 talking, ≈7 demo). Trim Segment 4 if you run long.

---

## Pre-flight checklist (do this before you record)

- [ ] **Update the repo** — your local checkout was 11 commits behind `origin/main`. `git pull`, then re-install (`uv pip install -e .`) and **restart the MCP server** so the lab tools run the current code (the newer `run_health_check` audits OSPF + BGP in one call).
- [ ] **Clean the lab to a known state** — remove leftover demo loopbacks: `SW1 Lo1000 (90.90.90.90)`, `SW2 Lo50 (30.30.30.30)`, `SW4 Lo200 (50.50.50.50)`. Either remove them ahead of time, or decide to use them as a "find the leftover config" beat.
- [ ] **Confirm health** — `run_health_check` over the whole lab: 4 switches healthy, OSPF 3/3 FULL, eBGP 3/3 Established.
- [ ] **Pick the demo host** — Claude Desktop / Claude Code (per-call approval prompt) for the *write* demo; keep any Open WebUI / Ollama path **read-only** on screen.
- [ ] **Writes gate** — for the live config change, start the server with `PACKET_CODERS_ALLOW_WRITES=true` and have the **server console visible** (the one-time confirm code prints there).
- [ ] Have a terminal showing `server.py` ready for the "tools are just Python functions" beat.

---

## Segment 0 — Cold open  ·  ~1 min

**Land:** the gap is *doing*, not *knowing*.

> "If you're a network engineer, you've probably already pasted a config into ChatGPT and asked
> 'why isn't this BGP session coming up?' And it gives you a genuinely good answer. But notice what
> just happened: *you* were the hands. You copied the output in, you read the suggestion, you went
> back to the CLI and typed it. The model is smart, but it's behind glass — it can't see your network
> and it can't touch it.
>
> Today I want to show you the thing that takes the glass away. It's called MCP — Model Context
> Protocol — and by the end I'll have a model log into four live Arista switches, check OSPF and BGP,
> and make a real config change, with me approving it. Same model you already use. The difference is
> it now has *tools*."

---

## Segment 1 — The ceiling of chat  ·  ~2 min

**Land:** plain chat has three hard limits — no live data, no actions, and you're the integration.

> "Let's be precise about what plain chat can't do, because that's what MCP fixes.
>
> **One — it has no live data.** It knows networking in general, but it doesn't know *your* SW3's
> neighbor table at 9am today. Anything current, you have to paste in.
>
> **Two — it can't take an action.** It can write you a perfect `router bgp` block, but it can't apply
> it. There's no hands on the keyboard.
>
> **Three — and this is the real tax — *you* are the integration.** You're the glue. Copy from the
> switch, paste to the chat, read the answer, copy back to the switch. Every loop is manual, and every
> manual loop is where typos and tired-at-4pm mistakes live.
>
> The instinct is 'I'll just write a script.' And sure — but now you're maintaining Python, parsing
> `show` output with regex, and the moment the question changes slightly the script doesn't cover it.
> MCP is the middle path: the model stays flexible like chat, but it gets a clean, safe set of *actions*
> it can take on your behalf."

---

## Segment 2 — What MCP actually is  ·  ~3 min

**Land:** MCP standardizes how a model gets tools. Three roles: host, model, server. The model never speaks MCP — the host does.

> "Here's the mental model. People call MCP 'USB-C for AI tools,' and that's actually a good analogy.
> Before USB-C, every device had its own connector. Before MCP, every AI app wired up tools its own way.
> MCP is the standard plug: build a tool once, and any MCP-aware app can use it.
>
> There are **three pieces**, and getting these straight is the whole 'aha':
>
> - **The MCP server** — that's the tools. In our case, a little Python program that knows how to SSH to
>   my switches and run commands. Each tool is literally just a typed Python function with a good
>   docstring. I'll show you the file — it's almost boring how simple it is. That's the point.
> - **The host** — the app you're actually in: Claude Desktop, Claude Code, Cursor, or a local chat UI.
>   The host runs the 'tool-calling loop': it shows the tools to the model, and when the model asks to
>   use one, the host actually calls it and feeds the result back.
> - **The model** — Claude, GPT, a local Qwen, whatever. **The model never speaks MCP.** It just sees
>   'here are some tools and what they do' and decides 'I should call `get_bgp_summary` on SW1.' The
>   host does the plumbing.
>
> Why does that separation matter to you? Because it means **you can swap any piece**. Same tools work
> with a cloud model or a fully local one. Change the model, the tools don't care. Add a tool, every
> host you use gets it for free. You're not building a brittle one-off integration — you're publishing a
> capability."

**Optional show-the-code beat (~30s):** open `server.py`, point at one `@mcp.tool` function.

> "This is the entire definition of a tool. A Python function, type hints, a docstring. The docstring is
> the part the model reads to decide when to use it — so for us, writing tools is mostly *writing good
> documentation*. The networking logic lives in a normal service layer behind it. FastMCP is deliberately thin."

---

## Segment 3 — Why this matters for network engineers  ·  ~2 min

**Land:** our jobs are read-heavy and tool-shaped. This fits like a glove.

> "Now, why is networking *especially* a good fit? Because so much of our day is the same shape:
> *go look at a thing, interpret it, maybe change one thing, verify it.* That's exactly what a
> tool-calling model is good at.
>
> Think about the everyday stuff: 'are all my OSPF adjacencies up?' 'which BGP sessions are flapping?'
> 'did that change actually propagate to the other switches?' Today that's you, SSHing into box after
> box, eyeballing output. With MCP, you ask once in plain English and the model fans out across every
> device, reads the right command *per platform* — because the tool knows EOS vs IOS vs Junos — and
> gives you the synthesized answer. 'Yes, all four switches, three-of-three FULL.'
>
> And the key safety idea, which I'll hammer in the demo: **reads are wide open, writes are gated.** The
> model can look at everything. But to *change* anything, a human has to approve it — and I built it so
> the model literally cannot approve its own change. That's the line that makes this usable on real gear
> instead of just a party trick."

---

## Segment 4 — Standard MCP vs. MCPo (OpenAPI)  ·  ~3 min

**Land:** MCP is the native protocol; mcpo is a bridge that re-exposes the *same* tools as a plain REST/OpenAPI server so non-MCP apps can use them.

> "Okay, the part I really wanted to get to, because it tripped me up at first too: **standard MCP versus
> MCPo.**
>
> **Standard MCP** is the native protocol. Hosts like Claude Desktop and Claude Code speak it directly.
> It runs either over **stdio** — the host launches the tool server as a local subprocess and they talk
> over standard in/out — or over **HTTP** for remote servers. It's session-based: the host and server
> have a live conversation. If your client speaks MCP, this is all you need. It's the cleanest path.
>
> **But here's the catch I hit.** A lot of tools you might *want* to use as your chat UI — Open WebUI is
> the big one — **don't speak MCP.** What they *do* speak is **OpenAPI** — that's the standard REST API
> description, the Swagger thing, that basically every web tool on earth understands.
>
> That's what **mcpo** is. MCPo — 'MCP-to-OpenAPI.' It's a little proxy that sits in front of your MCP
> server and **re-exposes the exact same tools as a normal REST API** with an auto-generated OpenAPI
> spec. You don't rewrite anything — your tools are still the same Python functions. mcpo just translates.
>
> So now you get a few real wins:
> - **Any OpenAPI-aware app can use your tools** — Open WebUI, custom scripts, whatever. Not just MCP clients.
> - **You get interactive docs for free** — there's a `/docs` page, you can literally click 'try it' in a browser, or hit it with `curl`. Way easier to debug than a stdio session.
> - **Standard HTTP everything** — normal auth with an API key, normal logging, normal reverse proxy.
> - **One process, many servers** — mcpo can mount several MCP servers behind one port, each under its
>   own URL prefix. So my lab tools live at `/packet-coders`, and I can bolt on the official filesystem
>   connector at `/filesystem` — and now the model can check the lab *and* save the report to a file.
>
> The honest trade-off: mcpo adds a hop, and it's request/response REST rather than a persistent MCP
> session. For a local chat UI driving read tools, you won't feel it.
>
> So the way I'd frame it: **if your client speaks MCP, use MCP directly** — that's Claude Desktop, Claude
> Code. **If your client only speaks REST/OpenAPI** — like Open WebUI, or you want a local-LLM stack with
> no cloud — **put mcpo in front and you get the same tools over standard HTTP.** Same tools either way.
> That's the thing to remember: mcpo isn't a different set of tools, it's a different *doorway* to the
> same ones."

---

## Segment 5 — Live demo  ·  ~6–7 min

**Setup line:** "Let me make this real. This is connected to four Arista EOS switches in a full mesh,
running OSPF and eBGP at the same time. Everything I'm about to do, I'm doing in plain English."

> Run each step by *typing the natural-language prompt into the host* and narrating what the model chose
> to do. The expected outputs below are from the live lab so you know what 'good' looks like.

### Demo 1 — "What's even in this lab?"  (tool: `list_lab_devices`)

**Prompt:** *"What devices are in my lab?"*

**What to narrate:** "Notice I didn't tell it a command or an IP. It picked the `list_lab_devices` tool on its own."

**Expected:** SW1–SW4 (Arista EOS, real SSH) plus a few mock devices. Router IDs `10.255.0.1`–`.4`.

### Demo 2 — "Is the control plane healthy?"  (tool: `run_health_check`)

**Prompt:** *"Run a health check across the whole lab — are OSPF and BGP healthy everywhere?"*

**What to narrate:** "One sentence, and it's fanning out to all four switches concurrently, running the
right commands for EOS, and summarizing. This is the part that replaces a tedious round of SSH sessions."

**Expected:** all four `healthy`; each switch shows 3 OSPF routes + 3 BGP routes; adjacencies up.

### Demo 3 — "Prove the adjacencies"  (tools: `get_ospf_neighbors`, `get_bgp_summary`)

**Prompt:** *"Show me SW1's OSPF neighbors and its BGP summary. Are they all up?"*

**What to narrate:** "Two tools, one question. And it reads them back in English instead of me parsing columns."

**Expected (real output you'll get):**

OSPF — three neighbors, all `FULL`:
```
10.255.0.3   FULL/DR   10.13.13.3   Ethernet2
10.255.0.4   FULL/DR   10.14.14.4   Ethernet3
10.255.0.2   FULL/DR   10.12.12.2   Ethernet1
```
BGP — three eBGP sessions, all `Estab`, 3 prefixes each:
```
Router identifier 10.255.0.1, local AS 65001
10.12.12.2  AS 65002  Estab  3/3
10.13.13.3  AS 65003  Estab  3/3
10.14.14.4  AS 65004  Estab  3/3
```

### Demo 4 — A targeted question  (tool: `send_command`)

**Prompt:** *"On SW3, what's in the routing table for the other switches' loopbacks?"*

**What to narrate:** "For anything the purpose-built tools don't cover, there's a general read tool —
but it's **read-only**. It blocks config and destructive commands at the door. The model can look;
it can't break."

**Expected:** remote loopbacks (`10.255.0.x/32`) show as `B` (eBGP); remote transit `/24`s show as `O` (OSPF).

### Demo 5 — The real change, with a human gate  (tool: `configure_device`)  ← the money shot

**Prompt:** *"Add a loopback 99 with address 10.99.99.99/32 on SW1, advertise it into OSPF, and confirm
the other switches learn it."*

**What to narrate — this is the most important 90 seconds of the talk:**

> "Watch what happens. The model proposes the config — but it does **not** just run it. First call is a
> preview, and a one-time confirmation code prints **only to my server console** — never back to the model.
> So even on a fully automatic agent, the model *cannot* approve its own change. *I* read the code off the
> console and hand it back to apply. That's the human-in-the-loop gate, and it works with any model.
> [Apply it.] Now let's verify it propagated — ask SW2 for its route to 10.99.99.99."

**Expected after apply:** SW2/SW3/SW4 learn `10.99.99.99/32` as an `O` (OSPF) route.

**Cleanup (do on camera or right after):** *"Remove loopback 99 from SW1."* — same gate, confirm, gone.
Leave the lab as you found it.

> **Optional flex:** "And just to close the loop on the earlier point — I can run this *exact* same demo
> driven by a local Qwen model through Open WebUI and mcpo, no cloud API at all. Same tools, different doorway."

---

## Segment 6 — Close  ·  ~1 min

**Land:** you already have the model; the leap is giving it tools — and a safe gate.

> "So that's the journey. You started at chat — smart, but behind glass, and you're the hands. MCP gives
> the model a clean set of tools, so it can actually read your network and propose changes. The protocol
> standardizes the plug, so you build a tool once and use it everywhere — Claude Desktop, Claude Code, or
> a fully local stack through mcpo. And the guardrail that makes it real for production-adjacent work is
> that **the model can look all it wants, but a human approves every change.**
>
> You don't have to boil the ocean. Start with read-only tools against a lab — `list devices`,
> `health check`, `check OSPF`. That alone will change how you work. The whole thing I showed is open
> source; clone it, point it at your own lab, and you'll have a local model reading your network in about
> five minutes."

---

## Appendix — quick-reference cards

### The three roles (say these slowly)
| Role | What it is | In this demo |
| --- | --- | --- |
| **MCP server** | The tools — typed functions | `packet-coders-mcp` (SSHes to switches) |
| **Host** | Runs the tool-calling loop | Claude Desktop / Claude Code / Open WebUI |
| **Model** | Decides which tool to call | Claude, or local Qwen — never speaks MCP itself |

### MCP vs. mcpo (the one-liner)
- **MCP** = native protocol, stdio or HTTP, session-based. Use it when your client speaks MCP (Claude Desktop/Code).
- **mcpo** = a proxy that re-exposes the *same* MCP tools as a standard **OpenAPI/REST** server. Use it when your client only speaks REST (Open WebUI) or for a fully-local stack. Bonus: free `/docs`, API-key auth, `curl`-able, multi-server behind one port.

### The six tools
| Tool | Read/Write | Everyday question it answers |
| --- | --- | --- |
| `list_lab_devices` | read | "What's in my lab?" |
| `run_health_check` | read | "Is OSPF/BGP healthy everywhere?" |
| `get_ospf_neighbors` | read | "Are my adjacencies FULL?" |
| `get_bgp_summary` | read | "Are my BGP sessions established?" |
| `send_command` | read (blocks config) | any targeted `show` command |
| `configure_device` | **write — gated** | "make this change" → human confirms |

### Safety story (one breath)
"Reads are open. Writes are gated. The confirm code prints only to the server console, never to the
model — so the model can't self-approve. And a single flag, `PACKET_CODERS_ALLOW_WRITES=false`, hides the
write tool entirely for a strictly read-only deployment."
</content>
</invoke>
