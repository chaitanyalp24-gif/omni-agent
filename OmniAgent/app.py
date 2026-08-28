import streamlit as st
import os
import io
import time
from datetime import datetime
import pandas as pd

from agent import (
    WORKSPACE_DIR,
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
    generate_video_url,
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

# Custom Styling
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 800; color: #1E88E5; margin-bottom: 0px; }
    .sub-header { font-size: 1.05rem; color: #555; margin-bottom: 20px; }
    .metric-card { background: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 8px; padding: 15px; }
    .stCodeBlock { border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content": "👋 Greetings! I am **OmniAgent OS**. I can research the web, write & run Python code, manage your workspace files, and generate images & motion videos. How can I help you today?"}
    ]
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "image_history" not in st.session_state:
    st.session_state.image_history = []

# ==========================================
# SIDEBAR: SETTINGS & WORKSPACE STATUS
# ==========================================
with st.sidebar:
    st.markdown("### ⚡ OmniAgent Control Core")
    
    # API Key Configuration
    env_api_key = os.getenv("GEMINI_API_KEY", "")
    api_key_input = st.text_input(
        "Google Gemini API Key:",
        value=env_api_key,
        type="password",
        help="Get a free key from https://aistudio.google.com"
    )
    active_api_key = api_key_input.strip() if api_key_input else env_api_key

    model_choice = st.selectbox(
        "LLM Brain Tier:",
        ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
        index=0
    )

    st.markdown("---")
    st.markdown("#### 📂 Workspace Live Telemetry")
    
    # Count files and folders
    file_count = 0
    folder_count = 0
    total_size = 0
    for root, dirs, files in os.walk(WORKSPACE_DIR):
        folder_count += len(dirs)
        file_count += len(files)
        for f in files:
            fp = os.path.join(root, f)
            total_size += os.path.getsize(fp)

    col_s1, col_s2 = st.columns(2)
    col_s1.metric("Files", file_count)
    col_s2.metric("Size", f"{round(total_size / 1024, 1)} KB")

    zip_buffer = create_workspace_zip()
    st.download_button(
        label="📦 Download Workspace ZIP",
        data=zip_buffer,
        file_name=f"workspace_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
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
        st.success("Workspace wiped clean.")
        st.rerun()

    st.markdown("---")
    st.markdown("#### 💳 Monetization & Pro Links")
    st.link_button("☕ Support Developer ($3)", "https://buymeacoffee.com", use_container_width=True)
    st.link_button("🚀 Upgrade to OmniAgent Pro", "https://stripe.com", use_container_width=True)

# Main Title Header
st.markdown("<div class='main-header'>🤖 OmniAgent OS</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Full-Stack Autonomous Agentic AI • Web Search • Code Runner • File Hub • Media Studio</div>", unsafe_allow_html=True)

# Application Tabs
tab_chat, tab_code, tab_img, tab_video, tab_files = st.tabs([
    "💬 Autonomous Agent Chat",
    "💻 Code Studio & Runner",
    "🎨 AI Image Studio",
    "🎬 Video & Motion Core",
    "📂 OpenClaw Workspace"
])

# ==========================================
# TAB 1: AUTONOMOUS AGENT CHAT
# ==========================================
with tab_chat:
    st.caption("OmniAgent can autonomously search the web, execute code in the sandbox, and create workspace files.")
    
    # Display Chat History
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input Box
    user_prompt = st.chat_input("Ask OmniAgent anything, e.g. 'Search for recent NASA discoveries and write a report to nasa_news.md'...")

    if user_prompt:
        if not active_api_key:
            st.error("⚠️ Please provide a valid Gemini API Key in the sidebar.")
        else:
            # Append User Message
            st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            # Generate Agent Response
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                with st.spinner("🤖 OmniAgent is reasoning and orchestrating tools..."):
                    try:
                        agent_model = initialize_agent_model(active_api_key, model_choice)
                        
                        # Enable Automatic Function Calling
                        chat = agent_model.start_chat(enable_automatic_function_calling=True)
                        
                        # Replay recent conversation context
                        for past_msg in st.session_state.chat_messages[-6:-1]:
                            if past_msg["role"] == "user":
                                chat.history.append({"role": "user", "parts": [past_msg["content"]]})
                            elif past_msg["role"] == "assistant":
                                chat.history.append({"role": "model", "parts": [past_msg["content"]]})

                        response = chat.send_message(user_prompt)
                        response_text = response.text

                        message_placeholder.markdown(response_text)
                        st.session_state.chat_messages.append({"role": "assistant", "content": response_text})
                    except Exception as e:
                        err_msg = f"⚠️ **Agent Error:** {str(e)}"
                        message_placeholder.markdown(err_msg)
                        st.session_state.chat_messages.append({"role": "assistant", "content": err_msg})

# ==========================================
# TAB 2: CODE STUDIO & SANDBOX EXECUTION
# ==========================================
with tab_code:
    st.subheader("💻 Interactive Code Studio & Python Sandbox")
    st.caption("Write, execute, and verify code live inside the isolated workspace sandbox environment.")

    col_code_left, col_code_right = st.columns([1, 1])

    with col_code_left:
        st.markdown("##### 📝 Code Editor")
        default_py = '''import matplotlib.pyplot as plt
import numpy as np

# Generate sample data
x = np.linspace(0, 10, 100)
y = np.sin(x)

# Create visualization
plt.figure(figsize=(8, 4))
plt.plot(x, y, label='Sine Wave', color='dodgerblue', lw=2)
plt.title('Autonomous Code Execution Plot')
plt.xlabel('X Axis')
plt.ylabel('Y Axis')
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend()
plt.tight_layout()

print("Execution finished successfully! Plot generated.")
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
        st.markdown("##### 🖥️ Execution Console & Visual Output")
        if run_btn:
            with st.spinner("Executing Python script in sandbox..."):
                exec_result = execute_python_code(code_input)
                
                if exec_result["stdout"]:
                    st.markdown("**Output (stdout):**")
                    st.code(exec_result["stdout"], language="text")
                
                if exec_result["stderr"]:
                    st.markdown("**Errors (stderr):**")
                    st.error(exec_result["stderr"])

                if exec_result["has_plots"]:
                    st.markdown("**Rendered Matplotlib Figures:**")
                    for fig in exec_result["plot_figures"]:
                        st.pyplot(fig)
        else:
            st.info("Click '▶️ Run Code' to execute the script and observe outputs here.")

# ==========================================
# TAB 3: AI IMAGE STUDIO
# ==========================================
with tab_img:
    st.subheader("🎨 Generative AI Image Studio")
    st.caption("Powered by high-detail diffusion models with automatic prompt enhancement.")

    img_col1, img_col2 = st.columns([1, 1])

    with img_col1:
        img_prompt_input = st.text_area("Image Prompt Description:", placeholder="e.g., A futuristic cyberpunk hacker lab with neon monitors, 8k resolution, cinematic lighting", height=120)
        
        opt1, opt2, opt3 = st.columns(3)
        aspect = opt1.selectbox("Aspect Ratio", ["1:1 (Square)", "16:9 (Landscape)", "9:16 (Portrait)"])
        model_type = opt2.selectbox("Model", ["flux", "turbo"])
        custom_seed = opt3.number_input("Seed (Optional)", min_value=0, max_value=999999, value=0)

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
                with st.spinner("Enhancing prompt with Gemini..."):
                    enhanced = enhance_prompt_with_gemini(img_prompt_input, active_api_key, "image")
                    st.success("Prompt Enhanced!")
                    img_prompt_input = enhanced
                    st.text_area("Enhanced Version", value=enhanced, height=80)
            else:
                st.warning("Please provide a prompt and Gemini API Key.")

    with img_col2:
        if generate_img_btn and img_prompt_input:
            with st.spinner("Generating ultra-res image..."):
                seed_val = None if custom_seed == 0 else custom_seed
                image_url = generate_image_url(img_prompt_input, width=w, height=h, seed=seed_val, model=model_type)
                
                st.image(image_url, caption=f"Prompt: {img_prompt_input}", use_container_width=True)
                
                img_bytes = download_media_bytes(image_url)
                if img_bytes:
                    st.download_button(
                        "📥 Download Full-Res Image",
                        data=img_bytes,
                        file_name=f"generated_art_{int(time.time())}.jpg",
                        mime="image/jpeg",
                        use_container_width=True
                    )
                    st.session_state.image_history.append({"url": image_url, "prompt": img_prompt_input})
        else:
            st.info("Describe your desired image on the left and click 'Render Artwork'.")

# ==========================================
# TAB 4: VIDEO & MOTION CORE
# ==========================================
with tab_video:
    st.subheader("🎬 AI Video & Dynamic Motion Studio")
    st.caption("Generate high-speed motion graphic loops, cinematic visuals, and animated sequences.")

    vid_col1, vid_col2 = st.columns([1, 1])

    with vid_col1:
        vid_prompt_input = st.text_area("Motion Prompt Description:", placeholder="e.g., A rotating golden holographic sphere floating in an ancient temple chamber", height=120)
        
        v_c1, v_c2 = st.columns(2)
        v_style = v_c1.selectbox("Visual Motion Style", ["cinematic", "3d animation", "cyberpunk fluid", "anime timelapse", "hyper-lapse"])
        v_fps = v_c2.selectbox("Quality Profile", ["Standard HD", "Ultra Dynamic 60FPS Simulation"])

        generate_vid_btn = st.button("🎬 Render Motion Visual", type="primary", use_container_width=True)

    with vid_col2:
        if generate_vid_btn and vid_prompt_input:
            with st.spinner("Synthesizing dynamic motion visual frames..."):
                motion_url = generate_video_url(vid_prompt_input, style=v_style)
                st.image(motion_url, caption=f"Motion Render: {vid_prompt_input} ({v_style})", use_container_width=True)
                
                motion_bytes = download_media_bytes(motion_url)
                if motion_bytes:
                    st.download_button(
                        "📥 Download Rendered Motion Frame",
                        data=motion_bytes,
                        file_name=f"motion_{int(time.time())}.jpg",
                        mime="image/jpeg",
                        use_container_width=True
                    )
        else:
            st.info("Enter a motion prompt and select your style to generate a visual animation sequence.")

# ==========================================
# TAB 5: OPENCLAW WORKSPACE & FILE MANAGER
# ==========================================
with tab_files:
    st.subheader("📂 OpenClaw Workspace File Manager")
    st.caption(f"Active Workspace Root: `{WORKSPACE_DIR}`")

    # File Explorer Toolbar
    f_action_col1, f_action_col2, f_action_col3 = st.columns([1, 1, 1])

    with f_action_col1:
        with st.expander("➕ Create New File"):
            new_fname = st.text_input("File Path/Name:", placeholder="subfolder/notes.txt")
            new_fcontent = st.text_area("Initial Content:", height=100)
            if st.button("Create File", use_container_width=True):
                if new_fname:
                    res = fs_write_file(new_fname, new_fcontent)
                    st.success(res)
                    st.rerun()

    with f_action_col2:
        with st.expander("📁 Create New Folder"):
            new_dname = st.text_input("Folder Name:", placeholder="data/csv_exports")
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

    # Workspace File Browser & Editor
    browser_col, editor_col = st.columns([1, 2])

    with browser_col:
        st.markdown("##### 📁 Workspace Tree")
        file_tree_text = fs_list_files()
        st.text_area("Directory Structure", value=file_tree_text, height=260, disabled=True)

        # Select file to inspect/edit
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
            st.info("Select a file from the dropdown on the left to read or edit its contents.")

    # Workspace Content Search (Grep)
    with st.expander("🔍 Search in Workspace Files"):
        search_q = st.text_input("Enter keyword or code snippet to search:")
        if search_q:
            results = fs_search_files(search_q)
            st.code(results, language="text")