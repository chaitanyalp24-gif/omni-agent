import os
import io
import sys
import json
import random
import shutil
import zipfile
import urllib.parse
import re
import platform
import subprocess
import shlex
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import requests
import numpy as np
from PIL import Image
import imageio
import google.generativeai as genai
from duckduckgo_search import DDGS
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ==========================================
# WORKSPACE & FILE SYSTEM CONFIGURATION
# ==========================================
WORKSPACE_DIR = os.path.abspath(os.path.join(os.getcwd(), "workspace"))
VIDEOS_DIR = os.path.join(WORKSPACE_DIR, "videos")
os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)


def _sanitize_path(subpath: str) -> str:
    """Ensures paths remain strictly inside WORKSPACE_DIR."""
    if not subpath:
        return WORKSPACE_DIR
    clean_subpath = str(subpath).strip().lstrip("/\\")
    target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, clean_subpath))
    workspace_prefix = WORKSPACE_DIR if WORKSPACE_DIR.endswith(os.sep) else WORKSPACE_DIR + os.sep
    if target_path != WORKSPACE_DIR and not target_path.startswith(workspace_prefix):
        raise PermissionError(f"Security Alert: Access outside workspace is denied ({subpath})")
    return target_path


# ==========================================
# OPENCLAW-STYLE FILE / WORK TOOLS
# ==========================================
def fs_list_files(subpath: str = "") -> str:
    """Lists files and folders recursively inside the workspace."""
    try:
        target_path = _sanitize_path(subpath)
        if not os.path.exists(target_path):
            return f"Directory does not exist: {subpath}"

        entries = []
        for root, dirs, files in os.walk(target_path):
            dirs.sort()
            files.sort()
            rel_root = os.path.relpath(root, WORKSPACE_DIR)
            rel_root = "" if rel_root == "." else rel_root
            for d in dirs:
                entries.append(f"📁 [DIR]  {os.path.join(rel_root, d)}")
            for f in files:
                fpath = os.path.join(root, f)
                size_kb = round(os.path.getsize(fpath) / 1024, 2)
                entries.append(f"📄 [FILE] {os.path.join(rel_root, f)} ({size_kb} KB)")

        return "\n".join(entries) if entries else "Workspace directory is empty."
    except Exception as e:
        return f"Error listing workspace: {str(e)}"


def fs_read_file(filename: str) -> str:
    """Reads UTF-8 text from a workspace file."""
    try:
        filepath = _sanitize_path(filename)
        if not os.path.isfile(filepath):
            return f"File '{filename}' not found."
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file '{filename}': {str(e)}"


def fs_write_file(filename: str, content: str) -> str:
    """Creates or overwrites a text file inside the workspace."""
    try:
        filepath = _sanitize_path(filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully saved file: {filename} ({len(content)} chars)"
    except Exception as e:
        return f"Error writing file '{filename}': {str(e)}"


def fs_create_directory(dir_name: str) -> str:
    """Creates a workspace directory."""
    try:
        dirpath = _sanitize_path(dir_name)
        os.makedirs(dirpath, exist_ok=True)
        return f"Successfully created folder: {dir_name}"
    except Exception as e:
        return f"Error creating directory: {str(e)}"


def fs_delete_path(path_to_delete: str) -> str:
    """Deletes a workspace file or directory."""
    try:
        target = _sanitize_path(path_to_delete)
        if target == WORKSPACE_DIR:
            return "Refused to delete the workspace root."
        if not os.path.exists(target):
            return f"Path does not exist: {path_to_delete}"
        if os.path.isfile(target) or os.path.islink(target):
            os.remove(target)
            return f"Deleted file: {path_to_delete}"
        shutil.rmtree(target)
        return f"Deleted directory: {path_to_delete}"
    except Exception as e:
        return f"Error deleting '{path_to_delete}': {str(e)}"


def fs_copy_path(source: str, destination: str) -> str:
    """Copies a workspace file or directory."""
    try:
        src = _sanitize_path(source)
        dst = _sanitize_path(destination)
        if not os.path.exists(src):
            return f"Source does not exist: {source}"
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return f"Copied '{source}' -> '{destination}'"
    except Exception as e:
        return f"Error copying path: {str(e)}"


def fs_move_path(source: str, destination: str) -> str:
    """Moves/renames a workspace file or directory."""
    try:
        src = _sanitize_path(source)
        dst = _sanitize_path(destination)
        if not os.path.exists(src):
            return f"Source does not exist: {source}"
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return f"Moved '{source}' -> '{destination}'"
    except Exception as e:
        return f"Error moving path: {str(e)}"


def fs_path_exists(path: str) -> str:
    try:
        return json.dumps({"path": path, "exists": os.path.exists(_sanitize_path(path))})
    except Exception as e:
        return f"Path check failed: {e}"


def fs_search_files(query: str) -> str:
    """Searches text content inside workspace files."""
    try:
        results = []
        ignored_dirs = {".git", "__pycache__", "node_modules"}
        for root, dirs, files in os.walk(WORKSPACE_DIR):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                fpath = os.path.join(root, file)
                rel_path = os.path.relpath(fpath, WORKSPACE_DIR)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                results.append(f"{rel_path}:{line_no}: {line.strip()}")
                except Exception:
                    continue
        return "\n".join(results[:50]) if results else f"No matches found for '{query}'."
    except Exception as e:
        return f"Error searching files: {str(e)}"


def create_workspace_zip() -> io.BytesIO:
    """Compresses the workspace into an in-memory ZIP buffer."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(WORKSPACE_DIR):
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, WORKSPACE_DIR)
                zip_file.write(filepath, arcname)
    buf.seek(0)
    return buf


# ==========================================
# CODE EXECUTION SANDBOX
# ==========================================
def execute_python_code(code: str) -> Dict[str, Any]:
    """Executes Python code with cwd set to the workspace and captures stdout/stderr/plots."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    original_cwd = os.getcwd()

    os.chdir(WORKSPACE_DIR)
    plt.close("all")
    execution_result = {
        "success": False,
        "stdout": "",
        "stderr": "",
        "has_plots": False,
        "plot_figures": [],
    }

    try:
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr
        sandbox_globals = {
            "__name__": "__main__",
            "os": os,
            "sys": sys,
            "plt": plt,
            "np": np,
            "WORKSPACE_DIR": WORKSPACE_DIR,
        }
        exec(code, sandbox_globals)
        figs = [plt.figure(n) for n in plt.get_fignums()]
        if figs:
            execution_result["has_plots"] = True
            execution_result["plot_figures"] = figs
        execution_result["success"] = True
    except Exception as err:
        execution_result["stderr"] = f"{captured_stderr.getvalue()}\n{type(err).__name__}: {err}"
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        os.chdir(original_cwd)

    execution_result["stdout"] = captured_stdout.getvalue()
    if not execution_result["stderr"]:
        execution_result["stderr"] = captured_stderr.getvalue()
    return execution_result


# ==========================================
# OPENCLAW-STYLE COMPUTER / COMMAND TOOL
# ==========================================
ALLOWED_COMMANDS = {
    "python", "python3", "pip", "pip3", "git", "node", "npm", "npx",
    "ffmpeg", "ffprobe", "ls", "find", "grep", "cat", "pwd", "whoami",
    "which", "where", "echo", "dir"
}
BLOCKED_COMMAND_PATTERNS = [
    r"\brm\s+-rf\s+[/~]", r"\bmkfs\b", r"\bshutdown\b", r"\breboot\b",
    r"\bformat\b\s+[a-z]:", r"\bdel\b\s+/s\s+/q\s+[a-z]:", r"\bdd\s+if=",
    r"curl\s+[^\n]*\|\s*(ba|z)?sh", r"wget\s+[^\n]*\|\s*(ba|z)?sh"
]


def _validate_command(command: str) -> Tuple[bool, str]:
    text = command.strip()
    if not text:
        return False, "Command is empty."
    lowered = text.lower()
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, lowered):
            return False, "Command blocked by the workspace safety policy."
    try:
        parts = shlex.split(text, posix=(os.name != "nt"))
    except ValueError as e:
        return False, f"Command parsing failed: {e}"
    if not parts:
        return False, "Command is empty."
    exe = os.path.basename(parts[0]).lower()
    if exe.endswith(".exe"):
        exe = exe[:-4]
    if exe not in ALLOWED_COMMANDS:
        return False, f"Executable '{exe}' is not in the allowed workspace command list."
    # Block explicit parent traversal / obvious absolute paths in arguments.
    for arg in parts[1:]:
        if ".." in arg.replace("\\", "/").split("/"):
            return False, "Parent-directory traversal is not allowed."
        if os.path.isabs(arg) and not arg.startswith(WORKSPACE_DIR):
            return False, "Absolute paths outside the workspace are not allowed."
    return True, ""


def run_workspace_command(command: str, timeout_seconds: int = 60) -> str:
    """Runs an allowlisted command from the workspace directory."""
    ok, reason = _validate_command(command)
    if not ok:
        return f"COMMAND BLOCKED: {reason}"

    try:
        completed = subprocess.run(
            command,
            cwd=WORKSPACE_DIR,
            shell=True,
            capture_output=True,
            text=True,
            timeout=max(1, min(int(timeout_seconds), 180)),
            env={**os.environ, "OMNIAGENT_WORKSPACE": WORKSPACE_DIR},
        )
        stdout = completed.stdout[-12000:]
        stderr = completed.stderr[-12000:]
        return json.dumps({
            "command": command,
            "return_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "success": completed.returncode == 0,
        }, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"command": command, "success": False, "error": "Command timed out."})
    except Exception as e:
        return json.dumps({"command": command, "success": False, "error": str(e)})


def get_system_info() -> str:
    return json.dumps({
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cwd": os.getcwd(),
        "workspace": WORKSPACE_DIR,
    }, indent=2)


# ==========================================
# LIVE WEB SEARCH / FETCH (MULTI-FALLBACK)
# ==========================================
def _ddg_search(query: str, max_results: int) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with DDGS() as ddgs:
        try:
            for r in ddgs.text(query, max_results=max_results):
                rows.append({
                    "title": r.get("title", "Untitled"),
                    "url": r.get("href", r.get("url", "")),
                    "snippet": r.get("body", r.get("description", "")),
                    "source": "DuckDuckGo",
                })
        except Exception:
            pass
    return rows


def _ddg_news(query: str, max_results: int) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with DDGS() as ddgs:
        try:
            for r in ddgs.news(query, max_results=max_results):
                rows.append({
                    "title": r.get("title", "Untitled"),
                    "url": r.get("url", ""),
                    "snippet": r.get("body", ""),
                    "source": r.get("source", "DuckDuckGo News"),
                    "date": r.get("date", ""),
                })
        except Exception:
            pass
    return rows


def _google_news_rss(query: str, max_results: int) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    try:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 OmniAgentOS/3.0"}, timeout=15)
        resp.raise_for_status()
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)
        for item in root.findall(".//item")[:max_results]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "").strip()
            source = item.findtext("source") or "Google News"
            if title and link:
                rows.append({"title": title, "url": link, "snippet": desc, "source": source, "date": pub_date})
    except Exception:
        pass
    return rows


def _ddg_html(query: str, max_results: int) -> List[Dict[str, str]]:
    """HTML fallback for environments where DDGS API calls fail."""
    rows: List[Dict[str, str]] = []
    try:
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 OmniAgentOS/3.0"}, timeout=15)
        resp.raise_for_status()
        html = resp.text
        # Simple parser intentionally avoids an extra HTML dependency.
        pattern = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', re.S)
        for match in pattern.findall(html):
            href, title_html, snippet_html = match
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            snippet = re.sub(r"<[^>]+>", "", snippet_html).strip()
            rows.append({"title": title, "url": href, "snippet": snippet, "source": "DuckDuckGo HTML"})
            if len(rows) >= max_results:
                break
    except Exception:
        pass
    return rows


def web_search(query: str, max_results: int = 8) -> str:
    """Robust live web search with news + multiple fallback providers."""
    query = str(query).strip()
    if not query:
        return "WEB_SEARCH_ERROR: query is empty."

    is_news = bool(re.search(r"\b(latest|news|today|recent|breaking|headlines|update|updates)\b", query, re.I))
    collected: List[Dict[str, str]] = []

    # News-first route for time-sensitive questions.
    if is_news:
        collected.extend(_ddg_news(query, max_results))
        if len(collected) < max_results:
            collected.extend(_google_news_rss(query, max_results - len(collected)))

    if len(collected) < max_results:
        collected.extend(_ddg_search(query, max_results - len(collected)))
    if len(collected) < max_results:
        collected.extend(_ddg_html(query, max_results - len(collected)))

    # De-duplicate by URL/title.
    seen = set()
    deduped = []
    for item in collected:
        key = item.get("url") or item.get("title", "")
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)

    if not deduped:
        return (
            f"WEB_SEARCH_UNAVAILABLE: Live search providers returned no usable results for '{query}'. "
            "Do not invent current facts. Tell the user the web search was unavailable and offer a direct URL fetch if they provide one."
        )

    lines = [f"### LIVE WEB RESULTS: {query}"]
    for i, r in enumerate(deduped[:max_results], 1):
        date = f" | {r['date']}" if r.get("date") else ""
        lines.append(f"**{i}. {r['title']}**{date}\nURL: {r['url']}\nSource: {r.get('source', 'web')}\n{r.get('snippet', '')}")
    return "\n\n".join(lines)


def web_fetch(url: str, max_chars: int = 12000) -> str:
    """Fetches and extracts readable text from a URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return "WEB_FETCH_ERROR: only http/https URLs are allowed."
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 OmniAgentOS/3.0"}, timeout=20)
        resp.raise_for_status()
        text = resp.text
        # Strip scripts/styles/tags for a compact retrieval payload.
        text = re.sub(r"<(script|style|noscript).*?>.*?</\1>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text[:max_chars]
    except Exception as e:
        return f"WEB_FETCH_ERROR: {e}"


# ==========================================
# AI IMAGE & REAL VIDEO GENERATION
# ==========================================
def generate_image_url(prompt: str, width: int = 1024, height: int = 1024, seed: Optional[int] = None, model: str = "flux") -> str:
    encoded_prompt = urllib.parse.quote(prompt.strip())
    if seed is None:
        seed = random.randint(1, 999999)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&model={model}&nologo=true"


def download_media_bytes(url: str) -> Optional[bytes]:
    try:
        headers = {"User-Agent": "OmniAgentOS/3.0"}
        resp = requests.get(url, headers=headers, timeout=40)
        return resp.content if resp.status_code == 200 else None
    except Exception:
        return None


def synthesize_ai_video(
    prompt: str,
    motion_type: str = "Cinematic Zoom In",
    duration_seconds: int = 4,
    fps: int = 24,
    width: int = 800,
    height: int = 450,
) -> Tuple[Optional[str], Optional[bytes]]:
    """Generates a genuine MP4 from an AI-generated base frame + camera motion."""
    try:
        seed = random.randint(100, 999999)
        base_img_url = generate_image_url(prompt, width=1280, height=720, seed=seed, model="flux")
        img_bytes = download_media_bytes(base_img_url)
        if not img_bytes:
            raise RuntimeError("Failed to fetch base AI scene for video synthesis.")

        base_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        orig_w, orig_h = base_img.size
        total_frames = max(1, int(duration_seconds * fps))
        frames = []

        for i in range(total_frames):
            progress = i / float(max(1, total_frames - 1))
            if motion_type == "Cinematic Zoom In":
                zoom = 1.0 + (0.28 * progress)
                crop_w, crop_h = int(orig_w / zoom), int(orig_h / zoom)
                left, top = (orig_w - crop_w) // 2, (orig_h - crop_h) // 2
            elif motion_type == "Dynamic Pan Right":
                zoom = 1.15
                crop_w, crop_h = int(orig_w / zoom), int(orig_h / zoom)
                max_shift_x = orig_w - crop_w
                left = int(max_shift_x * progress)
                top = (orig_h - crop_h) // 2
            elif motion_type == "Dramatic Tilt Up":
                zoom = 1.15
                crop_w, crop_h = int(orig_w / zoom), int(orig_h / zoom)
                left = (orig_w - crop_w) // 2
                max_shift_y = orig_h - crop_h
                top = int(max_shift_y * (1.0 - progress))
            else:
                zoom = 1.0 + 0.15 * np.sin(progress * np.pi)
                crop_w, crop_h = int(orig_w / zoom), int(orig_h / zoom)
                shift_x = int((orig_w - crop_w) * (0.5 + 0.3 * np.sin(progress * 2 * np.pi)))
                left = max(0, min(orig_w - crop_w, shift_x))
                top = (orig_h - crop_h) // 2

            cropped = base_img.crop((left, top, left + crop_w, top + crop_h))
            frames.append(np.array(cropped.resize((width, height), Image.Resampling.LANCZOS)))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_filename = f"video_{timestamp}_{random.randint(100, 999)}.mp4"
        video_path = os.path.join(VIDEOS_DIR, video_filename)
        with imageio.get_writer(
            video_path,
            fps=fps,
            codec="libx264",
            format="FFMPEG",
            pixelformat="yuv420p",
            output_params=["-preset", "medium", "-crf", "22"],
        ) as writer:
            for frame in frames:
                writer.append_data(frame)

        with open(video_path, "rb") as vf:
            video_bytes = vf.read()
        return video_path, video_bytes
    except Exception as e:
        print(f"Video synthesis error: {e}")
        return None, None


def enhance_prompt_with_gemini(prompt: str, api_key: str, media_type: str = "image") -> str:
    if not api_key:
        return prompt
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        req = (
            f"Expand and enhance this prompt for ultra-high quality AI {media_type} generation: "
            f"'{prompt}'. Return ONLY the enhanced descriptive prompt in 1-2 concise sentences without preamble."
        )
        res = model.generate_content(req)
        return res.text.strip().replace('"', "")
    except Exception:
        return prompt


# ==========================================
# VOICE INPUT / TRANSCRIPTION
# ==========================================
def transcribe_audio_bytes(audio_bytes: bytes, api_key: str, mime_type: str = "audio/wav") -> str:
    """Transcribes browser-recorded audio through Gemini. No separate speech API key is required."""
    if not audio_bytes:
        return ""
    if not api_key:
        raise RuntimeError("Gemini API key is required for voice transcription.")
    genai.configure(api_key=api_key)
    candidates = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]
    last_error = None
    for model_name in candidates:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([
                "Transcribe the user's speech exactly. Return only the transcript, with no commentary.",
                {"mime_type": mime_type, "data": audio_bytes},
            ])
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Voice transcription failed: {last_error}")



# ==========================================
# MULTI-PROVIDER MODEL ROUTER
# ==========================================
OMNIAGENT_VERSION = "4.1"

AGENT_SYSTEM_PROMPT = """
You are OmniAgent OS 4, an autonomous AI work assistant.

You can:
1. Research the live web and fetch pages.
2. Execute Python in the workspace.
3. Create, read, edit, search, copy, move and delete workspace files.
4. Run allowlisted development commands inside the workspace.
5. Inspect runtime information.
6. Generate images and MP4 video scenes.

OPERATING RULES:
- Act, don't just explain. When the user asks you to build, edit, test, research, organize, calculate or create something, use the relevant tools proactively.
- You may chain multiple tools: inspect -> edit -> test -> diagnose -> fix -> retest.
- For current/latest/news questions, use live web search before answering. Never invent current facts.
- When using fallback providers without native local tool execution, use supplied web/file context faithfully and do not pretend that a remote model executed local tools.
- If one model provider is unavailable, the application may route the request to another configured provider.
- Be concise but report what was actually done.
""".strip()

AVAILABLE_TOOLS = [
    web_search, web_fetch, execute_python_code,
    fs_write_file, fs_read_file, fs_list_files, fs_create_directory,
    fs_delete_path, fs_copy_path, fs_move_path, fs_path_exists,
    fs_search_files, run_workspace_command, get_system_info,
    generate_image_url,
]

DEFAULT_MODELS = {
    "Gemini": "gemini-2.5-flash",
    "Hugging Face": "meta-llama/Llama-3.2-3B-Instruct",
    "Groq": "openai/gpt-oss-120b",
    "OpenRouter": "openrouter/free",
    "Cohere": "command-a-plus-05-2026",
    "LM Studio": "local-model",
}

def is_provider_error(exc: Exception) -> bool:
    text = str(exc).lower()
    needles = [
        "429", "quota", "rate limit", "rate_limit", "resource exhausted",
        "too many requests", "unauthorized", "401", "403", "timeout",
        "temporarily unavailable", "service unavailable", "not found"
    ]
    return any(n in text for n in needles)

def safe_response_text(response) -> str:
    """Extract only text parts from a Gemini response. Never stringify a function_call part."""
    try:
        value = getattr(response, "text", None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    except Exception:
        pass

    texts = []
    try:
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                txt = getattr(part, "text", None)
                if isinstance(txt, str) and txt.strip():
                    texts.append(txt.strip())
    except Exception:
        pass
    return "\n\n".join(texts).strip()

def build_context_prompt(history, user_prompt, web_context=None):
    recent = history[-8:] if history else []
    lines = ["RECENT CONVERSATION:"]
    for m in recent:
        role = m.get("role", "user").upper()
        lines.append(f"{role}: {m.get('content', '')}")
    if web_context:
        lines.append("\nLIVE WEB CONTEXT:")
        lines.append(web_context)
    lines.append("\nCURRENT USER REQUEST:")
    lines.append(user_prompt)
    return "\n".join(lines)

def _http_json(url, headers, payload, timeout=45):
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code >= 400:
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:2000]
        raise RuntimeError(f"HTTP {resp.status_code}: {body}")
    return resp.json()

def call_hf(api_key, model, messages):
    try:
        from huggingface_hub import InferenceClient
    except Exception as exc:
        raise RuntimeError("huggingface_hub is not installed. Run pip install -r requirements.txt") from exc
    client = InferenceClient(api_key=api_key)
    out = client.chat.completions.create(model=model, messages=messages, max_tokens=2048)
    content = getattr(out.choices[0].message, "content", "") if out and out.choices else ""
    if isinstance(content, list):
        content = " ".join(
            str(x.get("text", "")) if isinstance(x, dict) else str(getattr(x, "text", ""))
            for x in content
        )
    return str(content or "").strip()

def call_groq(api_key, model, messages):
    data = _http_json(
        "https://api.groq.com/openai/v1/chat/completions",
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 2048},
    )
    return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()

def call_openrouter(api_key, model, messages):
    data = _http_json(
        "https://openrouter.ai/api/v1/chat/completions",
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://streamlit.io",
            "X-OpenRouter-Title": "OmniAgent OS",
        },
        {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 2048},
    )
    return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()

def call_cohere(api_key, model, messages):
    data = _http_json(
        "https://api.cohere.com/v2/chat",
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 2048},
    )
    content = data.get("message", {}).get("content", [])
    texts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            texts.append(item.get("text", ""))
    return "\n".join(texts).strip()

def call_lmstudio(base_url, model, messages):
    url = base_url.rstrip("/") + "/chat/completions"
    data = _http_json(
        url,
        {"Content-Type": "application/json"},
        {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 2048},
    )
    return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()

def get_available_gemini_models(api_key: str) -> List[str]:
    default_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    if not api_key:
        return default_models
    try:
        genai.configure(api_key=api_key)
        discovered = []
        for m in genai.list_models():
            methods = getattr(m, "supported_generation_methods", [])
            if "generateContent" in methods:
                discovered.append(m.name.replace("models/", ""))
        return discovered or default_models
    except Exception:
        return default_models

def initialize_agent_model(api_key: str, preferred_model: str = "gemini-2.5-flash"):
    if not api_key:
        raise ValueError("Gemini API key is missing.")
    genai.configure(api_key=api_key)
    candidates = list(dict.fromkeys([
        preferred_model.replace("models/", ""),
        "gemini-2.5-flash", "gemini-2.0-flash",
        "gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.5-flash-8b",
    ]))
    last_error = None
    for cand in candidates:
        try:
            model = genai.GenerativeModel(
                model_name=cand,
                system_instruction=AGENT_SYSTEM_PROMPT,
                tools=AVAILABLE_TOOLS,
            )
            return model, cand
        except Exception as err:
            last_error = err
    raise last_error or RuntimeError("No compatible Gemini model was found.")

def run_gemini_agent(api_key, model_name, history, user_prompt, web_context=""):
    model, active_model = initialize_agent_model(api_key, model_name)
    prompt = build_context_prompt(history, user_prompt, web_context)
    chat = model.start_chat(enable_automatic_function_calling=True)
    response = chat.send_message(prompt)
    text = safe_response_text(response)
    if text:
        return text, active_model
    # If the SDK surfaced only non-text parts, ask the same model for a clean final response.
    recovery = model.generate_content(
        "Return a concise final user-facing answer based on the completed work. "
        "Do not output tool-call objects or internal protocol.\n\n" + prompt
    )
    recovered = safe_response_text(recovery)
    if recovered:
        return recovered, active_model
    return "✅ Task completed. Check the workspace for generated files/results.", active_model

def run_text_provider(provider, api_key, model, history, user_prompt, web_context="", lmstudio_url="http://localhost:1234/v1"):
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    for m in (history or [])[-8:]:
        role = "assistant" if m.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": m.get("content", "")})
    if web_context:
        messages.append({
            "role": "system",
            "content": "Live web context retrieved by OmniAgent:\n" + web_context
        })
    messages.append({"role": "user", "content": user_prompt})

    if provider == "Hugging Face":
        return call_hf(api_key, model, messages), model
    if provider == "Groq":
        return call_groq(api_key, model, messages), model
    if provider == "OpenRouter":
        return call_openrouter(api_key, model, messages), model
    if provider == "Cohere":
        return call_cohere(api_key, model, messages), model
    if provider == "LM Studio":
        return call_lmstudio(lmstudio_url, model, messages), model
    raise ValueError(f"Unsupported provider: {provider}")

def choose_provider_chain(mode, keys):
    configured = {k for k, v in keys.items() if v}
    if mode == "Auto":
        order = ["Gemini", "Hugging Face", "Groq", "OpenRouter", "Cohere", "LM Studio"]
        return [p for p in order if p in configured]
    return [mode] if mode == "LM Studio" or mode in configured else []

def transcribe_audio_bytes(audio_bytes: bytes, api_key: str = "", mime_type: str = "audio/wav",
                           hf_token: str = "", provider_mode: str = "Auto",
                           hf_model: str = "openai/whisper-large-v3-turbo") -> str:
    """Transcribe audio with Gemini first, then Hugging Face ASR fallback."""
    if not audio_bytes:
        return ""
    errors = []
    if api_key and provider_mode in {"Auto", "Gemini"}:
        try:
            genai.configure(api_key=api_key)
            for model_name in ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content([
                        "Transcribe the user's speech exactly. Return only the transcript.",
                        {"mime_type": mime_type, "data": audio_bytes},
                    ])
                    text = safe_response_text(response)
                    if text:
                        return text
                except Exception as exc:
                    errors.append(str(exc))
        except Exception as exc:
            errors.append(str(exc))

    if hf_token and provider_mode in {"Auto", "Hugging Face"}:
        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(api_key=hf_token)
            result = client.automatic_speech_recognition(audio_bytes, model=hf_model)
            text = getattr(result, "text", "") or ""
            if text.strip():
                return text.strip()
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError("Voice transcription failed. " + " | ".join(errors[-3:]))

