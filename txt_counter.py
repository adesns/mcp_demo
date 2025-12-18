import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# 创建 MCP Server
mcp = FastMCP("桌面 TXT 文件统计器")

DESKTOP_PATH = Path("/home/standard/桌面")

def _safe_desktop_file(filename: str) -> Path:
    """
    将用户传入的文件名解析为桌面内的安全路径，避免路径穿越（../）。
    只允许读取 DESKTOP_PATH 下的文件。
    """
    name = (filename or "").strip()
    if not name:
        raise ValueError("filename 不能为空")
    # 只取文件名，防止用户传入子路径/绝对路径
    name = Path(name).name
    p = (DESKTOP_PATH / name).resolve()
    desktop = DESKTOP_PATH.resolve()
    if not str(p).startswith(str(desktop) + os.sep) and p != desktop:
        raise ValueError("非法路径：只能读取桌面目录下的文件")
    return p

@mcp.tool()
def count_desktop_md_files() -> int:
    """Count the number of .md files on the desktop."""
    desktop_path = DESKTOP_PATH

    # Count .txt files
    md_files = list(desktop_path.glob("*.md"))
    return len(md_files)

@mcp.tool()
def list_desktop_md_files() -> str:
    """Get a list of all .md filenames on the desktop."""
    desktop_path = DESKTOP_PATH

    # Get all .txt files
    md_files = list(desktop_path.glob("*.md"))

    # Return the filenames
    if not md_files:
        return f"桌面（{desktop_path}）没有找到 .md 文件。"

    # Format the list of filenames
    file_list = "\n".join([f"- {file.name}" for file in md_files])
    return f"桌面（{desktop_path}）找到 {len(md_files)} 个 .md 文件：\n{file_list}"

@mcp.tool()
def read_desktop_md_file(filename: str, max_chars: int = 20000) -> str:
    """Read a .md file content from desktop by filename (supports truncation)."""
    p = _safe_desktop_file(filename)
    if p.suffix.lower() != ".md":
        raise ValueError("只能读取 .md 文件")
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{p}")

    text = p.read_text(encoding="utf-8", errors="replace")
    if max_chars is not None and max_chars > 0 and len(text) > max_chars:
        return text[:max_chars] + f"\n\n[内容过长，已截断：仅返回前 {max_chars} 字符]"
    return text

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run()
