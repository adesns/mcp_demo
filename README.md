# txt_counter：MCP 桌面 Markdown（.md）文件统计器

一个最小可运行的 MCP Demo：

- **MCP Server**：`txt_counter.py`（基于 `mcp.server.fastmcp.FastMCP`），提供“查看桌面 `.md` 文件”的 3 个工具
- **MCP Client**：`client.py`（STDIO 直连 MCP Server），用 **Qwen（DashScope OpenAI 兼容接口）** 做工具路由/多步调用

> 说明：当前桌面路径**写死**为 ` /home/standard/桌面 `（Ubuntu）。需要改路径请编辑 `txt_counter.py` 里的 `DESKTOP_PATH`。

## 功能（Tools）

Server 暴露 3 个工具（只处理 `.md`）：

- **`count_desktop_md_files`**：统计桌面 `.md` 文件数量
- **`list_desktop_md_files`**：列出桌面 `.md` 文件名
- **`read_desktop_md_file`**：读取桌面某个 `.md` 文件内容（按文件名读取，支持 `max_chars` 截断）

## 快速开始

### 0) 环境要求

- Python **3.11+**
- 推荐使用 [uv](https://github.com/astral-sh/uv)（仓库包含 `uv.lock`）

### 1) 安装依赖

用 uv（推荐）：

```bash
uv sync
```

或直接用 pip（不推荐但也能跑）：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 配置：Qwen 环境变量（运行 Client 必配）

`client.py` 当前**只支持**使用 Qwen 来决定“下一步调用哪个 MCP 工具”，因此必须配置：

```bash
export QWEN_API_KEY="你的key"
export QWEN_MODEL="qwen-plus"   # 可选：qwen-turbo / qwen-plus / qwen-max 等
# export QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"  # 可选，默认就是这个
```

### 3) 运行 Client（中文提问 + 自动工具调用）

交互模式：

```bash
uv run --with mcp python client.py
```

单次提问：

```bash
uv run --with mcp python client.py 我桌面有多少 md 文件
```

读取并总结（通常会先 `list` 确认存在，再 `read`，最后总结）：

```bash
uv run --with mcp python client.py 给我总结 设计模式.md 中有什么内容
```

### 4) （可选）直接验证 Server 工具（不走 MCP，不需要 Qwen）

```bash
uv run python -c "from txt_counter import count_desktop_md_files, list_desktop_md_files; print(count_desktop_md_files()); print(list_desktop_md_files())"
```

读取某个文件（示例：`设计模式.md`）：

```bash
uv run python -c "from txt_counter import read_desktop_md_file; print(read_desktop_md_file('设计模式.md', max_chars=2000))"
```

示例：

```bash
export CLIENT_LOG_LEVEL="DEBUG"
uv run --with mcp python client.py 给我总结 设计模式.md 中有什么内容
```

## 项目结构

```text
.
├─ txt_counter.py   # MCP Server（FastMCP）
├─ client.py        # MCP Client（Qwen 路由 + STDIO 直连）
├─ pyproject.toml
├─ uv.lock
├─ requirements.txt
└─ README.md
```
