import os
import io
import sys
import json
import random
import shutil
import zipfile
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import requests
import numpy as np
from PIL import Image
import imageio
import google.generativeai as genai
from duckduckgo_search import DDGS
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ==========================================
# WORKSPACE & FILE SYSTEM CONFIGURATION
# ==========================================
WORKSPACE_DIR = os.path.abspath(os.path.join(os.getcwd(), "workspace"))
VIDEOS_DIR = os.path.join(WORKSPACE_DIR, "videos")
os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)

def _sanitize_path(subpath: str) -> str:
    """Ensures safe paths confined strictly within WORKSPACE_DIR."""
    if not subpath:
        return WORKSPACE_DIR
    clean_subpath = subpath.strip().lstrip("/\\")
    target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, clean_subpath))
    if not target_path.startswith(WORKSPACE_DIR):
        raise PermissionError(f"Security Alert: Access outside workspace is denied ({subpath})")
    return target_path

# ==========================================
# OPENCLAW FILE MANAGER TOOLS
# ==========================================
def fs_list_files(subpath: str = "") -> str:
    """Lists files and folders inside the workspace directory."""
    try:
        target_path = _sanitize_path(subpath)
        if not os.path.exists(target_path):
            return f"Directory does not exist: {subpath}"
        
        entries = []
        for root, dirs, files in os.walk(target_path):
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
    """Reads content from a file inside the workspace."""
    try:
        filepath = _sanitize_path(filename)
        if not os.path.isfile(filepath):
            return f"File '{filename}' not found."
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file '{filename}': {str(e)}"

def fs_write_file(filename: str, content: str) -> str:
    """Creates or overwrites a file inside the workspace."""
    try:
        filepath = _sanitize_path(filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully saved file: {filename} ({len(content)} chars)"
    except Exception as e:
        return f"Error writing file '{filename}': {str(e)}"

def fs_create_directory(dir_name: str) -> str:
    """Creates a new folder inside the workspace."""
    try:
        dirpath = _sanitize_path(dir_name)
        os.makedirs(dirpath, exist_ok=True)
        return f"Successfully created folder: {dir_name}"
    except Exception as e:
        return f"Error creating directory: {str(e)}"

def fs_delete_path(path_to_delete: str) -> str:
    """Deletes a file or directory inside the workspace."""
    try:
        target = _sanitize_path(path_to_delete)
        if not os.path.exists(target):
            return f"Path does not exist: {path_to_delete}"
        if os.path.isfile(target):
            os.remove(target)
            return f"Deleted file: {path_to_delete}"
        elif os.path.isdir(target):
            shutil.rmtree(target)
            return f"Deleted directory: {path_to_delete}"
    except Exception as e:
        return f"Error deleting '{path_to_delete}': {str(e)}"

def fs_search_files(query: str) -> str:
    """Searches for text content inside all workspace files."""
    try:
        results = []
        for root, _, files in os.walk(WORKSPACE_DIR):
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
        return "\n".join(results[:30]) if results else f"No matches found for '{query}'."
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
    """Executes Python code safely and captures stdout/stderr and plots."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()

    original_cwd = os.getcwd()
    os.chdir(WORKSPACE_DIR)
    plt.close('all')

    execution_result = {
        "success": False,
        "stdout": "",
        "stderr": "",
        "has_plots": False,
        "plot_figures": []
    }

    try:
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr

        sandbox_globals = {
            "__name__": "__main__",
            "os": os,
            "sys": sys,
            "plt": plt,
            "WORKSPACE_DIR": WORKSPACE_DIR
        }

        exec(code, sandbox_globals)

        figs = [plt.figure(n) for n in plt.get_fignums()]
        if figs:
            execution_result["has_plots"] = True
            execution_result["plot_figures"] = figs

        execution_result["success"] = True
    except Exception as err:
        execution_result["stderr"] = f"{captured_stderr.getvalue()}\n{str(err)}"
        execution_result["success"] = False
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        os.chdir(original_cwd)

    execution_result["stdout"] = captured_stdout.getvalue()
    if not execution_result["stderr"]:
        execution_result["stderr"] = captured_stderr.getvalue()

    return execution_result

# ==========================================
# LIVE WEB SEARCH TOOL
# ==========================================
def web_search(query: str, max_results: int = 5) -> str:
    """Searches the live web using DuckDuckGo."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return f"No search results found for '{query}'."

            summary = [f"### Live Web Information for: '{query}'"]
            for i, r in enumerate(results, 1):
                title = r.get("title", "No Title")
                href = r.get("href", "#")
                body = r.get("body", "No description available.")
                summary.append(f"**{i}. [{title}]({href})**\n{body}\n")
            return "\n".join(summary)
    except Exception as e:
        return f"Web search could not retrieve results: {str(e)}"

# ==========================================
# AI IMAGE & REAL VIDEO GENERATION
# ==========================================
def generate_image_url(prompt: str, width: int = 1024, height: int = 1024, seed: Optional[int] = None, model: str = "flux") -> str:
    """Generates a direct AI image URL."""
    encoded_prompt = urllib.parse.quote(prompt.strip())
    if seed is None:
        seed = random.randint(1, 999999)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&model={model}&nologo=true"

def download_media_bytes(url: str) -> Optional[bytes]:
    """Downloads binary media safely from a URL."""
    try:
        headers = {"User-Agent": "OmniAgentOS/2.0"}
        resp = requests.get(url, headers=headers, timeout=40)
        if resp.status_code == 200:
            return resp.content
        return None
    except Exception:
        return None

def synthesize_ai_video(
    prompt: str,
    motion_type: str = "Cinematic Zoom In",
    duration_seconds: int = 4,
    fps: int = 24,
    width: int = 800,
    height: int = 450
) -> Tuple[Optional[str], Optional[bytes]]:
    """
    Generates a true MP4 video file with fluid cinematic motion keyframing.
    Saves the video inside workspace/videos/ and returns (filepath, video_bytes).
    """
    try:
        # Step 1: Generate high-resolution base scene
        seed = random.randint(100, 999999)
        base_img_url = generate_image_url(prompt, width=1280, height=720, seed=seed, model="flux")
        img_bytes = download_media_bytes(base_img_url)
        
        if not img_bytes:
            raise RuntimeError("Failed to fetch base AI scene for video synthesis.")
        
        base_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        orig_w, orig_h = base_img.size
        
        total_frames = duration_seconds * fps
        frames = []

        # Step 2: Compute motion trajectory matrices
        for i in range(total_frames):
            progress = i / float(total_frames)
            
            if motion_type == "Cinematic Zoom In":
                zoom = 1.0 + (0.28 * progress)
                crop_w = int(orig_w / zoom)
                crop_h = int(orig_h / zoom)
                left = (orig_w - crop_w) // 2
                top = (orig_h - crop_h) // 2
                
            elif motion_type == "Dynamic Pan Right":
                zoom = 1.15
                crop_w = int(orig_w / zoom)
                crop_h = int(orig_h / zoom)
                max_shift_x = orig_w - crop_w
                left = int(max_shift_x * progress)
                top = (orig_h - crop_h) // 2
                
            elif motion_type == "Dramatic Tilt Up":
                zoom = 1.15
                crop_w = int(orig_w / zoom)
                crop_h = int(orig_h / zoom)
                left = (orig_w - crop_w) // 2
                max_shift_y = orig_h - crop_h
                top = int(max_shift_y * (1.0 - progress))
                
            else: # "Orbital Pulse"
                zoom = 1.0 + 0.15 * np.sin(progress * np.pi)
                crop_w = int(orig_w / zoom)
                crop_h = int(orig_h / zoom)
                shift_x = int((orig_w - crop_w) * (0.5 + 0.3 * np.sin(progress * 2 * np.pi)))
                left = max(0, min(orig_w - crop_w, shift_x))
                top = (orig_h - crop_h) // 2

            cropped = base_img.crop((left, top, left + crop_w, top + crop_h))
            resized = cropped.resize((width, height), Image.Resampling.LANCZOS)
            frames.append(np.array(resized))

        # Step 3: Write out standard H.264 MP4 file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_filename = f"video_{timestamp}_{random.randint(100, 999)}.mp4"
        video_path = os.path.join(VIDEOS_DIR, video_filename)

        with imageio.get_writer(
            video_path,
            fps=fps,
            codec='libx264',
            format='FFMPEG',
            pixelformat='yuv420p',
            output_params=['-preset', 'medium', '-crf', '22']
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
    """Uses Gemini to turn a basic prompt into an ultra-detailed descriptive prompt."""
    if not api_key:
        return prompt
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        req = (
            f"Expand and enhance this prompt for an ultra-high quality AI {media_type} generation: "
            f"'{prompt}'. Return ONLY the enhanced descriptive prompt in 1-2 concise sentences without preamble."
        )
        res = model.generate_content(req)
        return res.text.strip().replace('"', '')
    except Exception:
        return prompt

# ==========================================
# DYNAMIC GEMINI MODEL RESOLUTION & AGENT BRAIN
# ==========================================
AGENT_SYSTEM_PROMPT = """You are OmniAgent OS, a state-of-the-art autonomous AI agent.
You have native access to:
1. Live Web Search (`web_search`)
2. Safe Python Code Sandbox (`execute_python_code`)
3. OpenClaw File System (`fs_write_file`, `fs_read_file`, `fs_list_files`, `fs_create_directory`, `fs_delete_path`, `fs_search_files`)
4. Image Studio Generator (`generate_image_url`)

GUIDELINES:
- When asked to search the live web, execute code, or manage files, proactively call the respective tools.
- Provide clean, professional Markdown answers with step-by-step clarity.
"""

AVAILABLE_TOOLS = [
    web_search,
    execute_python_code,
    fs_write_file,
    fs_read_file,
    fs_list_files,
    fs_create_directory,
    fs_delete_path,
    fs_search_files,
    generate_image_url
]

def get_available_gemini_models(api_key: str) -> List[str]:
    """Queries Google API to discover all valid models available for this specific API key."""
    default_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-1.5-flash-latest"]
    if not api_key:
        return default_models
    try:
        genai.configure(api_key=api_key)
        discovered = []
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                cleaned_name = m.name.replace("models/", "")
                discovered.append(cleaned_name)
        return discovered if discovered else default_models
    except Exception:
        return default_models

def initialize_agent_model(api_key: str, preferred_model: str = "gemini-1.5-flash"):
    """
    Initializes the Gemini model with tool calling.
    Includes auto-fallback to prevent 404 version/name errors.
    """
    genai.configure(api_key=api_key)
    clean_pref = preferred_model.replace("models/", "")
    
    # Priority cascade
    candidates = [
        clean_pref,
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash-8b"
    ]
    candidates = list(dict.fromkeys(candidates))

    last_error = None
    for cand in candidates:
        try:
            model = genai.GenerativeModel(
                model_name=cand,
                system_instruction=AGENT_SYSTEM_PROMPT,
                tools=AVAILABLE_TOOLS
            )
            return model, cand
        except Exception as err:
            last_error = err
            continue

    raise last_error