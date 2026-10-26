import json
import os
import re
import time
from pathlib import Path
import streamlit as st
from sarvamai import SarvamAI

# Set Streamlit page configuration
st.set_page_config(
    page_title="Citizen Application Sorter",
    page_icon="📋",
    layout="wide",
)

# ---------------------------------------------------------
# Environment & Client Setup
# ---------------------------------------------------------
def load_api_key():
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))
    return os.environ.get("SARVAM_API_KEY")

api_key = load_api_key()
if not api_key:
    st.error("SARVAM_API_KEY not found in environment or .env file. Please ensure it is configured.")
    st.stop()

@st.cache_resource
def get_client(key: str):
    return SarvamAI(api_subscription_key=key)

client = get_client(api_key)

# ---------------------------------------------------------
# UI Header
# ---------------------------------------------------------
st.title("📋 Citizen Application Sorter")
st.caption("AI-powered triage for government officers • Powered by Sarvam Document Intelligence & sarvam-105b")

col_input, col_output = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("1. Upload Application")
    uploaded_file = st.file_uploader(
        "Upload a photo or scan of the citizen's application (any Indian language)",
        type=["jpg", "jpeg", "png", "webp", "pdf"],
        help="Supports printed and handwritten applications in all 22 Indian languages and English.",
    )

    if uploaded_file is not None:
        if uploaded_file.type.startswith("image/"):
            st.image(uploaded_file, caption="Uploaded Document Preview", use_container_width=True)
        else:
            st.info(f"File uploaded: {uploaded_file.name}")

    st.subheader("2. Output Language")
    target_lang = st.radio(
        "Select language for sorted output:",
        options=["English", "Hindi (हिन्दी)"],
        horizontal=True,
    )

    process_btn = st.button("🚀 Process & Sort Application", type="primary", use_container_width=True, disabled=(uploaded_file is None))

# ---------------------------------------------------------
# Processing Logic
# ---------------------------------------------------------
def digitise_document(file_obj):
    """Submits file to Sarvam Document Intelligence and polls for completion."""
    file_bytes = file_obj.getvalue()
    content_type = file_obj.type or "image/jpeg"
    
    # Start digitise job
    start_resp = client.doc_ai.digitise(
        file=[(file_obj.name, file_bytes, content_type)]
    )
    job_id = start_resp.job_id

    # Poll status
    status_placeholder = st.empty()
    max_retries = 30
    for attempt in range(max_retries):
        status_resp = client.doc_ai.get_status(job_id=job_id)
        current_status = status_resp.status
        status_placeholder.info(f"Digitising document with Sarvam Vision... (Status: {current_status})")
        
        if current_status in ("completed", "partially_completed"):
            break
        elif current_status in ("failed", "rejected"):
            raise RuntimeError(f"Sarvam Document Intelligence failed with status: {current_status}")
        
        time.sleep(2)
    else:
        raise TimeoutError("Document digitisation timed out.")

    status_placeholder.empty()

    # Retrieve Markdown results
    results = client.doc_ai.get_results(job_id=job_id, format="md")
    full_text = ""
    if hasattr(results, "documents") and results.documents:
        for doc in results.documents:
            if doc.pages:
                for page in doc.pages:
                    if page.content:
                        full_text += page.content + "\n\n"
    
    return full_text.strip()


def extract_application_details(ocr_text: str, language_choice: str):
    """Uses sarvam-105b to filter noise and extract structured civic fields."""
    lang_name = "Hindi" if "Hindi" in language_choice else "English"
    
    prompt = f"""You are an expert civic triage assistant for Indian government officers.
Analyze the following digitized citizen application (written in an Indian language or English).

Your task:
1. Ignore noise: Ignore emotional language, repeated complaints, honorifics, flattery, and narrative filler.
2. Extract the applicant's name and contact number (phone, email, or address contact) ONLY for administrative reply. Do NOT put these in the work bullets. If not found, write "Not provided".
3. Extract "work_requested": A concise list of 2 to 4 bullet points describing ONLY the specific, actionable civic work or repair requested.
4. Identify "department_responsible": The government department or civic body responsible for addressing this grievance (e.g., Public Works Department (PWD), Municipal Corporation / Sanitation, Electricity Board / DISCOM, Water Supply & Sewerage Board, Revenue Department, Police / Traffic, Health & Family Welfare).
5. Assign "priority" (1 to 5):
   - 5: Critical / Danger to human life or public safety (live wires, imminent collapse, contaminated drinking water outbreak)
   - 4: Urgent civic failure affecting community (main road blocked, overflowing sewer in residential area)
   - 3: Standard civic grievance / repair (pothole repair, broken street light, garbage clearance)
   - 2: Minor inconvenience or non-urgent administrative inquiry
   - 1: Low-priority query or general informational petition
6. Provide "priority_reason": Exactly one clear sentence explaining why this priority was assigned.
7. Translate/format all fields strictly into {lang_name}.

Document text:
\"\"\"
{ocr_text}
\"\"\"

Respond strictly with a valid JSON object matching this schema:
{{
  "applicant_name": "Applicant name or Not provided",
  "applicant_contact": "Contact number/info or Not provided",
  "work_requested": ["Specific work item 1", "Specific work item 2"],
  "department_responsible": "Responsible department name",
  "priority": 3,
  "priority_reason": "Single sentence explanation of priority."
}}
"""

    response = client.chat.completions(
        model="sarvam-105b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    content = response.choices[0].message.content or "{}"
    # Extract JSON safely
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except Exception:
            pass
    return {
        "applicant_name": "Could not parse",
        "applicant_contact": "Could not parse",
        "work_requested": [content],
        "department_responsible": "General Administration",
        "priority": 3,
        "priority_reason": "Automated evaluation.",
    }


# ---------------------------------------------------------
# Output Column Rendering
# ---------------------------------------------------------
with col_output:
    st.subheader("3. Actionable Officer Summary")

    if process_btn and uploaded_file is not None:
        try:
            with st.spinner("Step 1/2: Reading document via Sarvam Document Intelligence..."):
                ocr_text = digitise_document(uploaded_file)

            if not ocr_text:
                st.warning("No readable text could be extracted from this document. Please ensure the image is clear.")
            else:
                with st.spinner("Step 2/2: Filtering noise & extracting triage fields via sarvam-105b..."):
                    data = extract_application_details(ocr_text, target_lang)

                # 1. Applicant Details Box (separate)
                st.markdown("#### 👤 Applicant Details")
                with st.container(border=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**Name:** {data.get('applicant_name', 'Not provided')}")
                    with c2:
                        st.markdown(f"**Contact Number / Info:** {data.get('applicant_contact', 'Not provided')}")

                st.divider()

                # 2. Priority & Department
                c_prio, c_dept = st.columns([1, 1])
                priority = data.get("priority", 3)
                prio_colors = {
                    5: "🔴 **Priority 5 (Critical - Safety Risk)**",
                    4: "🟠 **Priority 4 (High - Urgent Disruption)**",
                    3: "🟡 **Priority 3 (Medium - Standard Maintenance)**",
                    2: "🔵 **Priority 2 (Low - Minor Inconvenience)**",
                    1: "⚪ **Priority 1 (Minimal - Informational)**",
                }
                badge = prio_colors.get(priority, f"Priority {priority}")

                with c_prio:
                    st.markdown("#### Priority Level")
                    st.markdown(f"### {badge}")
                    st.caption(f"**Reason:** {data.get('priority_reason', '')}")

                with c_dept:
                    st.markdown("#### Department Responsible")
                    dept = data.get("department_responsible", "General Administration")
                    st.markdown(f"### 🏛️ {dept}")

                st.divider()

                # 3. Work Requested
                st.markdown("#### 🛠️ Work Requested")
                work_items = data.get("work_requested", [])
                if isinstance(work_items, list) and work_items:
                    for item in work_items:
                        st.markdown(f"- **{item}**")
                else:
                    st.markdown(f"- {work_items}")

                # 4. Raw Transcript Expander for Audit
                with st.expander("🔍 View Raw Extracted Text (Document Intelligence)", expanded=False):
                    st.text(ocr_text)

        except Exception as e:
            st.error(f"Error processing application: {str(e)}")
    else:
        st.info("Upload an application photo on the left and click **'Process & Sort Application'** to view the triage summary.")
