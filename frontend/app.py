import streamlit as st
import requests
import datetime
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


# Page configuration
st.set_page_config(
    page_title="AI-Powered Bid & Proposal Response Engine",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling Injection
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
}
.stApp {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
    color: #c9d1d9;
}
.header-container {
    background: rgba(22, 27, 34, 0.85);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(48, 54, 61, 0.7);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}
.metric-box {
    background: rgba(33, 38, 45, 0.9);
    border: 1px solid rgba(56, 139, 253, 0.4);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(56, 139, 253, 0.05);
}
.metric-value {
    font-size: 2.5rem;
    font-weight: 800;
    color: #58a6ff;
}
.decision-go {
    background: linear-gradient(90deg, #2ea44f 0%, #238636 100%);
    color: white;
    padding: 10px 20px;
    border-radius: 30px;
    font-weight: 800;
    text-align: center;
    font-size: 1.5rem;
    box-shadow: 0 4px 15px rgba(46, 164, 79, 0.3);
}
.decision-nogo {
    background: linear-gradient(90deg, #f85149 0%, #da3633 100%);
    color: white;
    padding: 10px 20px;
    border-radius: 30px;
    font-weight: 800;
    text-align: center;
    font-size: 1.5rem;
    box-shadow: 0 4px 15px rgba(248, 81, 73, 0.3);
}
.card {
    background: rgba(22, 27, 34, 0.75);
    border: 1px solid rgba(48, 54, 61, 0.6);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 15px;
}
</style>
""", unsafe_allow_html=True)

API_URL = "http://localhost:8000"

# Sidebar Workspace Manager
st.sidebar.markdown("<h3 style='color:#58a6ff; font-size: 1.15rem; font-weight: 800; margin-top: 0;'>AI-Powered Bid & Proposal Response Engine</h3>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# User Session Switcher
st.sidebar.markdown("<h4 style='color:#c9d1d9; margin-bottom:5px;'>👤 Active Session</h4>", unsafe_allow_html=True)
user_options = {
    "admin": "admin (Bid Manager)",
    "writer": "writer (Pre-Sales Writer)",
    "viewer": "viewer (Executive Viewer)"
}
selected_user = st.sidebar.selectbox(
    "Switch User Persona:",
    options=list(user_options.keys()),
    format_func=lambda x: user_options[x],
    label_visibility="collapsed"
)
st.session_state["username"] = selected_user

role_badges = {
    "admin": "👑 **Role:** Bid Manager (Full Access)",
    "writer": "✍️ **Role:** Pre-Sales Writer (Drafts Only)",
    "viewer": "👁️ **Role:** Executive Viewer (Read Only)"
}
st.sidebar.info(role_badges[selected_user])
st.sidebar.markdown("---")

headers = {"X-Username": selected_user}

def has_perm(permission):
    user_permissions = {
        "admin": ["create_workspace", "override_checklist", "edit_draft", "export_proposal"],
        "writer": ["edit_draft", "export_proposal"],
        "viewer": ["export_proposal"]
    }
    return permission in user_permissions.get(selected_user, [])

# Fetch workspaces
try:
    response = requests.get(f"{API_URL}/workspaces", headers=headers)
    if response.status_code == 200:
        workspaces = response.json()
    else:
        workspaces = []
except Exception:
    workspaces = []
    st.sidebar.warning("⚠️ FastAPI Backend disconnected. Run python3 main.py on port 8000.")

# Workspace list
workspace_options = ["Select or Create Workspace"] + [f"{w['title']} [{w['id']}]" for w in workspaces]

default_index = 0
if "new_workspace_option" in st.session_state:
    target_option = st.session_state["new_workspace_option"]
    if target_option in workspace_options:
        default_index = workspace_options.index(target_option)
    # Clear the session state so that subsequent selections work normally
    del st.session_state["new_workspace_option"]

selected_option = st.sidebar.selectbox("Active RFP Workspaces", workspace_options, index=default_index)

st.sidebar.markdown("---")

# Gemini AI Configuration Panel
st.sidebar.markdown("<h4 style='color:#c9d1d9; margin-bottom:5px;'>🧠 Gemini AI Settings</h4>", unsafe_allow_html=True)
use_llm = st.sidebar.checkbox("Enable Gemini AI Mode", value=False, help="Uses Google Gemini model for deep RFP parsing and proposal narrative writing.")
gemini_api_key = ""
selected_model = "gemini-1.5-flash"
if use_llm:
    # Look for environment variable first
    import os
    env_key = os.environ.get("GEMINI_API_KEY", "")
    gemini_api_key = st.sidebar.text_input("Gemini API Key:", value=env_key, type="password", help="Enter your Google AI Studio API key. Left blank, it falls back to backend env var.")
    model_options = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]
    selected_model = st.sidebar.selectbox("Gemini Model:", options=model_options, index=0, help="Select the Google Gemini LLM model to use.")



with st.sidebar.expander("📚 Ingest Capability Files", expanded=False):
    st.markdown("Build your RAG database by uploading documents (PDF, DOCX, XLSX, TXT):")
    can_upload = has_perm("create_workspace")
    cap_domain = st.selectbox("Capability Domain:", ["General", "Cybersecurity", "IT Services", "Construction", "Energy", "Healthcare", "Logistics"], disabled=not can_upload)
    cap_file = st.file_uploader("Upload Case Study/CV:", type=["pdf", "docx", "xlsx", "txt"], key="cap_upload", disabled=not can_upload)
    if st.button("Upload to RAG Library", disabled=not can_upload):
        if cap_file:
            with st.spinner("Parsing & Chunking Document..."):
                try:
                    files = {"file": (cap_file.name, cap_file.getvalue(), cap_file.type)}
                    data = {"domain": cap_domain}
                    res = requests.post(f"{API_URL}/capabilities/upload", files=files, data=data, headers=headers)
                    if res.status_code == 200:
                        st.success(f"Success! Created {res.json()['chunks_count']} chunks.")
                    else:
                        st.error(f"Upload failed: {res.text}")
                except Exception as e:
                    st.error(f"Failed to connect: {e}")
        else:
            st.warning("Please select a file to upload.")
    if not can_upload:
        st.caption("🔒 Upload locked (Bid Managers only)")

# Template loader to aid rapid prototyping
RFP_TEMPLATES = {
    "IT Services (Cybersecurity RFP)": {
        "title": "Hospital Cybersecurity Infrastructure Upgrade",
        "sector": "IT Services",
        "budget": "PKR 25M",
        "deadline": (datetime.date.today() + datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
        "rfp_text": (
            "Section 1: General Requirements\n"
            "The selected vendor must possess a valid ISO 27001 Certification.\n"
            "The vendor must outline their database security protocols.\n"
            "The project manager must have a certified profile.\n\n"
            "Section 2: Proposal Questions\n"
            "Question 1: Describe your company's experience in deploying cybersecurity architectures.\n"
            "Question 2: Detail your deployment timeline and threat mitigation methodologies."
        )
    },
    "IT Services (Mobile Banking App)": {
        "title": "NextGen Mobile Banking App Development",
        "sector": "IT Services",
        "budget": "PKR 85M",
        "deadline": (datetime.date.today() + datetime.timedelta(days=60)).strftime("%Y-%m-%d"),
        "rfp_text": (
            "Section 1: Security & Compliance\n"
            "The selected vendor must possess a valid ISO 27001 Certification.\n"
            "The application architecture must support high availability with 99.9% uptime SLA.\n"
            "The project team must include a PMP certified manager.\n\n"
            "Section 2: Technical Questions\n"
            "Question 1: Describe your company's past experience with mobile banking app development.\n"
            "Question 2: Explain how your team will handle data encryption and database security protocols."
        )
    },
    "Road Construction RFP": {
        "title": "National Highway Re-Carpet Expansion",
        "sector": "Construction",
        "budget": "PKR 200M",
        "deadline": (datetime.date.today() + datetime.timedelta(days=45)).strftime("%Y-%m-%d"),
        "rfp_text": (
            "Section 1: Technical Standards\n"
            "The civil contractor must have prior experience in road engineering.\n"
            "A safety inspector with certified experience must be assigned.\n\n"
            "Section 2: Proposal Questions\n"
            "Question 1: Describe your previous experience with road and bridge engineering.\n"
            "Question 2: Detail your project duration mapping and safety guarantee methods."
        )
    },
    "Construction (Solar Grid installation)": {
        "title": "Solar Energy Power Station Construction",
        "sector": "Construction",
        "budget": "PKR 120M",
        "deadline": (datetime.date.today() + datetime.timedelta(days=90)).strftime("%Y-%m-%d"),
        "rfp_text": (
            "Section 1: Operations & Compliance\n"
            "The engineering firm must possess a valid ISO 9001 certification.\n"
            "All physical civil structures must adhere to standard safety compliance guidelines.\n"
            "The structural team lead must hold a PMP certification.\n\n"
            "Section 2: Project Questions\n"
            "Question 1: Describe your company's past experience in solar energy grid construction.\n"
            "Question 2: Detail your quality assurance program and raw supply line checks."
        )
    },
    "Logistics (Smart Fleet GPS Tracking)": {
        "title": "Logistics Fleet GPS and Warehouse Integration",
        "sector": "Logistics",
        "budget": "PKR 45M",
        "deadline": (datetime.date.today() + datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
        "rfp_text": (
            "Section 1: Operational Mandates\n"
            "The vendor must support real-time active GPS tracking standards for fleet capacity.\n"
            "The contractor must provide warehouse cargo liability coverage of at least PKR 10M.\n"
            "Operations must include a PMP certified logistics manager.\n\n"
            "Section 2: Technical Questions\n"
            "Question 1: Explain your past experience with cargo tracking and barcode scanner systems.\n"
            "Question 2: Detail your customer support SLA response time and transit on-time rates."
        )
    }
}

if selected_option == "Select or Create Workspace":
    st.markdown("<h1 style='color:#58a6ff;'>🚀 Create New RFP Workspace</h1>", unsafe_allow_html=True)
    st.markdown("Ingest a tender or request document, run multi-agent RAG analysis, and auto-draft proposals.")
    
    can_create = has_perm("create_workspace")
    if not can_create:
        st.warning("🔒 Workspace creation is locked for your current role. Switch to a Bid Manager role (e.g. admin) to create new RFPs.")
        
    # Template filler selection box
    template_choice = st.selectbox("Fill Form using Prototype Template:", ["Empty Form"] + list(RFP_TEMPLATES.keys()), disabled=not can_create)
    
    default_vals = {"title": "", "sector": "IT Services", "budget": "PKR 10M", "deadline": datetime.date.today(), "rfp_text": ""}
    if template_choice != "Empty Form":
        t_data = RFP_TEMPLATES[template_choice]
        default_vals["title"] = t_data["title"]
        default_vals["sector"] = t_data["sector"]
        default_vals["budget"] = t_data["budget"]
        default_vals["deadline"] = datetime.datetime.strptime(t_data["deadline"], "%Y-%m-%d").date()
        default_vals["rfp_text"] = t_data["rfp_text"]
        
    with st.form("create_workspace_form"):
        title = st.text_input("RFP Project Title", value=default_vals["title"], disabled=not can_create)
        col1, col2, col3 = st.columns(3)
        with col1:
            sector = st.selectbox("Industry Vertical", ["IT Services", "Construction", "Energy", "Healthcare", "Logistics"], index=["IT Services", "Construction", "Energy", "Healthcare", "Logistics"].index(default_vals["sector"]), disabled=not can_create)
        with col2:
            budget = st.text_input("RFP Estimated Budget", value=default_vals["budget"], disabled=not can_create)
        with col3:
            deadline = st.date_input("Submission Deadline", value=default_vals["deadline"], disabled=not can_create)
            
        rfp_file = st.file_uploader("Upload RFP File (PDF, DOCX, TXT):", type=["pdf", "docx", "txt"], disabled=not can_create)
        rfp_text = st.text_area("Or Paste RFP Technical Requirements / Prompt Text", value=default_vals["rfp_text"], height=200, disabled=not can_create)
        
        submitted = st.form_submit_button("Run Multi-Agent Response Engine ⚡", disabled=not can_create)
        
        if submitted:
            if not title:
                st.error("Please enter a project title.")
            elif not rfp_text and not rfp_file:
                st.error("Please upload an RFP file or paste technical requirements text.")
            else:
                with st.spinner("Executing Agent Core loops (Analyst -> Researcher -> Scorer -> Writer -> Reviewer)..."):
                    try:
                        payload = {
                            "title": title,
                            "sector": sector,
                            "budget": budget,
                            "deadline": deadline.strftime("%Y-%m-%d"),
                            "rfp_text": rfp_text if rfp_text else "",
                            "use_llm": use_llm,
                            "llm_model": selected_model
                        }
                        files = {}
                        if rfp_file:
                            files["rfp_file"] = (rfp_file.name, rfp_file.getvalue(), rfp_file.type)
                            
                        req_headers = headers.copy()
                        if use_llm and gemini_api_key:
                            req_headers["X-Gemini-API-Key"] = gemini_api_key
                            
                        res = requests.post(f"{API_URL}/workspaces", data=payload, files=files if rfp_file else None, headers=req_headers)
                        if res.status_code == 200:
                            ws_id = res.json()["workspace_id"]
                            st.session_state["new_workspace_option"] = f"{title} [{ws_id}]"
                            st.success(f"Success! Workspace {ws_id} initialized.")
                            st.rerun()
                        else:
                            st.error(f"Error starting workflow: {res.text}")
                    except Exception as e:
                        st.error(f"Failed to connect to API: {e}")

else:
    # Selected Workspace Detail View
    selected_id = selected_option.split("[")[-1].replace("]", "").strip()
    
    # Load data
    try:
        res = requests.get(f"{API_URL}/workspaces/{selected_id}", headers=headers)
        if res.status_code == 200:
            data = res.json()
            ws = data["workspace"]
            checklist = data["compliance_checklist"]
            drafts = data["proposal_drafts"]
            win_prob = data["win_probability"]
            decision = data["decision"]
            breakdown = data["scoring_breakdown"]
        else:
            st.error("Error loading workspace data.")
            st.stop()
    except Exception as e:
        st.error(f"API Error: {e}")
        st.stop()
        
    # Header Card
    st.markdown(f"""
    <div class="header-container">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <h1 style="margin:0; color:#58a6ff;">{ws['title']}</h1>
                <p style="margin:5px 0 0 0; color:#8b949e;">Workspace ID: <code>{ws['id']}</code> | Sector: <b>{ws['client']}</b> | Deadline: <b>{ws['deadline']}</b></p>
            </div>
            <div class="{"decision-go" if decision == "GO" else "decision-nogo"}">
                Recommendation: {decision}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Win Probability & Metrics Row
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-box">
            <div style="color:#8b949e; font-size:0.9rem;">WIN PROBABILITY</div>
            <div class="metric-value" style="color:{"#3fb950" if decision=="GO" else "#f85149"};">{win_prob}%</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-box">
            <div style="color:#8b949e; font-size:0.9rem;">BUDGET ALIGNMENT</div>
            <div class="metric-value">{breakdown['budget_fit']}%</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-box">
            <div style="color:#8b949e; font-size:0.9rem;">COMPLIANCE FIT</div>
            <div class="metric-value">{breakdown['compliance_fit']}%</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-box">
            <div style="color:#8b949e; font-size:0.9rem;">CAPABILITY RATIO</div>
            <div class="metric-value">{breakdown['gaps_score']}%</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="metric-box">
            <div style="color:#8b949e; font-size:0.9rem;">COMPETITOR PENALTY</div>
            <div class="metric-value" style="color:#f85149;">-{breakdown['competitor_penalty']}%</div>
        </div>
        """, unsafe_allow_html=True)
        
    # Main Application tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Compliance Checklist Grid", 
        "✍️ Technical Narrative Editor", 
        "📊 Sector Evaluation Criteria", 
        "📋 SOW Plan & Estimates",
        "📥 Export & Download"
    ])
    
    with tab1:
        st.markdown("### Compliance Checklist Audits")
        st.markdown("Requirements parsed by **Analyst Agent** matched against **Capability Library** via Researcher RAG queries.")
        
        # Checklist table loop
        for item in checklist:
            status_color = "#3fb950" if item["status"] == "Pass" else ("#f85149" if item["status"] == "Fail" else "#8b949e")
            is_overridden = f" ({item['override_status']})" if item.get("override_status") else ""
            
            with st.container():
                st.markdown(f"""
                <div class="card" style="border-left: 5px solid {status_color};">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h4 style="margin:0;">Requirement Check: <code>{item['id'].split('-')[-1]}</code> | <span style="font-size:0.95rem; font-weight:normal; color:#8b949e;">Section: {item['section']}</span></h4>
                        <span style="color:{status_color}; font-weight:bold; font-size:1.1rem;">{item['status'].upper()}{is_overridden}</span>
                    </div>
                    <p style="margin:10px 0; font-size:1.05rem;">{item['description']}</p>
                    <p style="margin:5px 0; color:#8b949e; font-size:0.95rem;"><b>Matched Evidence Source:</b> <i>{item['matched_evidence']}</i></p>
                    <p style="margin:0; color:#8b949e; font-size:0.9rem;"><b>Notes:</b> {item['notes']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Interactive manual overrides
                col_btn1, col_btn2, col_btn3, col_lock = st.columns([1.5, 1.5, 1.5, 5])
                can_override = has_perm("override_checklist")
                with col_btn1:
                    if st.button("Pass Requirement", key=f"p-{item['id']}", disabled=not can_override):
                        requests.post(f"{API_URL}/workspaces/{selected_id}/checklist/{item['id']}/override", json={"status": "Pass", "notes": "Approved manually after verification"}, headers=headers)
                        st.rerun()
                with col_btn2:
                    if st.button("Fail Requirement", key=f"f-{item['id']}", disabled=not can_override):
                        requests.post(f"{API_URL}/workspaces/{selected_id}/checklist/{item['id']}/override", json={"status": "Fail", "notes": "Capability missing or certification invalid"}, headers=headers)
                        st.rerun()
                with col_btn3:
                    if st.button("Waive Requirement", key=f"w-{item['id']}", disabled=not can_override):
                        requests.post(f"{API_URL}/workspaces/{selected_id}/checklist/{item['id']}/override", json={"status": "Waived", "notes": "Waived by client request"}, headers=headers)
                        st.rerun()
                if not can_override:
                    with col_lock:
                        st.markdown("<span style='color:#f85149; font-size:0.9rem; line-height:38px;'>🔒 Overrides locked (Bid Managers only)</span>", unsafe_allow_html=True)
                st.write("\n")
                
    with tab2:
        st.markdown("### Technical Proposal Narrative Editor")
        st.markdown("Review and modify AI-generated proposal narrative sections created by the **Writer Agent**.")
        
        for idx, draft in enumerate(drafts):
            st.markdown(f"#### Question {draft['question_id']}: **{draft['question_text']}**")
            
            # Reviewer comments box
            comments = draft["comments"]
            if "[Warning]" in comments:
                st.warning(comments)
            else:
                st.info(comments)
                
            # Split Screen View
            col_l, col_r = st.columns([6, 4])
            can_edit = has_perm("edit_draft")
            with col_l:
                edited_answer = st.text_area(
                    "Draft Proposal Text (Markdown supported):",
                    value=draft["drafted_answer"],
                    height=280,
                    key=f"ans-{draft['question_id']}",
                    disabled=not can_edit
                )
                col_save, col_edit_lock = st.columns([3, 7])
                with col_save:
                    if st.button("Save Draft Updates", key=f"save-{draft['question_id']}", disabled=not can_edit):
                        res_upd = requests.post(
                            f"{API_URL}/workspaces/{selected_id}/drafts/{draft['question_id']}/edit",
                            json={"drafted_answer": edited_answer},
                            headers=headers
                        )
                        if res_upd.status_code == 200:
                            st.success("Draft updated locally in SQLite.")
                        else:
                            st.error("Failed to save draft.")
                if not can_edit:
                    with col_edit_lock:
                        st.markdown("<span style='color:#f85149; font-size:0.9rem; line-height:38px;'>🔒 Editing locked (Pre-Sales Writers/Bid Managers only)</span>", unsafe_allow_html=True)
            with col_r:
                st.markdown(f"""
                <div class="card" style="height:325px; overflow-y:auto; font-size:0.95rem;">
                    <h5 style="margin-top:0; color:#58a6ff;">Capability Reference Context</h5>
                    <p style="white-space: pre-line;">{draft['matched_evidence']}</p>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("---")
            
    with tab3:
        st.markdown(f"### Standard Evaluation Criteria Taxonomy – {ws['client']}")
        st.markdown("This sector-specific scoring taxonomy is used by clients to grade proposal bids.")
        try:
            crit_res = requests.get(f"{API_URL}/criteria/{ws['client']}", headers=headers)
            if crit_res.status_code == 200:
                criteria_list = crit_res.json()
                if criteria_list:
                    # Render a nice table
                    table_data = []
                    for c in criteria_list:
                        table_data.append({
                            "Criteria ID": c["id"],
                            "Evaluation Parameter": c["criteria_name"],
                            "Description": c["description"],
                            "Standard Weight Range": c["weight_range"]
                        })
                    st.table(table_data)
                else:
                    st.info("No criteria loaded for this sector.")
            else:
                st.error("Failed to load evaluation criteria.")
        except Exception as e:
            st.error(f"Error connecting to taxonomy API: {e}")

    with tab4:
        st.markdown("### AI-Generated Statement of Work (SOW) Estimates")
        st.markdown("Operational resource headcounts, man-months timeline, and cost analysis structures aligned to the bid budget.")
        
        sow = data.get("sow_plan")
        if sow:
            # 1. Milestones
            st.markdown("#### 1. Project Milestones & Deliverables Schedule")
            m_list = sow.get("milestones", [])
            if m_list:
                st.table(m_list)
            else:
                st.info("No milestone data found.")
                
            # 2. Labor Efforts
            st.markdown("#### 2. Resource Headcount & Labor Effort Estimates")
            e_list = sow.get("efforts", [])
            if e_list:
                st.table(e_list)
            else:
                st.info("No labor effort data found.")
                
            # 3. Cost Breakdown
            st.markdown("#### 3. SOW Cost Analysis & Allocation")
            c_list = sow.get("costs", [])
            if c_list:
                st.table(c_list)
            else:
                st.info("No cost analysis data found.")
        else:
            st.warning("No SOW Plan generated for this workspace. SOW generation is performed on new workspace initializations.")

    with tab5:
        st.markdown("### Proposal Document Generation")
        st.markdown("Compile your workspace configurations, compliance grids, and narrative drafts into a single structured, branded Microsoft Word Document (.docx).")
        
        st.write("\n")
        export_link = f"{API_URL}/workspaces/{selected_id}/export?username={selected_user}"
        
        st.markdown(f"""
        <div style='text-align: center; padding: 40px;'>
            <a href='{export_link}' target='_blank'>
                <button style='
                    background: linear-gradient(135deg, #1f6feb 0%, #094cb4 100%);
                    color: white;
                    padding: 15px 30px;
                    border: none;
                    border-radius: 8px;
                    font-size: 1.2rem;
                    font-weight: bold;
                    cursor: pointer;
                    box-shadow: 0 4px 15px rgba(31, 111, 235, 0.4);
                '>
                    📥 Compile & Download .DOCX Document
                </button>
            </a>
            <p style='color:#8b949e; margin-top:15px;'>Generates fully compliant headers, styled headings, and references matched from capability libraries.</p>
        </div>
        """, unsafe_allow_html=True)
