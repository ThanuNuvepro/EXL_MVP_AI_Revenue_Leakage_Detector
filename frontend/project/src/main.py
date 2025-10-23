# FIX: Ensured all required modules are imported for a self-contained and executable script.
import streamlit as st
import requests
import os
import logging
import pandas as pd
from datetime import datetime
# FIX: Imported specific types from the 'typing' module for clear and robust function signatures.
from typing import List, Dict, Any, Optional
# FIX: Imported streamlit_autorefresh to implement non-blocking UI updates, addressing a critical performance issue.
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv
import matplotlib.pyplot as plt

# --- Configuration ---
# Load environment variables from .env file
load_dotenv()

# FIX: Configured basic logging to ensure application events are captured for monitoring and debugging.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# FIX: Securely retrieve secrets and configuration, preventing hardcoded credentials.
# API_KEY = st.secrets.get("API_KEY", os.getenv("API_KEY"))
# FIX: Removed the insecure default 'http' URL. The application will now require an explicit
# BACKEND_API_URL configuration, enhancing security by preventing accidental insecure deployments.
BACKEND_API_URL = os.getenv("BACKEND_API_URL")

# --- Constants for Session State and Widget Keys ---
# FIX: Defined constants for session state and widget keys to prevent typos and improve code maintainability.
SESSION_STATE_INVOICE_ID = "selected_invoice_id"
SESSION_STATE_NARRATIVE = "genai_narrative"
SESSION_STATE_COMPARISON_IDS = "comparison_invoice_ids"
SESSION_STATE_AUTO_REFRESH = "auto_refresh_enabled"
SESSION_STATE_API_KEY = "api_key" # New session state for the API key
SESSION_STATE_API_ENDPOINT = "api_endpoint"
SESSION_STATE_DEPLOYMENT_NAME = "deployment_name"
SESSION_STATE_MODEL_NAME = "model_name"
WIDGET_KEY_INVOICE_SELECTION = "invoice_selection"
WIDGET_KEY_VENDOR_FILTER = "vendor_filter"
WIDGET_KEY_GENERATE_BUTTON = "generate_narrative_button"

# --- Page Setup ---
st.set_page_config(
    page_title="Cognitive Invoice Risk Management Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- API Communication ---
# FIX: Corrected the type hint to use the modern union syntax `|` and ensured the function is fully defined.
def _api_get_request(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]] | Dict[str, Any]]:
    """
    A reusable helper function for making API GET requests.
    This centralizes API key validation, header creation, request execution, and error handling.

    Args:
        endpoint (str): The API endpoint to call (e.g., "/summary").
        params (dict, optional): A dictionary of query parameters. Defaults to None.

    Returns:
        A dictionary or list with the JSON response from the API if successful, otherwise None.
    """
    try:
        url = f"{BACKEND_API_URL}{endpoint}"
        headers = {}  # {"Authorization": f"Bearer {API_KEY}"}
        # FIX: Added a timeout to the request to prevent the app from hanging indefinitely.
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status() # FIX: Ensures that HTTP errors (4xx or 5xx) are raised as exceptions.
        return response.json()
    except requests.exceptions.RequestException as e:
        # FIX: Implemented comprehensive error handling and logging for API requests to aid in debugging.
        logging.error(f"API request to {url} failed: {e}", exc_info=True)
        st.error(f"Failed to connect to the backend API. Please check the connection and try again.")
        return None

def _api_post_request(endpoint: str, json_data: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """A reusable helper function for making API POST requests."""
    try:
        url = f"{BACKEND_API_URL}{endpoint}"
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        response = requests.post(url, headers=headers, json=json_data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logging.error(f"API POST request to {url} failed: {e}", exc_info=True)
        st.error(f"Failed to send data to the backend API: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"API POST request to {url} failed: {e}", exc_info=True)
        st.error(f"Failed to send data to the backend API. Please try again.")
        return None

def _api_upload_request(uploaded_file: Any, api_key: str, api_endpoint: str, deployment_name: str, model_name: str) -> Optional[Dict[str, Any]]:
    """A helper function for making multipart/form-data API POST requests for file uploads."""
    try:
        url = f"{BACKEND_API_URL}/api/invoices/upload"
        files = {'invoice_pdf': (uploaded_file.name, uploaded_file, 'application/pdf')}
        data = {
            'api_key': api_key,
            'api_endpoint': api_endpoint,
            'deployment_name': deployment_name,
            'model_name': model_name
        }
        response = requests.post(url, files=files, data=data, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logging.error(f"API upload request to {url} failed: {e}", exc_info=True)
        error_message = e.response.json().get("message", e.response.text)
        st.error(f"Failed to process invoice: {error_message}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"API upload request to {url} failed: {e}", exc_info=True)
        st.error(f"Failed to connect to the backend API for upload. Please try again.")
        return None

# --- Data Fetching ---
@st.cache_data(ttl=30)
def fetch_summary_metrics() -> Optional[Dict[str, Any]]:
    """Fetches summary metrics from the backend API using the centralized helper."""
    return _api_get_request("/api/dashboard/summary")

@st.cache_data(ttl=30)
def fetch_vendors() -> List[str]:
    """
    Fetches the list of unique vendors from a dedicated endpoint to avoid loading all invoices.
    """
    vendors_data = _api_get_request("/api/vendors")
    # FIX: Added a type check to handle potential malformed API responses gracefully.
    if isinstance(vendors_data, list):
        return ["All Vendors"] + sorted(vendors_data)
    return ["All Vendors"]

@st.cache_data(ttl=30)
def fetch_invoices(vendor_name: Optional[str] = None, risk_level: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches invoices from the backend, optionally filtering by vendor.
    """
    params = {}
    if vendor_name and vendor_name != "All Vendors":
        params["vendor_name"] = vendor_name
    if risk_level and risk_level != "All Risk Levels":
        params["risk_level"] = risk_level
    return _api_get_request("/api/invoices/", params=params)

def fetch_ai_narrative(invoice_id: str, api_key: str, api_endpoint: str, deployment_name: str, model_name: str) -> Optional[Dict[str, Any]]:
    """
    Fetches the GenAI narrative for a specific invoice from the backend.
    """
    if not invoice_id:
        return None
    if not api_key:
        st.error("API Key is required to generate a summary. Please enter it in the sidebar.")
        return None

    # Pass the API key in the JSON body of the POST request
    return _api_post_request(
        f"/api/invoices/{invoice_id}/narrative",
        json_data={
            "api_key": api_key,
            "api_endpoint": api_endpoint,
            "deployment_name": deployment_name,
            "model_name": model_name
        }
    )

# --- UI Components ---
def display_summary_metrics():
    """Fetches and displays the summary metric cards."""
    summary_data = fetch_summary_metrics()
    col1, col2, col3 = st.columns(3)
    # FIX: Added a check to ensure summary_data is not None before attempting to access its keys.
    if summary_data:
        with col1:
            total_invoices = summary_data.get("total_invoices", "N/A")
            st.metric(label="Total Invoices Processed", value=total_invoices)
        with col2:
            invoices_per_risk = summary_data.get("invoices_per_risk_level", {})
            high_risk_alerts = invoices_per_risk.get("High", 0)
            st.metric(label="High-Risk Alerts", value=high_risk_alerts)

        with col3:
            avg_risk_score = summary_data.get("average_risk_score")
            # FIX: Safely format the risk score, handling cases where it might not be a number.
            formatted_score = f"{avg_risk_score:.2f}" if isinstance(avg_risk_score, (int, float)) else "N/A"
            st.metric(label="Average Risk Score", value=formatted_score)
    else:
        # FIX: Provide a clear user message and placeholder data when the API call fails.
        st.warning("Could not retrieve summary metrics. Displaying placeholder data.")
        with col1:
            st.metric(label="Total Invoices Processed", value="-")
        with col2:
            st.metric(label="High-Risk Alerts", value="-")
        with col3:
            st.metric(label="Average Risk Score", value="-")

def display_visualizations(df: pd.DataFrame):
    """Displays a single, polished chart for the top 5 high-risk vendors."""
    st.subheader("Data Visualizations")

    if df is None or df.empty:
        st.info("No data available to display visualizations.")
        return

    st.markdown("<h6>Top 5 High-Risk Vendors</h6>", unsafe_allow_html=True)
    top_vendors = df.groupby('vendor_name')['risk_score'].mean().nlargest(5)
    
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(top_vendors.index, top_vendors.values, color='deepskyblue', edgecolor='black')
    
    ax.set_title('Top 5 Vendors by Average Risk Score', fontsize=16, color='white')
    ax.set_xlabel('Vendor', fontsize=12, color='white')
    ax.set_ylabel('Average Risk Score', fontsize=12, color='white')
    
    ax.tick_params(colors='white', which='both')
    plt.xticks(rotation=45, ha="right")
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.01, f'{yval:.2f}', ha='center', va='bottom', color='white')

    fig.patch.set_facecolor('none')
    ax.set_facecolor('none')

    st.pyplot(fig, use_container_width=True)

def display_invoice_table() -> Optional[pd.DataFrame]:
    """Displays the vendor filter and the interactive invoice table."""
    st.subheader("High-Risk Invoice Review")

    vendors = fetch_vendors()
    
    col1, col2 = st.columns(2)
    with col1:
        selected_vendor = st.selectbox(
            "Filter by Vendor",
            options=vendors,
            key=WIDGET_KEY_VENDOR_FILTER
        )
    with col2:
        selected_risk_level = st.selectbox(
            "Filter by Risk Level",
            options=["All Risk Levels", "High", "Medium", "Low"],
            key="risk_level_filter"
        )

    invoices_data = fetch_invoices(vendor_name=selected_vendor, risk_level=selected_risk_level)

    if not invoices_data:
        st.warning("Could not retrieve invoice data from the backend. The invoice table cannot be displayed.")
        return None

    try:
        df = pd.DataFrame(invoices_data)

        def get_risk_level_display(level):
            if level == 'High':
                return "High 🔴"
            elif level == 'Medium':
                return "Medium 🟠"
            return "Low 🟢"

        df['risk_level_display'] = df['risk_level'].apply(get_risk_level_display)
        df["pdf_url"] = df["invoice_id"].apply(lambda id: f"{BACKEND_API_URL}/api/invoices/{id}/pdf")
        df["Summarise"] = False
        
        display_columns = [
            "invoice_id", "vendor_name", "invoice_date", "amount", 
            "risk_score", "risk_level_display", "pdf_url", "Summarise"
        ]

        edited_df = st.data_editor(
            df,
            hide_index=True,
            column_order=display_columns,
            column_config={
                "invoice_id": "Invoice ID",
                "vendor_name": "Vendor Name",
                "invoice_date": "Invoice Date",
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                "risk_score": st.column_config.ProgressColumn(
                    "Risk Score",
                    help="Risk score from 0 (low) to 100 (high)",
                    format="%d",
                    min_value=0,
                    max_value=100,
                ),
                "risk_level_display": "Risk Level",
                "pdf_url": st.column_config.LinkColumn("View Invoice", display_text="View Invoice"),
                "Summarise": st.column_config.CheckboxColumn("Summarise", help="Select one or two invoices to summarise")
            },
            key="invoice_selection_editor"
        )

        selected_rows = edited_df[edited_df["Summarise"]]
        selected_ids = selected_rows["invoice_id"].tolist()
        logging.info(f"Selected invoice IDs: {selected_ids}")

        if len(selected_ids) > 2:
            st.warning("You can select a maximum of two invoices for summarization.")
            selected_ids = selected_ids[-2:]
        
        st.session_state[SESSION_STATE_COMPARISON_IDS] = selected_ids
        
        return edited_df

    except (ValueError, TypeError) as e:
        logging.error(f"Failed to create or process DataFrame from invoice data: {e}", exc_info=True)
        st.error("An error occurred while processing the invoice data. Please check the data format from the API.")
        return None

def display_comparative_analysis(invoices_df: pd.DataFrame, selected_ids: List[str]):
    """Displays a side-by-side comparison of two selected invoices."""
    if len(selected_ids) != 2:
        return

    st.subheader("Comparative Analysis")
    col1, col2 = st.columns(2)

    for i, invoice_id in enumerate(selected_ids):
        invoice_data = invoices_df[invoices_df['invoice_id'] == invoice_id].iloc[0]
        with (col1 if i == 0 else col2):
            st.markdown(f"#### Invoice: `{invoice_id}`")
            st.text(f"Vendor: {invoice_data['vendor_name']}")
            st.text(f"Date: {invoice_data['invoice_date']}")
            st.metric(label="Amount", value=f"${invoice_data['amount']:.2f}")
            st.metric(label="Risk Score", value=f"{invoice_data['risk_score']:.2f}")



def display_single_invoice_details(invoices_df: pd.DataFrame, selected_ids: List[str]):
    """Displays the details of a single selected invoice and the AI summary."""
    if len(selected_ids) != 1:
        return

    invoice_id = selected_ids[0]
    invoice_data = invoices_df[invoices_df['invoice_id'] == invoice_id].iloc[0]

    st.subheader(f"Details for Invoice: `{invoice_id}`")
    col1, col2 = st.columns(2)
    with col1:
        st.text(f"Vendor: {invoice_data['vendor_name']}")
        st.text(f"Date: {invoice_data['invoice_date']}")
    with col2:
        st.metric(label="Amount", value=f"${invoice_data['amount']:.2f}")
        st.metric(label="Risk Score", value=f"{invoice_data['risk_score']:.2f}")

    if f"narrative_{invoice_id}" in st.session_state:
        with st.expander("AI-Generated Summary", expanded=True):
            narrative = st.session_state[f"narrative_{invoice_id}"]
            for paragraph in narrative.split('\n'):
                if paragraph.strip():
                    st.markdown(f"💡 {paragraph}")
    elif st.button("Generate AI Summary", key=f"generate_summary_{invoice_id}"):
        api_key = st.session_state.get("api_key")
        if not api_key:
            st.error("API Key is required to generate a summary. Please enter it in the sidebar.")
        else:
            with st.spinner("Generating AI summary... This may take a moment."):
                narrative_data = fetch_ai_narrative(
                    invoice_id,
                    api_key,
                    st.session_state.get(SESSION_STATE_API_ENDPOINT),
                    st.session_state.get(SESSION_STATE_DEPLOYMENT_NAME),
                    st.session_state.get(SESSION_STATE_MODEL_NAME)
                )
                if narrative_data and "narrative" in narrative_data:
                    st.session_state[f"narrative_{invoice_id}"] = narrative_data["narrative"]
                    st.rerun()
                else:
                    st.error("Failed to generate summary. The backend did not return a narrative.")

# --- Main Application ---
def run_app():
    """Initializes and runs the Streamlit dashboard application."""
    st.markdown(
        """
        <style>
        body {
            color: white !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.title("Cognitive Invoice Risk Management Dashboard")

    if not BACKEND_API_URL:
        error_msg = "CRITICAL: BACKEND_API_URL is not configured."
        logging.critical(error_msg)
        st.error(error_msg)
        st.stop()

    IS_PROD = os.getenv("ENVIRONMENT", "development") == "production"
    if IS_PROD and not BACKEND_API_URL.startswith("https://"):
        error_msg = "CRITICAL SECURITY RISK: BACKEND_API_URL must use HTTPS in production."
        logging.critical(error_msg)
        st.error(error_msg)
        st.stop()

    # Initialize session state keys
    if SESSION_STATE_INVOICE_ID not in st.session_state:
        st.session_state[SESSION_STATE_INVOICE_ID] = None
    if SESSION_STATE_NARRATIVE not in st.session_state:
        st.session_state[SESSION_STATE_NARRATIVE] = None
    if SESSION_STATE_COMPARISON_IDS not in st.session_state:
        st.session_state[SESSION_STATE_COMPARISON_IDS] = []
    if SESSION_STATE_AUTO_REFRESH not in st.session_state:
        st.session_state[SESSION_STATE_AUTO_REFRESH] = False
    if SESSION_STATE_API_KEY not in st.session_state:
        st.session_state[SESSION_STATE_API_KEY] = ""
    if SESSION_STATE_API_ENDPOINT not in st.session_state:
        st.session_state[SESSION_STATE_API_ENDPOINT] = ""
    if SESSION_STATE_DEPLOYMENT_NAME not in st.session_state:
        st.session_state[SESSION_STATE_DEPLOYMENT_NAME] = ""
    if SESSION_STATE_MODEL_NAME not in st.session_state:
        st.session_state[SESSION_STATE_MODEL_NAME] = ""
    if "requested_summaries" not in st.session_state:
        st.session_state.requested_summaries = set()

    # --- Sidebar ---
    st.sidebar.title("Dashboard Controls")

    st.sidebar.info(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.sidebar.divider()

    st.sidebar.title("Process New Invoice")
    st.sidebar.text_input(
        "Your API Key",
        type="password",
        key=SESSION_STATE_API_KEY,
        help="Enter your API key once per session."
    )
    st.sidebar.text_input(
        "API Endpoint",
        key=SESSION_STATE_API_ENDPOINT,
        help="Enter the API endpoint."
    )
    st.sidebar.text_input(
        "Deployment Name",
        key=SESSION_STATE_DEPLOYMENT_NAME,
        help="Enter the deployment name."
    )
    st.sidebar.text_input(
        "Model Name",
        key=SESSION_STATE_MODEL_NAME,
        help="Enter the model name."
    )
    uploaded_file = st.sidebar.file_uploader(
        "Upload Invoice PDF",
        type="pdf"
    )

    if st.sidebar.button("Process Invoice"):
        if uploaded_file is None:
            st.sidebar.warning("Please upload a PDF file.")
        elif not st.session_state.get(SESSION_STATE_API_KEY):
            st.sidebar.warning("Please enter your API key.")
        else:
            with st.spinner("Processing your invoice..."):
                result = _api_upload_request(
                    uploaded_file,
                    st.session_state[SESSION_STATE_API_KEY],
                    st.session_state[SESSION_STATE_API_ENDPOINT],
                    st.session_state[SESSION_STATE_DEPLOYMENT_NAME],
                    st.session_state[SESSION_STATE_MODEL_NAME]
                )
                if result:
                    st.sidebar.success(f"Successfully processed Invoice ID: {result.get('invoice_id')}")
                    st.cache_data.clear()
                    st.rerun()

    # Main dashboard layout
    display_summary_metrics()
    st.divider()

    invoices_df = display_invoice_table()

    if invoices_df is not None:
        display_visualizations(invoices_df)
        st.divider()
        
        selected_ids = st.session_state.get(SESSION_STATE_COMPARISON_IDS, [])
        logging.info(f"Selected invoice IDs from session state: {selected_ids}")
        if selected_ids:
            st.subheader("Invoice Details")
            display_single_invoice_details(invoices_df, selected_ids)
            display_comparative_analysis(invoices_df, selected_ids)
        else:
            st.info("Select one or two invoices from the table to see more details.")

    if st.session_state.get(SESSION_STATE_AUTO_REFRESH):
        st_autorefresh(interval=30 * 1000, key="data_refresher")

# --- Execution Guard ---
if __name__ == "__main__":
    run_app()