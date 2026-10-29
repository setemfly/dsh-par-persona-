"""Expression verifier: cheap, deterministic claims guard (spec §10.4).

It cannot prove a reply is true. It can catch the expensive failure: the model
claiming it *did* something when the executor did nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_ACTION_CLAIM = re.compile(
    r"(我(已经|已|刚刚|刚)(帮你|给你|替你)?.{0,6}(发|订|买|改|删|转账|下载|安装|提交|上传|取消|预订|寄|邮寄))"
    r"|(I(?:'ve| have) (?:already )?(?:sent|booked|deleted|installed|uploaded|submitted|transferred|cancelled))",
    re.IGNORECASE,
)
_HIDDEN_STATE = re.compile(r"(我的\s*(valence|arousal|stress|dominance|trust)\s*=\s*[\d.]+)", re.IGNORECASE)


@dataclass
class VerifierResult:
    ok: bool
    issues: list[dict] = field(default_factory=list)


def verify_reply(text: str, *, executed_actions: list[str]) -> VerifierResult:
    issues: list[dict] = []
    if not executed_actions and _ACTION_CLAIM.search(text):
        issues.append(
            {
                "type": "unbacked_action_claim",
                "severity": "high",
                "detail": "reply claims an action was performed but no step executed",
            }
        )
    m = _HIDDEN_STATE.search(text)
    if m:
        issues.append(
            {
                "type": "internal_state_leak",
                "severity": "medium",
                "detail": f"leaked internal state token: {m.group(1)}",
            }
        )
    return VerifierResult(ok=not issues, issues=issues)
