# embedded-hmi-workflows

[English README](README.md)

面向嵌入式显示器与 HMI 开发的轻量工作流技能仓库。

这个仓库收纳了一组可复用的小型工程流程技能，当前主要覆盖以下场景：

- handoff / resume 交接与续接
- 基于仓库内配置的 build 执行
- 基于仓库内配置的 deploy 执行
- 面向工作流自动化的轻量共享脚本

第一版仓库刻意保持轻量。相比做成一个很重的框架，它更强调：

- 技能边界清晰
- 本地 secrets 与仓库内容分离
- 对公开发布更安全的默认行为

## 当前包含的技能

### Handoff

- `write-handoff`：刷新项目当前的标准 handoff / resume 入口
- `resume-handoff`：从标准 handoff 入口继续工作，并重新检查可变状态

### Build 与 Deploy

- `build-action`：从仓库内配置文件执行一次构建动作
- `deploy-action`：从仓库内配置文件执行一次部署动作

## 仓库结构

```text
embedded-hmi-workflows/
├─ skills/
│  ├─ write-handoff/
│  ├─ resume-handoff/
│  ├─ build-action/
│  └─ deploy-action/
├─ shared/
│  └─ handoff/
├─ tools/
└─ tests/
```

- `skills/`：技能定义与 agent 元数据
- `shared/`：被多个技能复用的小型共享脚本
- `tools/`：供 build / deploy 技能调用的可执行脚本
- `tests/`：面向公开发布安全性的聚焦测试

## 当前约定

### Build / Deploy 配置布局

当前 `build-action` 和 `deploy-action` 默认推荐这样的项目布局：

```text
project-root/
└─ project_ai/
   ├─ build-deploy.skill.yaml
   └─ build-deploy.secrets.local.json
```

说明：

- `build-deploy.skill.yaml` 适合在团队确认需要复用工作流入口时纳入仓库
- `build-deploy.secrets.local.json` 仅用于本地，不应提交到 Git
- 脚本也支持通过 `--config` 显式传入配置文件路径
- 仓库当前已附带一个最小起步模板：`project_ai/build-deploy.skill.example.yaml`

### Handoff 模式

handoff 技能当前支持多种恢复 / 写回布局，例如：

- `legacy-handoff`
- `single-current`
- `hybrid-compat`

handoff 相关共享逻辑位于 `shared/handoff/`。

## 安全与公开发布说明

这个仓库会尽量避免明显的敏感信息泄露，但仍然默认使用者需要保持谨慎。

- 不要提交本地 secrets 文件
- 不要提交 build / deploy 运行日志
- 对外分享示例前，先检查目标主机、远程路径、重启命令和健康检查命令
- 密码型 SSH 认证目前仍被支持，但更推荐 key-based auth
- `build` / `deploy` 工具在写命令日志时，会对 `sshpass -p` 密码做脱敏处理

## 验证

当前仓库包含的基础验证主要有：

- 确认命令日志中的密码会被脱敏
- 防止公开 deploy 文档中出现 RFC1918 私网 IP 示例
- 对已收录 Python 脚本做语法级编译检查

可用下面的命令运行聚焦测试：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_publish_safety -v
```

## 后续计划

后续可能继续补充：

- 示例配置文件
- 更完整的回归测试
- 面向公开仓库的 CI 检查
- 更多适用于嵌入式显示 / HMI 团队的工作流技能
