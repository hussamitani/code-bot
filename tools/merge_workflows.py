#!/usr/bin/env python3
"""Merge the CodeBot n8n exports in workflows/ into one workflow JSON.

- every node is renamed "[Tag] Name" so the shared names (Settings, Config, ...) stay unique
- $('Name') / $node["Name"] / $items('Name') references are rewritten to the new names
- Execute Workflow nodes between the CodeBot workflows are removed and wired directly
  to the former Execute Workflow Trigger (kept as a pass-through NoOp node)
- each workflow becomes its own row on the canvas, labelled with a sticky note
"""
import json, re, sys, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "workflows"
OUT = SRC / "CodeBot - All-in-one.json"

FILES = {  # file -> tag, in canvas order
    "CodeBot - Telegram Router.json": "Router",
    "CodeBot - _work (Telegram → Claude).json": "Work",
    "CodeBot - Chat.json": "Chat",
    "CodeBot - Connect Repo.json": "Connect",
    "CodeBot - Planning.json": "Planning",
    "CodeBot - Start Claude Routine.json": "Start",
    "CodeBot - Dev-Orchestrator.json": "Orchestrator",
    "CodeBot - Signal Sweep.json": "Sweep",
    "CodeBot - Setup (one-time).json": "Setup",
}
# workflow display name -> tag (what the Execute Workflow nodes point at)
CALLEE = {
    "CodeBot - /work (Telegram → Claude)": "Work",
    "CodeBot - Connect Repo": "Connect",
    "CodeBot - Chat": "Chat",
    "CodeBot - Planning": "Planning",
    "CodeBot - Start Claude Routine": "Start",
}
ENTRY = "n8n-nodes-base.executeWorkflowTrigger"
EXEC = "n8n-nodes-base.executeWorkflow"


def rename_refs(value, mapping):
    """Rewrite node-name references inside any string of a JSON structure."""
    if isinstance(value, dict):
        return {k: rename_refs(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [rename_refs(v, mapping) for v in value]
    if not isinstance(value, str):
        return value
    def sub(pattern, fmt):
        nonlocal value
        def r(m):
            q, name = m.group(1), m.group(2)
            return fmt(q, mapping[name]) if name in mapping else m.group(0)
        value = re.sub(pattern, r, value)
    sub(r"\$\(\s*(['\"])(.+?)\1\s*\)", lambda q, n: f"$({q}{n}{q})")
    sub(r"\$node\[\s*(['\"])(.+?)\1\s*\]", lambda q, n: f"$node[{q}{n}{q}]")
    sub(r"\$items\(\s*(['\"])(.+?)\1", lambda q, n: f"$items({q}{n}{q}")
    return value


def main():
    nodes, conns, tag_entry, seen_ids = [], {}, {}, set()
    y_cursor = 0
    parsed = []
    for fname, tag in FILES.items():
        wf = json.loads((SRC / fname).read_text())
        parsed.append((tag, wf))

    exec_target = {}  # (tag, exec node name) -> callee tag
    for tag, wf in parsed:
        mapping = {n["name"]: f"[{tag}] {n['name']}" for n in wf["nodes"]}
        for n in wf["nodes"]:
            if n["type"] == EXEC:
                cached = n["parameters"]["workflowId"].get("cachedResultName")
                exec_target[(tag, n["name"])] = CALLEE[cached]
        ys = [n["position"][1] for n in wf["nodes"]]
        top, bottom = min(ys), max(ys)
        label = {
            "parameters": {"content": f"## {tag}\n{wf['name']}", "height": 80, "width": 420},
            "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
            "position": [min(n["position"][0] for n in wf["nodes"]) - 40, y_cursor - 140],
            "id": str(uuid.uuid4()), "name": f"[{tag}] label",
        }
        nodes.append(label)
        for n in wf["nodes"]:
            if n["type"] == EXEC:
                continue
            n = json.loads(json.dumps(n))
            n["name"] = mapping[n["name"]]
            n["parameters"] = rename_refs(n["parameters"], mapping)
            n["position"] = [n["position"][0], n["position"][1] - top + y_cursor]
            if n["id"] in seen_ids:
                n["id"] = str(uuid.uuid4())
            seen_ids.add(n["id"])
            if n["type"] == ENTRY:
                tag_entry[tag] = n["name"]
                n["type"], n["typeVersion"], n["parameters"] = "n8n-nodes-base.noOp", 1, {}
                n["notes"] = "Was the Execute Workflow Trigger; now a pass-through entry point."
            nodes.append(n)
        for src, outs in wf["connections"].items():
            conns_src = mapping[src]
            conns[conns_src] = {
                kind: [[{**c, "node": mapping[c["node"]]} for c in branch] for branch in branches]
                for kind, branches in outs.items()
            }
        y_cursor += bottom - top + 360

    # replace connections that pointed at Execute Workflow nodes with the callee's entry node
    for tag, wf in parsed:
        for (t, exec_name), callee in exec_target.items():
            if t != tag:
                continue
            old = f"[{tag}] {exec_name}"
            assert old not in conns, f"{old} has downstream connections"
            for outs in conns.values():
                for branches in outs.values():
                    for branch in branches:
                        for c in branch:
                            if c["node"] == old:
                                c["node"] = tag_entry[callee]
    # fan-in from several callers is fine, but drop duplicate edges
    for outs in conns.values():
        for kind, branches in outs.items():
            for branch in branches:
                uniq = []
                for c in branch:
                    if c not in uniq:
                        uniq.append(c)
                branch[:] = uniq

    merged = {
        "name": "CodeBot - All-in-one",
        "nodes": nodes,
        "pinData": {},
        "connections": conns,
        "active": False,
        # successful executions hold bot/worker tokens (see SETUP.md), so keep them off
        "settings": {"executionOrder": "v1", "availableInMCP": False, "saveDataSuccessExecution": "none"},
        "tags": [],
    }
    OUT.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(nodes)} nodes")


if __name__ == "__main__":
    sys.exit(main())
