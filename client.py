import json
import os
import sys
import logging
from pathlib import Path

import anyio
import httpx
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


logger = logging.getLogger("txt_counter_client")


def _setup_logging() -> None:
    """
    日志开关：
    - CLIENT_LOG_LEVEL: DEBUG / INFO / WARNING / ERROR（默认 INFO）
    - CLIENT_LOG_FILE:  写入日志文件路径（例如：/tmp/client.log 或 ./client.log）
    - CLIENT_LOG_STDERR: 是否同时输出到终端(stderr)，默认 true（true/false/1/0）
    """
    def _truthy(v: str | None, default: bool = True) -> bool:
        if v is None:
            return default
        return v.strip().lower() in ("1", "true", "yes", "y", "on")

    level_name = (os.getenv("CLIENT_LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_file = os.getenv("CLIENT_LOG_FILE")
    to_stderr = _truthy(os.getenv("CLIENT_LOG_STDERR"), default=True)

    # 防止重复添加 handlers（多次调用 anyio.run / 交互模式）
    if getattr(logger, "_configured", False):  # type: ignore[attr-defined]
        logger.setLevel(level)
        return

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    if to_stderr:
        sh = logging.StreamHandler(stream=sys.stderr)
        sh.setFormatter(formatter)
        logger.addHandler(sh)

    if log_file:
        try:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except OSError as e:
            if to_stderr:
                logger.warning("无法写入日志文件 %s：%s（已退回仅输出到终端）", log_file, e)

    logger.setLevel(level)
    setattr(logger, "_configured", True)  # type: ignore[attr-defined]


def _preview(text: str, limit: int = 300) -> str:
    t = (text or "").replace("\r\n", "\n")
    if len(t) <= limit:
        return t
    return t[:limit] + f"...（已截断，原长度={len(t)}）"


def _format_user_error(err: BaseException) -> str:
    """
    anyio/mcp 里经常会把异常包在 ExceptionGroup 里，这里做一个“给人看的”错误消息。
    """
    # Python 3.11+: ExceptionGroup / BaseExceptionGroup
    if isinstance(err, BaseExceptionGroup):  # type: ignore[name-defined]
        # 取第一个子异常作为展示
        if err.exceptions:
            return _format_user_error(err.exceptions[0])
        return str(err)
    return str(err)


def _get_qwen_config() -> tuple[str | None, str, str]:
    """
    Qwen（OpenAI 兼容接口）配置：
    - QWEN_API_KEY: 必填（不填则不启用大模型路由）
    - QWEN_MODEL:  默认 qwen-plus
    - QWEN_BASE_URL: 默认 DashScope compatible-mode endpoint
    """
    api_key = os.getenv("QWEN_API_KEY")
    model = os.getenv("QWEN_MODEL") or "qwen-plus"
    base_url = os.getenv("QWEN_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    return api_key, model, base_url.rstrip("/")

async def _qwen_chat(messages: list[dict]) -> str:
    api_key, model, base_url = _get_qwen_config()
    if not api_key:
        raise RuntimeError(
            "未配置 QWEN_API_KEY：client.py 现在只支持使用 Qwen。\n"
            '请先执行：export QWEN_API_KEY="你的key"'
        )

    logger.info("Qwen 请求：model=%s base_url=%s messages=%d", model, base_url, len(messages))
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    content = (((data or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    content_str = str(content).strip()
    logger.debug("Qwen 原始返回预览：%s", _preview(content_str, 500))
    return content_str


async def _decide_with_qwen(question: str, *, tools: list[dict]) -> dict:
    """
    让 Qwen 决定下一步：
    - 调用工具（call_tool）
    - 直接回答（final）
    输出必须是严格 JSON：
      {"action":"call_tool","tool":"...","arguments":{}} 或 {"action":"final","answer":"..."}
    """
    system = (
        "你是一个带工具的助手。你可以先调用工具获取信息，再回答用户。\n"
        "只输出严格 JSON，不要输出多余文字。\n"
        "你必须在下面两种 JSON 之一中选择输出：\n"
        '1) {"action":"call_tool","tool":"工具名","arguments":{}}\n'
        '2) {"action":"final","answer":"你的回答"}\n'
        "可用工具：\n"
        + "\n".join([f"- {t.get('name')}: {t.get('description','')}".rstrip() for t in tools])
    )
    content = await _qwen_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]
    )
    try:
        obj = json.loads(content or "{}")
    except json.JSONDecodeError:
        raise RuntimeError(f"Qwen 返回内容不是严格 JSON，无法执行。\n原始返回：{content}")

    if not isinstance(obj, dict):
        raise RuntimeError(f"Qwen 返回的 JSON 不是对象：{content}")

    logger.info("Qwen 决策：%s", obj)
    return obj


def _extract_text(result) -> str:
    """
    CallToolResult 的内容通常在 content 里（TextContent），这里做个兼容提取。
    """
    parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if isinstance(text, str) and text:
            parts.append(text)
    if parts:
        return "\n".join(parts)
    # 兜底：直接字符串化
    return str(result)


async def _ask(question: str) -> str:
    _setup_logging()
    logger.info("用户问题：%s", question)
    server_py = Path(__file__).with_name("txt_counter.py")
    params = StdioServerParameters(command=sys.executable, args=[str(server_py)])

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # 先拿到工具列表
            tools_result = await session.list_tools()
            tools_for_llm = [{"name": t.name, "description": t.description or ""} for t in tools_result.tools]
            allowed = {t.name for t in tools_result.tools}
            logger.info("MCP 可用工具：%s", [t["name"] for t in tools_for_llm])

            # 多步：允许同一问题连续调用多个工具，直到模型输出 final
            MAX_STEPS = 6
            transcript: list[dict] = []

            for _step in range(MAX_STEPS):
                logger.info("==== step %d/%d ====", _step + 1, MAX_STEPS)
                decision = await _decide_with_qwen(question, tools=tools_for_llm)
                action = (decision.get("action") or "").strip()

                if action == "final":
                    answer = decision.get("answer")
                    if isinstance(answer, str) and answer.strip():
                        logger.info("最终回答生成完成（长度=%d）", len(answer.strip()))
                        return answer.strip()
                    raise RuntimeError("Qwen 返回了 action=final 但没有给出 answer。")

                if action != "call_tool":
                    raise RuntimeError(f'Qwen 返回的 action 非法：{action}（原始：{decision}）')

                tool = (decision.get("tool") or "").strip()
                arguments = decision.get("arguments") or {}
                if not isinstance(arguments, dict):
                    arguments = {}

                if tool not in allowed:
                    names = "\n".join([f"- {t.name}: {t.description or ''}".rstrip() for t in tools_result.tools])
                    raise RuntimeError(f"Qwen 返回了不存在的工具名：{tool}\n当前可用工具：\n{names}")

                logger.info("调用工具：%s arguments=%s", tool, arguments)
                tool_result = await session.call_tool(tool, arguments=arguments)
                tool_text = _extract_text(tool_result)
                logger.info("工具返回：len=%d preview=%s", len(tool_text), _preview(tool_text, 200))

                # 把每一步的工具结果累积进对话，让模型决定下一步（read / final / etc）
                transcript.append(
                    {
                        "role": "user",
                        "content": f"工具调用：{tool}\narguments：{arguments}\n工具结果：\n{tool_text}",
                    }
                )

                # 让模型看到“历史工具结果”
                # 这里通过把 transcript 拼到 question 后面，维持当前 _decide_with_qwen 的简单接口
                question = question + "\n\n" + "\n\n".join([m["content"] for m in transcript])

            raise RuntimeError(f"超过最大工具调用步数（{MAX_STEPS}），仍未得到最终回答。")


async def _interactive() -> None:
    print("MCP Client（输入问题，比如：我桌面有什么文件 / 桌面有多少 md；输入 exit 退出）")
    while True:
        q = input("> ").strip()
        if q.lower() in ("exit", "quit", "q"):
            return
        try:
            ans = await _ask(q)
            print(ans)
        except KeyboardInterrupt:
            return
        except Exception as e:
            print(_format_user_error(e))
            return


def main() -> None:
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:]).strip()
        try:
            print(anyio.run(_ask, question))
        except Exception as e:
            print(_format_user_error(e))
            raise SystemExit(1)
    else:
        try:
            anyio.run(_interactive)
        except Exception as e:
            print(_format_user_error(e))
            raise SystemExit(1)


if __name__ == "__main__":
    main()


