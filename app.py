import streamlit as st
import requests
import uuid

# ---------------------------
# Setup - Branding & Layout
# ---------------------------
st.set_page_config(
    page_title="Abit.ai CV Assessment",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.sidebar.image("https://abit.ai/wp-content/uploads/2023/09/abit-dark.png", width=200)
st.sidebar.title("🔐 Authentication")

# Alias dropdown
base_url_options = {
    "AWS EC2": "http://13.48.123.138:8000/api",
    "Localhost": "http://127.0.0.1:8000/api",
    "Dev Server": "http://dev.example.com/api"
}
base_url_alias = st.sidebar.selectbox("API Base URL", list(base_url_options.keys()), index=0)
base_url = base_url_options[base_url_alias]

# API key input
api_key = st.sidebar.text_input("API Key", type="password")

# Known valid key for testing
demo_valid_key = st.secrets["demo_valid_key"]

headers = {"accept": "application/json"}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

    if api_key == demo_valid_key:
        st.sidebar.success("✅ API key is valid.")
    else:
        st.sidebar.error("❌ Invalid API key.")
else:
    st.sidebar.info("🔑 Please enter your API key.")


# Helper functions
def safe_post(endpoint, files=None, data=None, params=None):
    if not api_key:
        st.error("❌ API key required.")
        return None
    try:
        return requests.post(f"{base_url}{endpoint}", headers=headers, files=files, data=data, params=params)
    except Exception as e:
        st.error(f"❌ Request failed: {e}")
        return None

def safe_get(endpoint, params=None):
    if not api_key:
        st.error("❌ API key required.")
        return None
    try:
        return requests.get(f"{base_url}{endpoint}", headers=headers, params=params)
    except Exception as e:
        st.error(f"❌ Request failed: {e}")
        return None

def safe_get_rank_candidates(page=1, page_size=100, sort_by="final_assessment_score", sort_order="desc", recommendation_type=None):
    params = {
        "page": page,
        "page_size": page_size,
        "sort_by": sort_by,
        "sort_order": sort_order
    }
    if recommendation_type:
        params["recommendation_type"] = recommendation_type
    return safe_get("/rank-candidates", params=params)

# ---------------------------
# Sidebar - Operations
# ---------------------------
st.sidebar.title("⚙️ Operations")
operation = st.sidebar.radio("Select Operation", [
    "Home",
    "Upload Job Requirements",
    "Upload CVs",
    "Assess CVs",
    "Rank Candidates",
    "Download Results",
    "Reset All Data"
])

# ---------------------------
# Main Panel (Dynamic)
# ---------------------------
st.title("📄 Abit.ai CV Assessment System")

# ---------------------------
# Home
# ---------------------------
if operation == "Home":
    st.header("🏠 System Health Check")
    if st.button("Check API Health"):
        try:
            resp = requests.get(base_url.replace("/api", "") + "/health")
            if resp.status_code == 200:
                st.success("✅ API is healthy.")
            else:
                st.error("❌ API health check failed.")
        except Exception:
            st.error("❌ Could not connect to API.")

# ---------------------------
# Upload Job Requirements
# ---------------------------
if operation == "Upload Job Requirements":
    st.header("📄 Upload Job Description")
    job_file = st.file_uploader("Upload Job Description (PDF/DOCX)", type=["pdf", "docx"])
    if job_file and st.button("Upload Job"):
        files = {"file": (job_file.name, job_file, job_file.type)}
        response = safe_post("/upload-job", files=files)
        if response and response.status_code == 200:
            st.success("✅ Job Description uploaded successfully.")
            st.text_area("Extracted Job Requirements", value=str(response.json().get("extracted_requirements")), height=250)

# ---------------------------
# Upload CVs
# ---------------------------
if operation == "Upload CVs":
    import time

    st.header("📁 Upload Candidate CVs")

    if "upload_key" not in st.session_state:
        st.session_state.upload_key = str(uuid.uuid4())

    st.markdown("ℹ️ Previously uploaded CVs stay unless you Reset All.")

    # Upload Component
    cv_files = st.file_uploader(
        "Select CVs (multiple allowed)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key=st.session_state.upload_key
    )

    if st.button("Upload Selected CVs"):
        if cv_files:
            files = [("files", (cv.name, cv, cv.type)) for cv in cv_files]
            response = safe_post("/upload-cv", files=files)

            if response and response.status_code == 200:
                data = response.json()
                uploaded = len(data.get("uploaded_files", []))
                skipped = len(cv_files) - uploaded

                st.session_state.upload_results = {
                    "uploaded": uploaded,
                    "skipped": skipped,
                    "timestamp": time.time()
                }

                st.success(f"✅ Uploaded: {uploaded} | ❗Skipped (Duplicates): {skipped}")

                st.session_state.upload_key = str(uuid.uuid4())

            else:
                st.error("❌ Upload failed. Try again.")
        else:
            st.warning("⚠️ No files selected.")

    if "upload_results" in st.session_state:
        results = st.session_state.upload_results
        if results:
            st.info(f"📄 Last Upload -> Uploaded: {results['uploaded']} | ❗Skipped: {results['skipped']}")

    st.divider()

    # ---- Uploaded CVs List
    st.subheader("📦 Uploaded CVs List")

    list_resp = safe_get("/list-cvs")
    rank_resp = safe_get_rank_candidates(page=1, page_size=100, sort_by="final_assessment_score", sort_order="desc")

    if list_resp and list_resp.status_code == 200:
        list_data = list_resp.json()

        if not list_data:
            st.info("📭 No CVs uploaded yet.")
        else:
            assessed_filenames = set()
            if rank_resp and rank_resp.status_code == 200:
                for candidate in rank_resp.json().get("rankings", []):
                    assessed_filenames.add(candidate["filename"])

            filter_choice = st.selectbox("Filter by Status", ["All", "Assessed", "Not Assessed"])

            table = []
            for cv_id, filename in list_data.items():
                status = "✅ Assessed" if filename in assessed_filenames else "🕒 Not Assessed"
                if filter_choice == "All" or \
                   (filter_choice == "Assessed" and status == "✅ Assessed") or \
                   (filter_choice == "Not Assessed" and status == "🕒 Not Assessed"):
                    table.append({
                        "CV ID": int(cv_id),
                        "Filename": filename,
                        "Status": status
                    })

            st.dataframe(table, use_container_width=True)

# ---------------------------
# Assess CVs
# ---------------------------
if operation == "Assess CVs":
    st.header("🧠 Assess Uploaded CVs")

    if st.button("Run Batch Assessment"):
        resp = safe_post("/assess-all-cvs")
        if resp and resp.status_code == 200:
            result = resp.json()
            new_assessed = len(result.get("assessed_cvs", []))
            if new_assessed > 0:
                st.session_state.assess_message = f"✅ Successfully assessed {new_assessed} new CV(s)."
            else:
                st.session_state.assess_message = "ℹ️ All uploaded CVs have already been assessed."
            st.rerun()
        else:
            st.error("❌ Assessment failed.")

    if "assess_message" in st.session_state:
        st.success(st.session_state.assess_message)
        del st.session_state.assess_message

    st.divider()
    st.subheader("📑 Assessed CVs Overview")

    rank_resp = safe_get("/rank-candidates", params={"page": 1, "page_size": 100, "sort_by": "final_assessment_score", "sort_order": "desc"})

    if rank_resp and rank_resp.status_code == 200:
        data = rank_resp.json()
        assessed = data.get("rankings", [])
        if assessed:
            table_data = [{
                "Filename": item["filename"],
                "Tech Lead Score": item["detailed_scores"]["technical_lead"]["score"],
                "HR Specialist Score": item["detailed_scores"]["hr_specialist"]["score"],
                "Project Manager Score": item["detailed_scores"]["project_manager"]["score"],
                "Final Score": item["final_score"],
                "Recommendation": item["recommendation"]
            } for item in assessed]

            st.dataframe(table_data, use_container_width=True)

            for item in assessed:
                with st.expander(f"📄 {item['filename']} — Detailed Justifications"):
                    st.markdown(f"**Final Justification:** {item['final_justification']}")
                    st.write("**Technical Lead:**", item["detailed_scores"]["technical_lead"]["justification"])
                    st.write("**HR Specialist:**", item["detailed_scores"]["hr_specialist"]["justification"])
                    st.write("**Project Manager:**", item["detailed_scores"]["project_manager"]["justification"])
        else:
            st.info("📭 No CVs have been assessed yet.")
    else:
        st.error("❌ Failed to fetch assessed CVs.")

# ---------------------------
# Rank Candidates
# ---------------------------
if operation == "Rank Candidates":
    st.header("🏆 Rank Candidates")

    page = st.number_input("Page", min_value=1, value=1)
    page_size = st.number_input("Page Size", min_value=1, max_value=50, value=10)
    sort_by = st.selectbox("Sort By", ["final_assessment_score", "technical_lead_score", "hr_specialist_score", "project_manager_score"])
    sort_order = st.selectbox("Sort Order", ["desc", "asc"])
    recommendation_type = st.selectbox("Filter by Recommendation", ["None", "Interview", "Reject", "Maybe"])

    if st.button("Get Rankings"):
        params = {
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
        if recommendation_type != "None":
            params["recommendation_type"] = recommendation_type

        response = safe_get("/rank-candidates", params=params)

        if response and response.status_code == 200:
            data = response.json()
            st.success(f"Retrieved {len(data.get('rankings', []))} candidates.")

            rankings = data.get("rankings", [])
            if rankings:
                table_data = [{
                    "Rank": r["rank"],
                    "Filename": r["filename"],
                    "Final Score": r["final_score"],
                    "Recommendation": r["recommendation"]
                } for r in rankings]

                st.dataframe(table_data, use_container_width=True)

                for r in rankings:
                    with st.expander(f"📄 {r['filename']} — Details"):
                        st.markdown(f"**Final Justification:** {r['final_justification']}")
                        st.markdown("**Detailed Scores:**")
                        st.write("Tech Lead:", r["detailed_scores"]["technical_lead"]["justification"])
                        st.write("HR Specialist:", r["detailed_scores"]["hr_specialist"]["justification"])
                        st.write("Project Manager:", r["detailed_scores"]["project_manager"]["justification"])
            else:
                st.warning("No candidates found.")
        else:
            st.error("❌ Failed to retrieve rankings.")

# ---------------------------
# Download Results
# ---------------------------
if operation == "Download Results":
    st.header("⬇️ Download Assessment Results")

    fmt = st.selectbox("Select Format", ["json", "csv"])
    if st.button("Download Results"):
        resp = safe_get("/download-assessments", params={"format": fmt})
        if resp and resp.status_code == 200:
            st.download_button(
                f"Download {fmt.upper()}",
                resp.content,
                file_name=f"assessments.{fmt}",
                mime="application/octet-stream"
            )
        else:
            st.error("❌ Failed to download results.")

# ---------------------------
# Reset All Data
# ---------------------------
if operation == "Reset All Data":
    st.header("🧹 Reset Storage")

    if st.button("Reset Everything"):
        resp = safe_post("/reset-cvs")
        if resp and resp.status_code == 200:
            st.success("✅ All CVs and Assessments cleared.")
            st.session_state.clear()
            st.rerun()
        else:
            st.error("❌ Reset failed.")
