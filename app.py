"""
Streamlit Web UI for FinPulse: AI Financial & Earnings Call Research Copilot.

Features:
- Main dashboard styled with modern, dark-mode-optimized financial terminal theme.
- Dedicated Workspace Views (isolated via sidebar navigation to prevent UI stacking):
  1. Financial Q&A Copilot: Fast text query input, sample financial queries, 
     expandable citations, and colored confidence badges.
  2. Cross-Company Guidance Comparison: Select any two corporate filings to detect
     conflicting guidance, differing CapEx outlooks, or margin divergences.
  3. Filings & Transcripts Library: Visualizes ingested financial documents, chunk counts,
     and allows uploading new quarterly reports/transcripts.
"""

import logging
import os
from pathlib import Path

# Silence harmless Streamlit file watcher warnings
logging.getLogger("streamlit.watcher.local_sources_watcher").setLevel(logging.ERROR)

import streamlit as st
import config
import rag_engine
import vector_store
from ingest import ingest_all

# Set page configuration
st.set_page_config(
    page_title="FinPulse | AI Financial & Earnings Call Copilot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Financial Terminal Dark Theme CSS
st.markdown("""
<style>
    /* Global styling */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
    }
    
    /* Header & Branding */
    .fin-brand-header {
        padding: 1.2rem 1.5rem;
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        border: 1px solid #312e81;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px -3px rgba(0, 0, 0, 0.4);
    }
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .subtitle {
        color: #94a3b8;
        font-size: 0.98rem;
        margin-bottom: 0;
    }
    
    /* Metrics summary bar */
    .metric-card {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        text-align: center;
    }
    .metric-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-label {
        font-size: 0.78rem;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Citation cards */
    .citation-card {
        background-color: #111827;
        border-left: 4px solid #38bdf8;
        border-radius: 6px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.85rem;
        border-top: 1px solid #1f2937;
        border-right: 1px solid #1f2937;
        border-bottom: 1px solid #1f2937;
    }
    .citation-header {
        font-weight: 600;
        color: #67e8f9;
        font-size: 0.88rem;
        margin-bottom: 0.35rem;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .citation-snippet {
        font-style: italic;
        color: #e2e8f0;
        font-size: 0.86rem;
        line-height: 1.45;
    }

    /* Confidence Badges */
    .confidence-high {
        background-color: #064e3b;
        color: #34d399;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 700;
        border: 1px solid #059669;
    }
    .confidence-medium {
        background-color: #78350f;
        color: #fbbf24;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 700;
        border: 1px solid #d97706;
    }
    .confidence-low {
        background-color: #7f1d1d;
        color: #f87171;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 700;
        border: 1px solid #dc2626;
    }

    /* Prompt Chips */
    .stButton>button {
        border-radius: 6px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar: Workspace Navigation & API Keys ──────────────────────────────
st.sidebar.markdown("## 📈 FinPulse Navigator")

workspace_view = st.sidebar.radio(
    "Select Workspace:",
    [
        "🔍 Financial Q&A Copilot",
        "⚖️ Cross-Company Guidance Comparison",
        "📁 Filings & Transcripts Library"
    ],
    index=0
)

st.sidebar.markdown("---")

# API Key Validation Helper
def check_api_key():
    active_key = config.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
    if not active_key:
        st.sidebar.warning("⚠️ **GROQ_API_KEY is not set**")
        st.sidebar.caption("Get a free key at [console.groq.com/keys](https://console.groq.com/keys).")
        key_input = st.sidebar.text_input("Enter Groq API Key:", type="password", key="sidebar_key_input")
        if key_input:
            key_clean = key_input.strip()
            os.environ["GROQ_API_KEY"] = key_clean
            config.GROQ_API_KEY = key_clean
            st.sidebar.success("API Key saved!")
            st.rerun()
        return False
    else:
        st.sidebar.success("✅ **LLM Engine Connected**")
        with st.sidebar.expander("🔑 Manage API Key"):
            new_key = st.text_input("New API Key:", type="password", key="new_key_input")
            if st.button("Update Key") and new_key:
                clean_new_key = new_key.strip()
                os.environ["GROQ_API_KEY"] = clean_new_key
                config.GROQ_API_KEY = clean_new_key
                st.sidebar.success("Key updated!")
                st.rerun()
        return True

has_api_key = check_api_key()

# Sidebar: Knowledge Base Stats
st.sidebar.markdown("### 📊 Database Status")
try:
    ingested_docs = rag_engine.get_available_documents()
    db_count = vector_store.get_collection_count()
except Exception:
    ingested_docs = []
    db_count = 0

st.sidebar.metric("Indexed Transcripts", len(ingested_docs))
st.sidebar.metric("Total Knowledge Chunks", db_count)

# Sidebar: Model Selector
st.sidebar.markdown("### ⚙️ Engine Settings")
selected_model = st.sidebar.selectbox(
    "Reasoning Model:",
    ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b", "groq/compound"],
    index=0,
    help="openai/gpt-oss-120b delivers top financial reasoning and strict citation extraction."
)
config.GROQ_MODEL = selected_model

if st.sidebar.button("🔄 Re-index Financial Docs"):
    with st.spinner("Re-indexing financial transcripts in docs/..."):
        try:
            ingest_all(clear_first=True)
            st.sidebar.success("Re-indexing complete!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Re-indexing failed: {e}")

st.sidebar.markdown("---")
st.sidebar.caption(f"🤖 Model: `{config.GROQ_MODEL}`")
st.sidebar.caption("⚡ Embeddings: `all-MiniLM-L6-v2`")
st.sidebar.caption("🎯 Reranker: `bge-reranker-base`")

# ── Top Brand Header ──────────────────────────────────────────────────────
st.markdown("""
<div class="fin-brand-header">
    <div class="main-title">📈 FinPulse: AI Financial & Earnings Call Research Copilot</div>
    <div class="subtitle">Institutional-grade RAG engine for SEC 10-K/10-Q filings, quarterly earnings calls, and cross-company financial benchmarking.</div>
</div>
""", unsafe_allow_html=True)

# First-time initialization banner if DB is empty
if db_count == 0:
    st.info("ℹ️ **Initial Setup Required**: The financial vector database has not been indexed yet.")
    if st.button("🚀 Initialize Financial Database (Index Built-in Transcripts)", type="primary"):
        with st.spinner("Indexing earnings reports from docs/ directory..."):
            try:
                ingest_all(clear_first=True)
                st.success("Financial documents indexed successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error initializing knowledge base: {e}")


# ══════════════════════════════════════════════════════════════════════════
# WORKSPACE VIEW 1: FINANCIAL Q&A COPILOT
# ══════════════════════════════════════════════════════════════════════════
if workspace_view == "🔍 Financial Q&A Copilot":
    st.subheader("🔍 Financial & Earnings Call Q&A")
    st.caption("Ask questions across quarterly earnings transcripts, SEC filings, segment revenues, and management guidance.")

    # High-impact sample queries for earnings calls
    sample_queries = [
        "What did NVIDIA's CFO state regarding Blackwell supply and gross margins?",
        "Compare Azure Cloud revenue growth with Google Cloud operating margins.",
        "What are Tesla's projected 2025 CapEx and Robotaxi production targets?",
        "How much did Apple's Services segment generate and what is the device installed base?"
    ]

    st.markdown("**💡 High-Impact Sample Queries:**")
    sq_cols = st.columns(len(sample_queries))
    selected_sample = None
    for idx, (col, sq) in enumerate(zip(sq_cols, sample_queries)):
        if col.button(sq, key=f"sample_{idx}"):
            selected_sample = sq

    if "current_query" not in st.session_state:
        st.session_state.current_query = ""

    if selected_sample:
        st.session_state.current_query = selected_sample

    # Clean, text-only search input
    search_col, clear_col = st.columns([5, 1])
    with search_col:
        query_input = st.text_input(
            "Enter your financial research query:",
            value=st.session_state.current_query,
            placeholder="e.g., What were Google Cloud's Q4 operating margins and revenue growth rate?",
            key="financial_query_box"
        )
    with clear_col:
        st.write("") # vertical spacing
        if st.button("✕ Clear", key="clear_query_btn"):
            st.session_state.current_query = ""
            st.rerun()

    # Submit action
    active_query = query_input.strip() if query_input else ""
    submit_clicked = st.button("🚀 Analyze & Generate Answer", type="primary", key="submit_qa_btn")
    trigger_search = (submit_clicked and active_query) or (selected_sample is not None and active_query)

    # Session state for persistent results
    if "last_query" not in st.session_state:
        st.session_state.last_query = ""
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "flagged" not in st.session_state:
        st.session_state.flagged = False

    if trigger_search and active_query:
        if not has_api_key:
            st.error("Please configure an API Key in the sidebar first.")
        else:
            with st.spinner("Retrieving financial chunks, reranking evidence, and synthesizing response..."):
                try:
                    res = rag_engine.ask(active_query)
                    st.session_state.last_query = active_query
                    st.session_state.last_result = res
                    st.session_state.flagged = False
                except Exception as e:
                    err_msg = str(e).lower()
                    if "429" in err_msg or "rate limit" in err_msg or "quota" in err_msg:
                        st.error("🛑 **API Rate Limit Exceeded**")
                        st.warning("Please wait 20-30 seconds or switch model/key in the sidebar.")
                    else:
                        st.error(f"Error analyzing query: {e}")

    # Render Q&A Result
    if st.session_state.last_result:
        res = st.session_state.last_result
        orig_q = st.session_state.last_query

        st.markdown("---")

        # Confidence level badge
        score = res.get("confidence", 0.0)
        level = res.get("confidence_level", "low")
        if level == "high":
            badge_html = f"<span class='confidence-high'>● High Confidence ({score:.2f})</span>"
        elif level == "medium":
            badge_html = f"<span class='confidence-medium'>▲ Medium Confidence ({score:.2f})</span>"
        else:
            badge_html = f"<span class='confidence-low'>■ Low Confidence ({score:.2f})</span>"

        st.markdown(f"**Evidence Grounding:** {badge_html}", unsafe_allow_html=True)

        # Answer Section
        st.markdown("### 📝 Research Synthesis")
        st.markdown(res.get("answer", "No answer generated."))

        # Low Confidence Warning & Human Review Flag
        if level == "low" or res.get("no_answer"):
            st.warning("⚠️ **Low Evidence Warning:** The available financial transcripts do not contain explicit numbers or statements to fully verify this query without extrapolation.")
            if not st.session_state.flagged:
                if st.button("📥 Flag for Financial Analyst Review", key="flag_analyst_btn"):
                    rag_engine.flag_for_review(orig_q, res["answer"], res["confidence"], res["language"])
                    st.session_state.flagged = True
                    st.success("Query and synthesis logged for analyst review.")
            else:
                st.info("✅ Flagged for Financial Analyst Review.")

        # Grounded Sources & Citations
        if res.get("citations"):
            st.markdown("### 📑 Grounded Sources & Verifiable Citations")
            for cit in res["citations"]:
                c_num = cit.get("source_number", "?")
                c_file = cit.get("source_file", "unknown")
                c_loc = cit.get("page_or_chunk", "unknown")
                c_snip = cit.get("snippet", "")

                st.markdown(f"""
                <div class="citation-card">
                    <div class="citation-header">
                        <span>📄 [Source {c_num}]</span>
                        <span><b>{c_file}</b></span>
                        <span style="color:#94a3b8;">({c_loc})</span>
                    </div>
                    <div class="citation-snippet">"{c_snip}"</div>
                </div>
                """, unsafe_allow_html=True)
        elif res.get("no_answer"):
            st.warning("System refused to answer to prevent financial hallucination. No verifiable numbers found.")


# ══════════════════════════════════════════════════════════════════════════
# WORKSPACE VIEW 2: CROSS-COMPANY GUIDANCE COMPARISON
# ══════════════════════════════════════════════════════════════════════════
elif workspace_view == "⚖️ Cross-Company Guidance Comparison":
    st.subheader("⚖️ Cross-Company Guidance & Peer Inconsistency Detection")
    st.write("Compare two corporate earnings calls to benchmark CapEx investments, cloud operating margins, AI roadmaps, or conflicting market outlooks.")

    if len(ingested_docs) < 2:
        st.warning("Please index at least 2 financial documents to perform peer comparisons.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            doc1 = st.selectbox("Select Primary Company/Filing:", ingested_docs, key="comp_doc1_select")
        with col2:
            doc2_options = [d for d in ingested_docs if d != doc1]
            doc2 = st.selectbox("Select Peer Company/Filing:", doc2_options, key="comp_doc2_select") if doc2_options else None

        topic = st.text_input(
            "Comparison Metric / Topic (Optional):",
            placeholder="e.g., AI Infrastructure CapEx, Cloud Margins, Autonomous Driving, China Revenue Exposure..."
        )

        if doc1 and doc2:
            if st.button("⚖️ Run Peer Benchmarking Analysis", type="primary", key="run_contradict_btn"):
                if not has_api_key:
                    st.error("Please configure an API Key in the sidebar first.")
                else:
                    with st.spinner("Analyzing differences, divergences, and strategic alignment between filings..."):
                        try:
                            res = rag_engine.contradict(doc1, doc2, topic)
                            if "error" in res:
                                st.error(res["error"])
                            else:
                                st.markdown("### 📊 Executive Benchmarking Summary")
                                st.write(res.get("summary", ""))

                                if res.get("has_contradiction"):
                                    st.markdown("### ⚠️ Key Divergences & Strategic Inconsistencies")
                                    for con in res.get("contradictions", []):
                                        with st.expander(f"📌 Divergence: {con.get('topic', 'Comparison')}", expanded=True):
                                            c_left, c_right = st.columns(2)
                                            with c_left:
                                                st.markdown(f"**{doc1}:**")
                                                st.info(con.get("doc1_position", "N/A"))
                                            with c_right:
                                                st.markdown(f"**{doc2}:**")
                                                st.info(con.get("doc2_position", "N/A"))
                                            st.markdown("**Analyst Synthesis on Conflict / Divergence:**")
                                            st.warning(con.get("reasoning", ""))
                                else:
                                    st.success("✅ Consistent Outlook: No conflicting claims or divergent guidance detected across the analyzed topics.")
                        except Exception as e:
                            st.error(f"Error during comparison: {e}")


# ══════════════════════════════════════════════════════════════════════════
# WORKSPACE VIEW 3: FILINGS & TRANSCRIPTS LIBRARY
# ══════════════════════════════════════════════════════════════════════════
elif workspace_view == "📁 Filings & Transcripts Library":
    st.subheader("📁 Financial Filings & Transcripts Library")
    st.write("Review all indexed earnings transcripts, view file sizes, and upload new corporate filings.")

    docs_dir = Path(config.DOCS_DIR)
    if docs_dir.exists():
        files = [f for f in docs_dir.iterdir() if f.is_file() and not f.name.startswith(".")]
        if files:
            st.markdown(f"**Currently Active Financial Documents ({len(files)} files):**")
            for f in sorted(files, key=lambda x: x.name):
                size_kb = f.stat().st_size / 1024
                ext = f.suffix.upper().replace(".", "")
                st.markdown(f"- 📄 **`{f.name}`** — `{size_kb:.1f} KB` ({ext} filing)")
        else:
            st.info("No documents found in `docs/` folder.")

    st.markdown("---")
    st.markdown("### 📤 Ingest New Quarterly Reports or Transcripts")
    st.caption("Upload additional earnings call transcripts or SEC 10-K/10-Q documents (.txt, .pdf, or .md) to expand the knowledge base.")

    uploaded_files = st.file_uploader(
        "Upload corporate documents:",
        type=["txt", "pdf", "md"],
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button(f"📥 Index {len(uploaded_files)} Uploaded Document(s)", type="primary"):
            docs_dir.mkdir(parents=True, exist_ok=True)
            saved_count = 0
            for uf in uploaded_files:
                dest = docs_dir / uf.name
                with open(dest, "wb") as out:
                    out.write(uf.getvalue())
                saved_count += 1
            
            with st.spinner(f"Parsing and embedding {saved_count} new document(s)..."):
                try:
                    ingest_all(clear_first=False)
                    st.success(f"Successfully indexed {saved_count} document(s)!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")
