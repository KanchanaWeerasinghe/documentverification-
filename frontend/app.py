import os
import shutil
from pathlib import Path

import streamlit as st

from api_client import APIClient, APIError


API_URL = os.getenv("DOCUMENT_API_URL", "http://localhost:8000")
ROOT = Path(__file__).resolve().parent.parent
PRIMARY_STORAGE = Path(os.getenv("PRIMARY_STORAGE_PATH", str(ROOT / "backend" / "data" / "primary")))
REFERENCE_STORAGE = Path(os.getenv("REFERENCE_STORAGE_PATH", str(ROOT / "backend" / "data" / "references")))
STAGES = ["parsed", "chunked", "embedded", "summarized", "key_points_extracted", "entities_extracted", "verified", "done"]

st.set_page_config(page_title="Medical Document Verification", page_icon="DV", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root { --ink:#17212b; --muted:#66737d; --line:#d9e1df; --mint:#b9e6d5; --coral:#e76f51; --paper:#f6f8f5; }
.stApp { background:var(--paper); color:var(--ink); font-family:'DM Sans',sans-serif; }
h1,h2,h3 { font-family:'Space Grotesk',sans-serif; letter-spacing:0; }
[data-testid="stSidebar"] { background:#17212b; } [data-testid="stSidebar"] * { color:#edf5f0 !important; }
.eyebrow { color:var(--coral); font-size:.78rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }
.hero { border-bottom:1px solid var(--line); padding:1rem 0 1.5rem; margin-bottom:1.5rem; }
.hero h1 { font-size:clamp(2rem,4vw,3.5rem); margin:.25rem 0 .4rem; }
.hero p { color:var(--muted); font-size:1.05rem; max-width:720px; }
.panel { background:white; border:1px solid var(--line); border-radius:8px; padding:1.15rem; margin-bottom:1rem; }
.step { color:var(--muted); font-size:.8rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.citation { background:#f0f7f3; border-left:4px solid var(--mint); padding:.8rem 1rem; margin-top:.5rem; }
</style>""", unsafe_allow_html=True)


def client() -> APIClient:
    return APIClient(API_URL, st.session_state.get("access_token"))


def save_upload(uploaded_file, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / uploaded_file.name
    with target.open("wb") as output:
        shutil.copyfileobj(uploaded_file, output)


def login_screen():
    _, column, _ = st.columns([1, 1.2, 1])
    with column:
        st.markdown('<div class="eyebrow">Secure review workspace</div>', unsafe_allow_html=True)
        st.title("Medical Document Verification")
        st.write("Verify prescribed medications against the institutional formulary.")
        with st.form("login"):
            username = st.text_input("Email or username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
        if submitted:
            try:
                result = APIClient(API_URL).login(username, password)
                st.session_state.authenticated = True
                st.session_state.access_token = result.get("access_token")
                st.session_state.user = result.get("user", {"username": username})
                st.rerun()
            except APIError:
                st.error("Login failed. Check your username and password.")


def show_progress(status):
    st.subheader("Document Verification Progress")
    stage_map = {item["name"]: item for item in status.get("stages", [])}
    for name in STAGES:
        item = stage_map.get(name, {})
        state = item.get("status", "PENDING")
        label = name.replace("_", " ").title()
        icon = "✓" if state == "COMPLETED" else "!" if state == "FAILED" else "●" if state == "STARTED" else "○"
        timestamp = item.get("completed_at") or item.get("started_at") or ""
        st.write(f"**{icon} {label}**  |  {state.title()}  {timestamp}")
        if state == "FAILED" and item.get("error"):
            st.error(item["error"])


def show_result(result):
    status = result.get("status", "UNSUPPORTED")
    labels = {"SUPPORTED": ("✓", "Supported"), "CONTRADICTED": ("!", "Contradicted"), "UNSUPPORTED": ("?", "Unsupported")}
    icon, label = labels.get(status, ("?", status.title()))
    with st.expander(f"{icon} {result.get('medication_name', 'Unknown medication')} - {label}", expanded=status != "SUPPORTED"):
        st.write(result.get("explanation") or "No explanation was returned by the backend.")
        for comparison in result.get("comparisons", []):
            st.write(f"**{comparison.get('parameter', 'Parameter')}:** {comparison.get('primary_value', 'Not specified')} | Reference: {comparison.get('reference_value', 'Not specified')}")
        evidence = result.get("evidence")
        if status in {"CONTRADICTED", "UNSUPPORTED"}:
            st.markdown("**Flagged issue citation**")
            if evidence:
                st.markdown('<div class="citation">', unsafe_allow_html=True)
                st.write(f"Medication: {evidence.get('medication_name') or result.get('medication_name')}")
                st.write(f"Section: {evidence.get('section') or 'Not provided'}")
                st.write(f"Page: {evidence.get('page') or 'Not provided'}")
                st.write(evidence.get("text") or "No supporting reference passage was retrieved.")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("No supporting reference passage was retrieved.")


def verification_page():
    user = st.session_state.get("user", {})
    st.sidebar.markdown("## Medical Document Verification")
    st.sidebar.caption(user.get("username", "Authenticated user"))
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
    st.markdown('<div class="hero"><div class="eyebrow">Evidence-led review</div><h1>Medical Document Verification</h1><p>Compare a primary document with an institutional reference and inspect every flagged result.</p></div>', unsafe_allow_html=True)

    reference = st.session_state.get("reference_document_id")
    primary = st.session_state.get("primary_document_id")
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown('<div class="panel"><div class="step">Step 1 / Reference document</div>', unsafe_allow_html=True)
        reference_file = st.file_uploader("Upload institutional reference", type=["pdf", "docx"], key="reference_file")
        if reference_file:
            st.caption(f"Selected: {reference_file.name}")
            if st.button("Upload reference", key="upload_reference"):
                try:
                    save_upload(reference_file, REFERENCE_STORAGE)
                    with st.spinner("Uploading reference document..."):
                        data = client().ingest_reference()
                    st.session_state.reference_document_id = data["reference_id"]
                    st.session_state.reference_name = reference_file.name
                    st.success("Reference document queued for ingestion.")
                    st.rerun()
                except APIError as exc:
                    st.error(str(exc))
        if reference:
            st.success(f"Reference: {st.session_state.get('reference_name', 'Selected document')} (ID {reference})")
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="panel"><div class="step">Step 2 / Primary document</div>', unsafe_allow_html=True)
        primary_file = st.file_uploader("Upload primary document", type=["pdf", "docx"], key="primary_file")
        if primary_file:
            st.caption(f"Selected: {primary_file.name} ({primary_file.size / 1024:.1f} KB)")
            if st.button("Prepare primary document", key="upload_primary"):
                save_upload(primary_file, PRIMARY_STORAGE)
                st.session_state.primary_document_id = primary_file.name
                st.session_state.primary_name = primary_file.name
                st.session_state.primary_content = primary_file.getvalue()
                st.success("Primary document ready.")
        if primary:
            st.success(f"Primary: {st.session_state.get('primary_name', 'Selected document')}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel"><div class="step">Step 3 / Verify document</div>', unsafe_allow_html=True)
    ready = bool(reference and st.session_state.get("primary_name"))
    if st.button("Start Verification", type="primary", disabled=not ready, use_container_width=True):
        try:
            with st.spinner("Starting verification..."):
                data = client().start_verification(reference)
            st.session_state.job_id = data["job_id"]
            st.session_state.job_status = "QUEUED"
            st.rerun()
        except APIError as exc:
            st.error(str(exc))
    if not ready:
        st.info("Upload or select both documents to continue.")
    st.markdown("</div>", unsafe_allow_html=True)

    job_id = st.session_state.get("job_id")
    if not job_id:
        return
    try:
        status = client().get_job_status(job_id)
        st.session_state.job_status = status.get("status")
        show_progress(status)
        if status.get("status") not in {"COMPLETED", "FAILED"}:
            if st.button("Refresh status", key="refresh_status"):
                st.rerun()
        if status.get("status") == "FAILED":
            if st.button("Retry Verification"):
                st.session_state.pop("job_id", None)
                st.rerun()
        elif status.get("status") == "COMPLETED" or status.get("current_stage") == "done":
            data = client().get_results(job_id)
            results = data.get("results", [])
            st.session_state.verification_results = results
            st.markdown("## Verification Results")
            summary = status.get("metadata", {}).get("summary")
            critical_points = status.get("metadata", {}).get("critical_points", [])
            result_left, result_right = st.columns(2, gap="large")
            with result_left:
                st.markdown("### Primary Document")
                content = st.session_state.get("primary_content")
                if content and st.session_state.get("primary_name", "").lower().endswith(".pdf"):
                    st.pdf(content)
                else:
                    st.info(f"Primary document: {st.session_state.get('primary_name', 'Unavailable')}")
                    if content:
                        st.download_button("Download primary document", content, st.session_state.get("primary_name"), key="download_primary")
            with result_right:
                st.markdown("### Summary")
                st.write(summary or "No summary was returned by the backend.")
                st.markdown("### Critical Points")
                if critical_points:
                    for point in critical_points:
                        st.write(f"- {point.get('point', point) if isinstance(point, dict) else point}")
                else:
                    st.caption("No critical points were returned by the backend.")
            counts = {key: sum(item.get("status") == key for item in results) for key in ("SUPPORTED", "CONTRADICTED", "UNSUPPORTED")}
            st.write(f"**{len(results)} medications reviewed** | ✓ {counts['SUPPORTED']} Supported | ! {counts['CONTRADICTED']} Contradicted | ? {counts['UNSUPPORTED']} Unsupported")
            for result in results:
                show_result(result)
    except APIError as exc:
        st.warning(f"Unable to retrieve verification status. {exc}")
        st.button("Refresh status", key="status_retry")


if not st.session_state.get("authenticated"):
    login_screen()
else:
    verification_page()
