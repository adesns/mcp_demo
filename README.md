## txt_counter（MCP 桌面 TXT 文件统计器）

你已经有了一个 MCP Server（`txt_counter.py`），它提供三个工具：

- `count_desktop_md_files`：统计桌面 `.md` 文件数量
- `list_desktop_md_files`：列出桌面 `.md` 文件名
- `read_desktop_md_file`：读取桌面某个 `.md` 文件内容（按文件名读取，可截断）

当前桌面路径写死为：`/home/standard/桌面`（Ubuntu）。

## 1) 直接验证工具是否正确

```bash
python -c "from txt_counter import count_desktop_txt_files, list_desktop_txt_files; print(count_desktop_txt_files()); print(list_desktop_txt_files())"
```

（如果你要测 `.md` 工具，改成：）

```bash
python -c "from txt_counter import count_desktop_md_files, list_desktop_md_files; print(count_desktop_md_files()); print(list_desktop_md_files())"
```

## 2) 运行 MCP Client（按中文提问并自动调用工具）

交互模式：

```bash
uv run --with mcp python client.py
```

单次提问：

```bash
uv run --with mcp python client.py 我桌面有什么文件
```

你也可以直接问（会先读取再总结）：

```bash
uv run --with mcp python client.py 给我总结 设计模式.md 中有什么内容
```

说明：现在 client 会按“先列出（list）确认文件存在 -> 再读取（read） -> 再总结”的顺序工作。

## 2.1) 用 Qwen 大模型做“工具选择/路由”（必配）

`client.py` **只支持**用 **Qwen** 来决定该调用哪个 MCP 工具，因此必须配置 `QWEN_API_KEY`。

在 DashScope（OpenAI 兼容模式）下，设置环境变量：

```bash
export QWEN_API_KEY="你的key"
export QWEN_MODEL="qwen-plus"   # 可选：qwen-turbo / qwen-plus / qwen-max 等
# export QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"  # 可选，默认就是这个
```

然后照常运行：

```bash
uv run --with mcp python client.py 我桌面有什么工具
```

## 2.2) 把提问过程日志写入文件

```bash
export CLIENT_LOG_FILE="./client.log"
export CLIENT_LOG_LEVEL="INFO"   # 或 DEBUG
uv run --with mcp python client.py 给我总结 设计模式.md 中有什么内容
```

## 3) 关于你看到的 Proxy Session Token 报错

`mcp dev` 会启动 Inspector + Proxy，网页/GUI 连接 Proxy 时需要填写 **Session token**。
而 `client.py` 走 STDIO 直连，不需要 token。
