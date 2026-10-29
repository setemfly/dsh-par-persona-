# 受治理的自我更新（`par update`）

规格 §14.4 与 ADR-007 的落地：运行时**不做代码自修改**。允许的是"声明式状态"的版本化替换，并且必须由具名人类批准。

## 流程

```
propose ──► proposed
              │  approve --by <人> --ref <凭据>
              ▼
           approved
              │  apply
              ▼
           applied ──► rollback ──► 上一个 applied
```

`apply` 在 status 不是 `approved` 时直接拒绝；`propose` 校验内容（人格卡必须通过 schema、`protect_humans` 必须 1.0、必须有人工理由）。

## 命令

```bash
# 1) 提议：把新人格卡写成 YAML（结构同 linxi.yaml）
par update propose --kind persona --file new_linxi.yaml \
    --rationale "降低直接程度，增加耐心" --by ops

# 2) 批准：必须写名字和凭据（工单/会话 id）
par update approve persona-1a2b3c4d5e6f --by alice --ref TICKET-42

# 3) 应用：写入 data/versions/<agent>/persona/<id>.yaml，并切换指针
par update apply persona-1a2b3c4d5e6f

# 4) 查看 / 回滚
par update list --kind persona
par update rollback --kind persona
```

## 语义

- 版本内容存 `config_version` 表：`version_id / kind / content_sha256 / status / proposed_by / approval_ref / applied_path / previous_version_id`。
- 指针存 `config_pointer`：每个 `(agent_id, kind)` 只有一个当前版本。
- `Agent.create` 启动时若指针存在且文件存在，就加载指针指向的人格卡；否则回落到 `runtime.yaml` 的路径。
- 每次 propose/approve/apply/rollback 都写一条审计（kind=`config_update.*`），因此"谁在什么时候因为什么改了人格"可查。
- 回滚只改指针，不删历史文件；被回滚的版本标记 `rolled_back`。

## 为什么不做自动应用

模型无法调用这个模块：它没有对应工具，API 也不暴露 propose/apply 的写路径。更新入口在 CLI，需要人执行。这是"人高于人格"的可执行版本，而不是一句原则。

## 与代码更新的关系

代码、依赖、工具注册仍走正常发布流程（PR/评审/部署），本模块不碰。若未来引入 OTA，需要单独的供应链签名方案，不在本规格范围。
