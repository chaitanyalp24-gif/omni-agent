import streamlit as st
import os
from agent import run_agent_chat, generate_image_url, generate_video_url

# --- APP LAYOUT CONFIG ---
st.set_page_config(page_title="OmniAgent OS", page_icon="🤖", layout="wide")
st.title("🤖 OmniAgent: All-In-One AI Cloud Hub")

# --- SIDEBAR MONETIZATION & SECURITY ---
with st.sidebar:
    st.header("💳 Revenue & Settings")
    st.markdown("---")
    
    # 1. Monetization: Buy Me A Coffee donation trigger
    st.subheader("Support This Agent")
    st.write("Keep this agent alive by donating below:")
    st.link_button("☕ Buy Me A Coffee ($3)", "https://buymeacoffee.com")
    
    # 2. Monetization: Stripe premium upgrades
    st.subheader("Premium License")
    st.link_button("🚀 Upgrade to Pro ($5/mo)", "https://stripe.com")
    st.markdown("---")
    
    # 3. Security: Prevent key theft by using safe user input masking
    st.subheader("Authentication")
    gemini_key = st.text_input("Enter your free Gemini API Key:", type="password", help="Get a free key from Google AI Studio")

# --- CORE INTERFACE TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat & Web Search", "🎨 Image Studio", "🎬 Video Core", "📂 File System"])

# TAB 1: Chat and Real-time Search
with tab1:
    st.subheader("Intellectual Chat & Live Web Searching Engine")
    user_query = st.text_input("Ask a question or request a web search:", placeholder="e.g., What is the current stock price of Apple?")
    if st.button("Ask Agent", key="chat_btn"):
        if user_query:
            with st.spinner("Agent is reasoning and fetching cloud metrics..."):
                answer = run_agent_chat(user_query, gemini_key)
                st.write(answer)
        else:
            st.warning("Please type a question first.")

# TAB 2: Text-To-Image AI Generation
with tab2:
    st.subheader("Generative Art Machine")
    img_prompt = st.text_input("Describe the image you want the agent to draw:", placeholder="e.g., a cybernetic neon cat coding on a laptop")
    if st.button("Generate Art", key="img_btn"):
        if img_prompt:
            with st.spinner("Rendering artwork in cloud space..."):
                final_img = generate_image_url(img_prompt)
                st.image(final_img, caption=f"Result for: '{img_prompt}'", use_column_width=True)
        else:
            st.warning("Please describe an image first.")

# TAB 3: Text-To-Video AI Generation
with tab3:
    st.subheader("Generative Motion Graphics Core")
    vid_prompt = st.text_input("Describe your targeted short motion graphic:", placeholder="e.g., spinning gold coin in 3d render matrix style")
    if st.button("Render Motion", key="vid_btn"):
        if vid_prompt:
            with st.spinner("Processing cloud video stream cycles..."):
                final_vid = generate_video_url(vid_prompt)
                st.write("🎥 Your generated live motion visual preview:")
                st.image(final_vid, caption="Rendered Motion Sequence", use_column_width=True)
        else:
            st.warning("Please describe a motion graphic first.")

# TAB 4: Cloud Container File Management
with tab4:
    st.subheader("Secure Document Management File Parser")
    uploaded_doc = st.file_uploader("Upload any document configuration text file (.txt or .csv) for parsing:", type=["txt", "csv"])
    if uploaded_doc is not None:
        try:
            # Read text file content safely entirely on cloud RAM container
            file_contents = uploaded_doc.read().decode("utf-8")
            st.success("✅ File loaded securely into agent environment storage!")
            
            st.write("**File Overview metadata:**")
            st.write(f"- Name: {uploaded_doc.name}")
            st.write(f"- Size: {uploaded_doc.size} bytes")
            
            st.markdown("---")
            st.write("**Parsed Contents View:**")
            st.text_area("File Text Output", value=file_contents, height=200)
        except Exception as e:
            st.error(f"Failed to read file layout parameters: {str(e)}")
