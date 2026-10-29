"""`par` — persona runtime CLI.

    par doctor                    check config, persona, DB, provider wiring
    par providers                 list configured providers
    par chat                      interactive REPL
    par say "..."                 one-shot turn
    par audit verify              verify the hash chain
    par memory stats              memory counts for the configured agent
    par serve                     web chat + OpenAI-compatible HTTP endpoint
    par update list|propose|approve|apply|rollback
                                  governed persona/policy versioning
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from par.config.settings import load_config
from par.identity.persona import load_persona
from par.llm.registry import ProviderRegistry, load_providers_file

DEFAULT_CONFIG = "configs/runtime.yaml"


def _config_path(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    if Path(DEFAULT_CONFIG).exists():
        return Path(DEFAULT_CONFIG)
    return Path(__file__).resolve().parents[2] / DEFAULT_CONFIG


async def _cmd_chat(args: argparse.Namespace) -> int:

    cfg = _config_path(args.config)
    agent = await _make_agent(cfg, args)
    print(f"{agent.persona.personality.display_name}> {agent.persona.greeting}")
    if args.once:
        result = await agent.turn(args.once)
        print(result.reply)
        await agent.aclose()
        return 0
    try:
        while True:
            try:
                line = input("你> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line in {"/exit", "/quit", ":q"}:
                break
            if line == "/state":
                print(json.dumps({"affect": agent.affect.model_dump(mode="json"), "labels": agent.labels}, ensure_ascii=False, indent=2))
                continue
            if line == "/audit":
                for row in agent.audit.read(limit=5):
                    print(row["seq"], row["kind"], row["ts"])
                continue
            result = await agent.turn(line)
            print(f"\n{agent.persona.personality.display_name}> {result.reply}\n")
            if not result.verifier.ok:
                print(f"[verifier] {result.verifier.issues}", file=sys.stderr)
    finally:
        await agent.aclose()
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    cfg_path = _config_path(args.config)
    problems: list[str] = []
    try:
        config = load_config(cfg_path)
    except Exception as exc:
        print(f"FAIL config {cfg_path}: {exc}")
        return 2
    print(f"ok   config      {cfg_path}")
    try:
        persona = load_persona(config.path(config.persona))
        print(f"ok   persona     {persona.personality.display_name} v{persona.personality.version}")
    except Exception as exc:
        problems.append(f"persona: {exc}")
    try:
        specs = load_providers_file(config.path(config.providers_file))
        reg = ProviderRegistry(specs)
        names = reg.names
        print(f"ok   providers   {', '.join(names) if names else '(none)'}")
        if config.provider not in names:
            problems.append(f"configured provider '{config.provider}' not found")
    except Exception as exc:
        problems.append(f"providers: {exc}")
    db = config.db_path
    print(f"ok   database    {db}")
    if problems:
        for p in problems:
            print(f"FAIL {p}")
        return 2
    print("ok   status      ready")
    return 0


def _cmd_providers(args: argparse.Namespace) -> int:
    config = load_config(_config_path(args.config))
    reg = ProviderRegistry(load_providers_file(config.path(config.providers_file)))
    for row in reg.describe():
        print(f"{row['name']:<12} {row['kind']:<16} {row['model']:<28} {row['base_url'] or ''}")
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    from par.audit.log import AuditIntegrityError, AuditLog

    config = load_config(_config_path(args.config))
    log = AuditLog(config.db_path)
    try:
        if args.action == "verify":
            report = log.verify()
            print(f"ok audit chain  records={report['records']} head={report['head'][:16]}…")
        else:
            head = log.head()
            print(json.dumps(head, ensure_ascii=False))
    except AuditIntegrityError as exc:
        print(f"FAIL audit integrity: {exc}")
        return 2
    finally:
        log.close()
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from par.server.app import serve

    serve(
        str(_config_path(args.config)),
        host=args.host,
        port=args.port,
        provider=args.provider,
        model=args.model,
    )
    return 0


def _cmd_update(args: argparse.Namespace) -> int:
    from par.audit.log import AuditLog
    from par.updates.manager import UpdateError, UpdateManager

    config = load_config(_config_path(args.config))
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditLog(config.db_path)
    mgr = UpdateManager(
        agent_id=config.agent_id,
        db_path=config.db_path,
        versions_dir=config.path("data/versions"),
        audit=audit,
    )
    try:
        if args.action == "list":
            kind = getattr(args, "kind", None)
            rows = mgr.store.list(config.agent_id, kind)
            if not rows:
                print("(no versions)")
            for v in rows:
                print(f"{v.version_id:<22} {v.kind:<8} {v.status:<12} {v.proposed_at}  {v.proposed_by}")
        elif args.action == "propose":
            import yaml

            content = yaml.safe_load(Path(args.file).read_text(encoding="utf-8"))
            v = mgr.propose(
                kind=args.kind,
                content=content,
                rationale=args.rationale,
                proposed_by=args.by,
            )
            print(f"proposed {v.version_id} ({v.kind}) status={v.status}")
        elif args.action == "approve":
            v = mgr.approve(args.version_id, approved_by=args.by, approval_ref=args.ref)
            print(f"approved {v.version_id} by {v.approved_by} ref={v.approval_ref}")
        elif args.action == "apply":
            v = mgr.apply(args.version_id)
            print(f"applied  {v.version_id} -> {v.applied_path}")
        elif args.action == "rollback":
            v = mgr.rollback(args.kind)
            print(f"rolled back {args.kind} -> {v.version_id} ({v.applied_path})")
    except UpdateError as exc:
        print(f"FAIL {exc}")
        return 2
    finally:
        mgr.close()
        audit.close()
    return 0


def _cmd_memory(args: argparse.Namespace) -> int:
    from par.memory.store import MemoryStore

    config = load_config(_config_path(args.config))
    store = MemoryStore(config.db_path)
    print(json.dumps(store.counts(config.agent_id), ensure_ascii=False))
    store.close()
    return 0


async def _make_agent(cfg: Path, args: argparse.Namespace) -> object:
    from par.orchestrator.agent import Agent

    return Agent.create(cfg, provider=getattr(args, "provider", None), model=getattr(args, "model", None))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="par", description="Persona runtime")
    p.add_argument("--config", help="path to runtime.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    chat = sub.add_parser("chat", help="interactive chat")
    chat.add_argument("--provider")
    chat.add_argument("--model")
    chat.add_argument("--once", metavar="TEXT", help="send one message and exit")
    chat.set_defaults(func=lambda a: asyncio.run(_cmd_chat(a)))

    say = sub.add_parser("say", help="one-shot message")
    say.add_argument("text")
    say.add_argument("--provider")
    say.add_argument("--model")
    say.set_defaults(func=lambda a: asyncio.run(_cmd_chat(argparse.Namespace(**{**vars(a), "once": a.text}))))

    doctor = sub.add_parser("doctor", help="self-check")
    doctor.set_defaults(func=_cmd_doctor)

    prov = sub.add_parser("providers", help="list providers")
    prov.set_defaults(func=_cmd_providers)

    audit = sub.add_parser("audit", help="audit log")
    audit.add_argument("action", choices=["verify", "head"])
    audit.set_defaults(func=_cmd_audit)

    mem = sub.add_parser("memory", help="memory stats")
    mem.add_argument("action", choices=["stats"])
    mem.set_defaults(func=_cmd_memory)

    serve = sub.add_parser("serve", help="local web chat + OpenAI-compatible endpoint")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=7860)
    serve.add_argument("--provider")
    serve.add_argument("--model")
    serve.set_defaults(func=_cmd_serve)

    upd = sub.add_parser("update", help="governed persona/policy updates")
    upd_sub = upd.add_subparsers(dest="action", required=True)
    u_list = upd_sub.add_parser("list")
    u_list.add_argument("--kind", choices=["persona", "policy", "runtime"])
    u_list.set_defaults(func=_cmd_update)
    u_prop = upd_sub.add_parser("propose")
    u_prop.add_argument("--kind", required=True, choices=["persona", "policy", "runtime"])
    u_prop.add_argument("--file", required=True, help="YAML file with the new content")
    u_prop.add_argument("--rationale", required=True)
    u_prop.add_argument("--by", required=True)
    u_prop.set_defaults(func=_cmd_update)
    u_appr = upd_sub.add_parser("approve")
    u_appr.add_argument("version_id")
    u_appr.add_argument("--by", required=True)
    u_appr.add_argument("--ref", required=True, help="approval reference (ticket/chat id)")
    u_appr.set_defaults(func=_cmd_update)
    u_apply = upd_sub.add_parser("apply")
    u_apply.add_argument("version_id")
    u_apply.set_defaults(func=_cmd_update)
    u_rb = upd_sub.add_parser("rollback")
    u_rb.add_argument("--kind", required=True, choices=["persona", "policy", "runtime"])
    u_rb.set_defaults(func=_cmd_update)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
