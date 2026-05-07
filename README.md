# down.mptext WeChat Key Refresh Skill

用于在 Codex 中检查、刷新并写回 `down.mptext.top` 微信公众号文章抓取 API Key 的技能包。

这个项目不会保存微信账号密码。它通过浏览器打开 `down.mptext.top`，复用或等待扫码登录后的站点会话，从 cookie、页面存储或接口响应中提取新的 auth key，验证成功后写入当前项目的 `.env`。

## 适用场景

- 当前项目依赖 `down.mptext.top` 抓取微信公众号文章。
- `.env` 中的 `WECHAT_PUBLIC_API_KEY` 过期、失效或需要轮换。
- 希望用 Codex 自动判断 key 是否有效，并在需要时引导扫码登录刷新。
- 希望定时检查 key 状态，并在 macOS 上收到失效提醒。

## 项目结构

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── down-mptext-api.md
└── scripts/
    └── refresh_down_mptext_key.py
```

- `SKILL.md`: Codex skill 说明和触发规则。
- `scripts/refresh_down_mptext_key.py`: 检查、刷新、写入 `.env` 的主脚本。
- `references/down-mptext-api.md`: `down.mptext.top` auth key 行为和接口备注。
- `agents/openai.yaml`: skill 在 OpenAI/Codex 环境中的展示元数据。

## 安装

把本目录放到 Codex skills 目录下，例如：

```bash
mkdir -p ~/.codex/skills
cp -R downwx_api.skill ~/.codex/skills/down-mptext-wechat-key-refresh
```

脚本依赖 Python 3、`requests` 和 `selenium`：

```bash
python -m pip install requests selenium
```

刷新流程默认使用 Chrome，并通过 Selenium 打开浏览器。也可以通过参数或环境变量切换到 Edge、Safari 或 Firefox。

## 快速使用

以下命令都应在“拥有 `.env` 的业务项目目录”中运行，而不是必须在本 skill 仓库内运行。

检查当前项目的默认 key：

```bash
python ~/.codex/skills/down-mptext-wechat-key-refresh/scripts/refresh_down_mptext_key.py --check
```

如果 key 已失效，打开浏览器刷新并写回 `.env`：

```bash
python ~/.codex/skills/down-mptext-wechat-key-refresh/scripts/refresh_down_mptext_key.py --refresh
```

用于定时提醒的检查模式：

```bash
python ~/.codex/skills/down-mptext-wechat-key-refresh/scripts/refresh_down_mptext_key.py --remind --notify
```

指定环境变量名、env 文件或站点地址：

```bash
python ~/.codex/skills/down-mptext-wechat-key-refresh/scripts/refresh_down_mptext_key.py \
  --refresh \
  --key-env MP_TEXT_AUTH_KEY \
  --env-file .env.local \
  --base-url https://down.mptext.top
```

## Codex 中的用法

安装后，可以直接让 Codex 处理当前项目的 key，例如：

```text
检查这个项目的 down.mptext API key 是否有效，失效的话帮我刷新。
```

Codex 会根据 `SKILL.md` 调用该技能，优先执行 `--check`，仅在 key 无效时进入浏览器扫码刷新流程。

## 配置项

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--env-file` | `./.env` | 读取和更新的 env 文件 |
| `--key-env` | `WECHAT_PUBLIC_API_KEY` | 保存 API key 的变量名 |
| `--base-url` | `https://down.mptext.top` | API 和登录站点基础地址 |
| `--login-url` | 空 | 浏览器打开的登录地址，默认使用 `--base-url` |
| `--browser` | `chrome` | 可选 `chrome`、`edge`、`safari`、`firefox` |
| `--user-data-dir` | `~/.codex/down-mptext-chrome-profile` | 持久化浏览器 profile，便于复用登录状态 |
| `--timeout` | `15` | HTTP 请求超时时间，单位秒 |
| `--wait-seconds` | `600` | 刷新模式中等待扫码登录的最长时间 |
| `--poll-seconds` | `3` | 浏览器 cookie/storage 轮询间隔 |
| `--notify` | 关闭 | `--remind` 发现 key 无效时显示系统通知 |
| `--no-backup` | 关闭 | 更新 `.env` 前不创建 `.env.bak` |
| `--keep-browser-open` | 关闭 | 刷新完成后保留浏览器窗口 |

也可以通过环境变量设置部分默认值：

```bash
export DOWN_MPTEXT_BROWSER=chrome
export DOWN_MPTEXT_USER_DATA_DIR=~/.codex/down-mptext-chrome-profile
```

## 工作流程

1. 从当前工作目录的 `.env` 读取 `WECHAT_PUBLIC_API_KEY`。
2. 请求 `GET https://down.mptext.top/api/public/v1/authkey` 验证 key。
3. 如果 key 有效，直接退出，不打开登录流程。
4. 如果 key 无效，`--refresh` 会打开浏览器并等待站点登录成功。
5. 脚本从 `auth-key` cookie、页面 storage 或 auth-key 接口响应中寻找候选 key。
6. 候选 key 通过接口验证后写回 `.env`，默认同时生成 `.env.bak`。

## API 认证方式

`down.mptext.top` 支持以下方式传递 auth key：

```http
X-Auth-Key: <key>
```

或使用 cookie：

```text
auth-key=<key>
```

脚本验证成功的判断依据是响应 JSON 中的 `code: 0`，或 `base_resp.ret: 0`。

## 排错

如果 `--check` 提示 `empty key`，确认当前目录下是否存在 `.env`，以及变量名是否为 `WECHAT_PUBLIC_API_KEY`。

如果浏览器没有自动保持登录状态，确认 `--user-data-dir` 指向的是可写目录，并尽量不要和日常浏览器 profile 混用。

如果 Selenium 无法打开浏览器，先确认已安装 `selenium`，本机浏览器版本可用，并尝试显式指定浏览器：

```bash
python ~/.codex/skills/down-mptext-wechat-key-refresh/scripts/refresh_down_mptext_key.py --refresh --browser chrome
```

如果扫码登录后仍超时，可能是站点没有在 cookie/storage 或 auth-key 接口中暴露可验证的新 key。可以加长等待时间：

```bash
python ~/.codex/skills/down-mptext-wechat-key-refresh/scripts/refresh_down_mptext_key.py --refresh --wait-seconds 900
```

## 安全注意事项

- 不要把 `.env`、`.env.bak` 或真实 auth key 提交到 Git。
- 每次网站登录都可能轮换 key，刷新后应以最新写入 `.env` 的值为准。
- 正常巡检优先使用 `--check` 或 `--remind`，只有 key 无效或明确需要轮换时再执行 `--refresh`。

