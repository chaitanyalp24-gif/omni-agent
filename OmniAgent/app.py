import streamlit as st
import os
import io
import time
from datetime import datetime
import pandas as pd

from agent import (
    WORKSPACE_DIR,
    VIDEOS_DIR,
    get_available_gemini_models,
    initialize_agent_model,
    web_search,
    execute_python_code,
    fs_list_files,
    fs_read_file,
    fs_write_file,
    fs_create_directory,
    fs_delete_path,
    fs_search_files,
    create_workspace_zip,
    generate_image_url,
    synthesize_ai_video,
    download_media_bytes,
    enhance_prompt_with_gemini
)

# Page Setup
st.set_page_config(
    page_title="OmniAgent OS | Autonomous AI Cloud Hub",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 800; color: #1E88E5; margin-bottom: 0px; }
    .sub-header { font-size: 1.05rem; color: #555; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# Session State Initialization
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content": "👋 Greetings! I am **OmniAgent OS**. I can research the live web, execute Python code, manage files, and generate high-resolution images & real MP4 videos."}
    ]
if "image_history" not in st.session_state:
    st.session_state.image_history = []
if "video_history" not in st.session_state:
    st.session_state.video_history = []

# ==========================================
# SIDEBAR: SETTINGS & DYNAMIC MODELS
# ==========================================
with st.sidebar:
    st.markdown("### ⚡ OmniAgent Control Core")
    
    env_api_key = os.getenv("GEMINI_API_KEY", "")
    api_key_input = st.text_input(
        "Google Gemini API Key:",
        value=env_api_key,
        type="password",
        help="Get your key at https://aistudio.google.com"
    )
    active_api_key = api_key_input.strip() if api_key_input else env_api_key

    # Dynamically fetch models valid for this specific key
    available_models = get_available_gemini_models(active_api_key)
    
    # Set smart default index
    default_idx = 0
    for target in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]:
        if target in available_models:
            default_idx = available_models.index(target)
            break

    model_choice = st.selectbox(
        "Active Gemini Model Tier:",
        available_models,
        index=default_idx
    )

    st.markdown("---")
    st.markdown("#### 📂 Workspace Telemetry")
    
    file_count = 0
    total_size = 0
    for root, dirs, files in os.walk(WORKSPACE_DIR):
        file_count += len(files)
        for f in files:
            fp = os.path.join(root, f)
            total_size += os.path.getsize(fp)

    col_s1, col_s2 = st.columns(2)
    col_s1.metric("Files", file_count)
    col_s2.metric("Size", f"{round(total_size / 1024, 1)} KB")

    zip_buffer = create_workspace_zip()
    st.download_button(
        label="📦 Export Workspace ZIP",
        data=zip_buffer,
        file_name=f"workspace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        mime="application/zip",
        use_container_width=True
    )

    if st.button("🗑️ Reset Workspace", use_container_width=True):
        for item in os.listdir(WORKSPACE_DIR):
            item_path = os.path.join(WORKSPACE_DIR, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        os.makedirs(VIDEOS_DIR, exist_ok=True)
        st.success("Workspace reset.")
        st.rerun()

    st.markdown("---")
    st.link_button("☕ Support Developer ($3)", "https://buymeacoffee.com", use_container_width=True)
    st.link_button("🚀 Upgrade to Pro", "https://stripe.com", use_container_width=True)

# Main Title
st.markdown("<div class='main-header'>🤖 OmniAgent OS</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Autonomous Agentic AI • Web Search • Sandbox Runner • OpenClaw File System • Image & MP4 Video Core</div>", unsafe_allow_html=True)

# Application Tabs
tab_chat, tab_code, tab_img, tab_video, tab_files = st.tabs([
    "💬 Autonomous Agent Chat",
    "💻 Code Studio & Runner",
    "🎨 AI Image Studio",
    "🎬 MP4 Video Core",
    "📂 OpenClaw Workspace"
])

# ==========================================
# TAB 1: AUTONOMOUS AGENT CHAT
# ==========================================
with tab_chat:
    st.caption("OmniAgent autonomously queries the live web, executes sandbox code, and manages workspace files.")
    
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_prompt = st.chat_input("Ask a question, request web research, or trigger code/file tasks...")

    if user_prompt:
        if not active_api_key:
            st.error("⚠️ Please provide a Gemini API Key in the sidebar.")
        else:
            st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                with st.spinner("🤖 OmniAgent is reasoning and orchestrating tools..."):
                    try:
                        agent_model, active_model_used = initialize_agent_model(active_api_key, model_choice)
                        chat = agent_model.start_chat(enable_automatic_function_calling=True)
                        
                        # Replay recent context safely
                        for past_msg in st.session_state.chat_messages[-6:-1]:
                            role_tag = "user" if past_msg["role"] == "user" else "model"
                            chat.history.append({"role": role_tag, "parts": [past_msg["content"]]})

                        response = chat.send_message(user_prompt)
                        response_text = response.text

                        message_placeholder.markdown(response_text)
                        st.session_state.chat_messages.append({"role": "assistant", "content": response_text})
                    except Exception as e:
                        err_msg = f"⚠️ **Agent Error:** {str(e)}"
                        message_placeholder.markdown(err_msg)
                        st.session_state.chat_messages.append({"role": "assistant", "content": err_msg})

# ==========================================
# TAB 2: CODE STUDIO & SANDBOX RUNNER
# ==========================================
with tab_code:
    st.subheader("💻 Interactive Code Studio & Python Sandbox")
    col_code_left, col_code_right = st.columns([1, 1])

    with col_code_left:
        st.markdown("##### 📝 Code Editor")
        default_py = '''import matplotlib.pyplot as plt
import numpy as np

# Generate sample visual data
x = np.linspace(0, 10, 100)
y = np.sin(x) * np.exp(-0.1 * x)

plt.figure(figsize=(8, 4))
plt.plot(x, y, label='Damped Wave', color='#1E88E5', lw=2.5)
plt.title('Autonomous Code Execution Waveform')
plt.xlabel('Time (s)')
plt.ylabel('Amplitude')
plt.grid(True, linestyle='--', alpha=0.5)
plt.legend()
plt.tight_layout()

print("Execution completed! Visualization rendered.")
'''
        code_input = st.text_area("Python Script", value=default_py, height=320, key="sandbox_code")

        c1, c2, c3 = st.columns([1, 1, 1])
        run_btn = c1.button("▶️ Run Code", use_container_width=True, type="primary")
        save_as_file = c2.text_input("Filename", value="script.py", label_visibility="collapsed")
        save_btn = c3.button("💾 Save File", use_container_width=True)

        if save_btn:
            res = fs_write_file(save_as_file, code_input)
            st.success(res)

    with col_code_right:
        st.markdown("##### 🖥️ Execution Console")
        if run_btn:
            with st.spinner("Running Python script in sandbox..."):
                exec_result = execute_python_code(code_input)
                
                if exec_result["stdout"]:
                    st.markdown("**Console Output:**")
                    st.code(exec_result["stdout"], language="text")
                
                if exec_result["stderr"]:
                    st.markdown("**Errors:**")
                    st.error(exec_result["stderr"])

                if exec_result["has_plots"]:
                    st.markdown("**Generated Visual Charts:**")
                    for fig in exec_result["plot_figures"]:
                        st.pyplot(fig)
        else:
            st.info("Click '▶️ Run Code' to execute Python in the isolated workspace.")

# ==========================================
# TAB 3: AI IMAGE STUDIO
# ==========================================
with tab_img:
    st.subheader("🎨 Generative AI Image Studio")
    img_col1, img_col2 = st.columns([1, 1])

    with img_col1:
        img_prompt_input = st.text_area("Image Prompt:", placeholder="e.g., A cybernetic astronaut exploring an illuminated bioluminescent cave, 8k, cinematic lighting", height=120)
        
        opt1, opt2, opt3 = st.columns(3)
        aspect = opt1.selectbox("Aspect Ratio", ["1:1 (Square)", "16:9 (Landscape)", "9:16 (Portrait)"])
        model_type = opt2.selectbox("Diffusion Model", ["flux", "turbo"])
        custom_seed = opt3.number_input("Seed (0 for random)", min_value=0, max_value=999999, value=0)

        dim_map = {
            "1:1 (Square)": (1024, 1024),
            "16:9 (Landscape)": (1280, 720),
            "9:16 (Portrait)": (720, 1280)
        }
        w, h = dim_map[aspect]

        b1, b2 = st.columns(2)
        enhance_btn = b1.button("✨ Enhance Prompt", use_container_width=True)
        generate_img_btn = b2.button("🎨 Render Artwork", type="primary", use_container_width=True)

        if enhance_btn:
            if img_prompt_input and active_api_key:
                with st.spinner("Refining prompt with Gemini..."):
                    enhanced = enhance_prompt_with_gemini(img_prompt_input, active_api_key, "image")
                    st.success("Prompt Enhanced!")
                    img_prompt_input = enhanced
                    st.text_area("Refined Prompt", value=enhanced, height=80)
            else:
                st.warning("Please provide a prompt and Gemini API Key.")

    with img_col2:
        if generate_img_btn and img_prompt_input:
            with st.spinner("Rendering artwork..."):
                seed_val = None if custom_seed == 0 else custom_seed
                image_url = generate_image_url(img_prompt_input, width=w, height=h, seed=seed_val, model=model_type)
                
                st.image(image_url, caption=f"Prompt: {img_prompt_input}", use_container_width=True)
                img_bytes = download_media_bytes(image_url)
                if img_bytes:
                    st.download_button(
                        "📥 Download Full-Res Image",
                        data=img_bytes,
                        file_name=f"art_{int(time.time())}.jpg",
                        mime="image/jpeg",
                        use_container_width=True
                    )
        else:
            st.info("Enter an image description and click 'Render Artwork'.")

# ==========================================
# TAB 4: REAL MP4 VIDEO CORE
# ==========================================
with tab_video:
    st.subheader("🎬 Generative MP4 Video Core")
    st.caption("Synthesizes genuine MP4 video files with dynamic cinematic camera trajectories.")

    vid_col1, vid_col2 = st.columns([1, 1])

    with vid_col1:
        vid_prompt_input = st.text_area("Video Concept Prompt:", placeholder="e.g., A futuristic flying supercar speeding through neon cyberpunk Tokyo in the rain, cinematic lighting", height=120)
        
        v_c1, v_c2, v_c3 = st.columns(3)
        v_motion = v_c1.selectbox("Camera Trajectory", ["Cinematic Zoom In", "Dynamic Pan Right", "Dramatic Tilt Up", "Orbital Pulse"])
        v_duration = v_c2.selectbox("Duration", [3, 4, 5], index=1)
        v_fps = v_c3.selectbox("Frame Rate", [24, 30], index=0)

        generate_vid_btn = st.button("🎬 Synthesize MP4 Video", type="primary", use_container_width=True)

    with vid_col2:
        if generate_vid_btn and vid_prompt_input:
            with st.spinner("🎬 Synthesizing multi-frame AI video sequence and compiling MP4..."):
                vid_path, vid_bytes = synthesize_ai_video(
                    prompt=vid_prompt_input,
                    motion_type=v_motion,
                    duration_seconds=v_duration,
                    fps=v_fps
                )
                
                if vid_bytes and vid_path:
                    st.success(f"✅ Real MP4 Video Generated and Saved: `{os.path.basename(vid_path)}`")
                    st.video(vid_bytes)
                    
                    st.download_button(
                        "📥 Download MP4 Video File",
                        data=vid_bytes,
                        file_name=os.path.basename(vid_path),
                        mime="video/mp4",
                        use_container_width=True
                    )
                else:
                    st.error("Video synthesis could not be completed. Please try again.")
        else:
            st.info("Enter your video prompt and click 'Synthesize MP4 Video' to create a real MP4 clip.")

# ==========================================
# TAB 5: OPENCLAW WORKSPACE FILE MANAGER
# ==========================================
with tab_files:
    st.subheader("📂 OpenClaw Workspace File Manager")
    st.caption(f"Active Workspace Root: `{WORKSPACE_DIR}`")

    f_action_col1, f_action_col2, f_action_col3 = st.columns([1, 1, 1])

    with f_action_col1:
        with st.expander("➕ Create New File"):
            new_fname = st.text_input("File Path/Name:", placeholder="notes.txt")
            new_fcontent = st.text_area("Initial Content:", height=100)
            if st.button("Create File", use_container_width=True):
                if new_fname:
                    res = fs_write_file(new_fname, new_fcontent)
                    st.success(res)
                    st.rerun()

    with f_action_col2:
        with st.expander("📁 Create New Folder"):
            new_dname = st.text_input("Folder Name:", placeholder="data")
            if st.button("Create Folder", use_container_width=True):
                if new_dname:
                    res = fs_create_directory(new_dname)
                    st.success(res)
                    st.rerun()

    with f_action_col3:
        with st.expander("📤 Upload File(s)"):
            uploaded_files = st.file_uploader("Upload to workspace", accept_multiple_files=True)
            if uploaded_files:
                for uf in uploaded_files:
                    target_dest = os.path.join(WORKSPACE_DIR, uf.name)
                    with open(target_dest, "wb") as f:
                        f.write(uf.getbuffer())
                st.success(f"Uploaded {len(uploaded_files)} file(s)!")
                st.rerun()

    st.markdown("---")

    browser_col, editor_col = st.columns([1, 2])

    with browser_col:
        st.markdown("##### 📁 Workspace Tree")
        file_tree_text = fs_list_files()
        st.text_area("Directory Tree", value=file_tree_text, height=260, disabled=True)

        all_files = []
        for r, _, fls in os.walk(WORKSPACE_DIR):
            for fl in fls:
                rel = os.path.relpath(os.path.join(r, fl), WORKSPACE_DIR)
                all_files.append(rel)

        selected_file = st.selectbox("Select File to View / Edit:", [""] + all_files)
        
        if selected_file:
            if st.button("🗑️ Delete Selected File", type="secondary", use_container_width=True):
                res = fs_delete_path(selected_file)
                st.warning(res)
                st.rerun()

    with editor_col:
        st.markdown("##### 📝 Live File Viewer & Editor")
        if selected_file:
            current_content = fs_read_file(selected_file)
            edited_content = st.text_area(
                f"Editing: {selected_file}",
                value=current_content,
                height=300
            )
            if st.button("💾 Save File Changes", type="primary", use_container_width=True):
                fs_write_file(selected_file, edited_content)
                st.success(f"File '{selected_file}' updated successfully!")
        else:
            st.info("Select a file from the dropdown on the left to read or edit.")

    with st.expander("🔍 Search in Workspace Files"):
        search_q = st.text_input("Enter keyword to search across all workspace files:")
        if search_q:
            results = fs_search_files(search_q)
            st.code(results, language="text")