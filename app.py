import os
import csv
from io import StringIO
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types


# -------------------- APP SETUP --------------------

# Find and load the .env file from the same folder as app.py.
project_folder = os.path.dirname(os.path.abspath(__file__))
env_file_path = os.path.join(project_folder, ".env")
load_dotenv(env_file_path, override=True)

# Configure the browser tab and use the full page width.
st.set_page_config(
    page_title="EcoSort AI",
    page_icon="♻️",
    layout="wide",
)

# Simple CSS makes the Streamlit page look cleaner.
st.markdown(
    """
    <style>
        .main-title {
            font-size: 2.8rem;
            font-weight: 700;
            color: #1b5e20;
            margin-bottom: 0;
        }

        .subtitle {
            color: #4f6352;
            font-size: 1.1rem;
        }

.section-card {
    background-color: #262730;
    padding: 18px;
    border-radius: 10px;
    border-left: 5px solid #2e7d32;
    color: white;
    }        
    </style>
    """,
    unsafe_allow_html=True,
)


# -------------------- GEMINI FUNCTIONS --------------------

def get_gemini_client():
    """Create a Gemini client using Streamlit Secrets or .env locally."""

    api_key = ""

    # Try Streamlit Secrets first
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        api_key = os.getenv("GEMINI_API_KEY", "")

    if not api_key:
        st.error("Gemini API key not found.")
        return None

    return genai.Client(api_key=api_key)


def analyse_waste_image(uploaded_image):
    """Send the uploaded image to Gemini Vision for waste analysis."""
    client = get_gemini_client()

    if client is None:
        return None

    # Fixed output format makes the Gemini response easy to display.
    instruction = """
You are an AI assistant for EcoSort AI, an educational waste-sorting project.

Analyse the waste item in this image. Return exactly these five lines:

Category: <Plastic, Paper, Glass, Metal, Organic, E-waste, Textile, Hazardous, or Unknown>
Recyclable: <Yes, No, or Check local rules>
Disposal: <one short and practical disposal instruction>
Tip: <one short environmental tip>
Confidence: <a whole number from 0 to 100>

If the object is unclear, use Category: Unknown and give a low confidence score.
Do not add headings, greetings, bullet points, or extra lines.
"""

    # Convert the image into a format that Gemini can understand.
    image_part = types.Part.from_bytes(
        data=uploaded_image.getvalue(),
        mime_type=uploaded_image.type or "image/jpeg",
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=[instruction, image_part],
        )

        return response.text

    except Exception as error:
        # A 503 error means Gemini is temporarily overloaded.
        if "503" in str(error):
            st.warning(
                "Gemini is temporarily busy. Please wait for one minute and try again."
            )
        else:
            st.error(f"Image analysis failed: {error}")

        return None


def read_analysis_result(result_text):
    """Convert Gemini's labelled response into a dictionary."""
    result = {
        "Category": "Unknown",
        "Recyclable": "Unknown",
        "Disposal": "No disposal advice received.",
        "Tip": "Reduce, reuse, and recycle whenever possible.",
        "Confidence": "0",
    }

    # Example line: Category: Plastic
    for line in result_text.splitlines():
        if ":" in line:
            label, value = line.split(":", 1)
            label = label.strip()
            value = value.strip()

            if label in result:
                result[label] = value

    # Remove % if Gemini returns values such as 85%.
    result["Confidence"] = result["Confidence"].replace("%", "")

    # Keep only valid whole-number confidence values.
    if not result["Confidence"].isdigit():
        result["Confidence"] = "0"

    return result


def answer_chat_question(question):
    """Answer a simple waste-related question using Gemini."""
    client = get_gemini_client()

    if client is None:
        return None

    prompt = f"""
You are EcoSort AI, a helpful waste-sorting assistant.

Answer in simple language using a maximum of three short sentences.
If waste rules differ by location, tell the user to check their local authority.
Do not invent local recycling rules.

Question: {question}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )

        return response.text

    except Exception as error:
        st.error(f"Chatbot response failed: {error}")
        return None


def create_history_csv(history):
    """Create a downloadable CSV report from the analysis history."""
    output = StringIO()

    writer = csv.DictWriter(
        output,
        fieldnames=[
            "Time",
            "Category",
            "Recyclable",
            "Disposal",
            "Confidence",
            "Feedback",
            "Corrected Category",
        ],
    )

    writer.writeheader()
    writer.writerows(history)

    return output.getvalue()


# -------------------- SESSION STATE --------------------

# Session state stores data while the website is open.
if "analysis_history" not in st.session_state:
    st.session_state.analysis_history = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# -------------------- SIDEBAR --------------------

with st.sidebar:
    st.header("About EcoSort AI")

    st.write(
        "EcoSort AI uses Gemini Vision to identify common waste items "
        "and provide basic disposal guidance."
    )

    st.subheader("Project objectives")
    st.write("• Improve awareness of waste segregation")
    st.write("• Demonstrate AI-powered image classification")
    st.write("• Encourage environmentally responsible decisions")
    st.write("• Include human validation for responsible AI")

    st.subheader("Responsible AI Notice")
    st.warning(
        "This application provides educational guidance only. "
        "Always follow local municipal waste-management rules."
    )

    if st.button("Clear current session"):
        st.session_state.analysis_history = []
        st.session_state.chat_history = []

        if "latest_analysis" in st.session_state:
            del st.session_state.latest_analysis

        if "latest_history_index" in st.session_state:
            del st.session_state.latest_history_index

        st.rerun()


# -------------------- HOME PAGE --------------------

st.markdown(
    '<p class="main-title">♻️ EcoSort AI</p>',
    unsafe_allow_html=True,
)

st.markdown(
    '<p class="subtitle">'
    "AI-powered waste classification, disposal guidance, and human validation"
    "</p>",
    unsafe_allow_html=True,
)

st.divider()


# -------------------- DASHBOARD METRICS --------------------

total_analyses = len(st.session_state.analysis_history)

plastic_count = sum(
    item["Category"].lower() == "plastic"
    for item in st.session_state.analysis_history
)

recyclable_count = sum(
    item["Recyclable"].lower() == "yes"
    for item in st.session_state.analysis_history
)

validated_count = sum(
    item["Feedback"] != "Not reviewed"
    for item in st.session_state.analysis_history
)

metric_1, metric_2, metric_3, metric_4 = st.columns(4)

metric_1.metric("Images analysed", total_analyses)
metric_2.metric("Plastic items found", plastic_count)
metric_3.metric("Recyclable items", recyclable_count)
metric_4.metric("Human validations", validated_count)


# -------------------- IMAGE ANALYSIS --------------------

st.header("Waste Image Analysis")

left_column, right_column = st.columns([1, 1])

with left_column:
    input_method = st.radio(
        "Choose image source",
        ["Upload image", "Use camera"],
        horizontal=True,
    )

    if input_method == "Upload image":
        uploaded_image = st.file_uploader(
            "Upload an image of a waste item",
            type=["jpg", "jpeg", "png"],
            help="Use a clear image with one main waste item.",
        )
    else:
        uploaded_image = st.camera_input(
            "Take a photo of a waste item"
        )

    if uploaded_image is not None:
        st.image(uploaded_image, caption="Waste image", width=400)

        if st.button("Analyse Waste Item", type="primary"):
            with st.spinner("Gemini Vision is analysing the image..."):
                result_text = analyse_waste_image(uploaded_image)

            if result_text:
                analysis = read_analysis_result(result_text)

                # Store this result in the history table.
                history_item = {
                    "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Category": analysis["Category"],
                    "Recyclable": analysis["Recyclable"],
                    "Disposal": analysis["Disposal"],
                    "Confidence": analysis["Confidence"] + "%",
                    "Feedback": "Not reviewed",
                    "Corrected Category": "",
                }

                st.session_state.analysis_history.append(history_item)
                st.session_state.latest_analysis = analysis

                # Remember the position of the newest result for feedback.
                st.session_state.latest_history_index = len(
                    st.session_state.analysis_history
                ) - 1

                # Refresh so dashboard metrics update immediately.
                st.rerun()

with right_column:
    st.markdown(
        """
        <div class="section-card">
        <h4>How EcoSort AI works</h4>
        <ol>
            <li>The user uploads or captures a waste image.</li>
            <li>Gemini Vision examines the visible waste item.</li>
            <li>The system returns classification and disposal guidance.</li>
            <li>A human can validate or correct the AI result.</li>
        </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -------------------- LATEST ANALYSIS --------------------

if "latest_analysis" in st.session_state:
    analysis = st.session_state.latest_analysis

    st.subheader("Latest AI Analysis")

    result_1, result_2, result_3 = st.columns(3)

    result_1.metric("Waste category", analysis["Category"])
    result_2.metric("Recyclable status", analysis["Recyclable"])
    result_3.metric("AI confidence", analysis["Confidence"] + "%")

    st.info("Disposal instruction: " + analysis["Disposal"])
    st.success("Environmental tip: " + analysis["Tip"])

    st.caption(
        "Confidence is Gemini's estimate from the image. "
        "It is not a guarantee of correct disposal."
    )

    # -------------------- HUMAN VALIDATION --------------------

    st.subheader("Human Validation")

    st.write(
        "Verify the AI classification. This demonstrates a human-in-the-loop "
        "approach to responsible AI."
    )

    latest_index = st.session_state.get("latest_history_index")

    if (
        latest_index is not None
        and latest_index < len(st.session_state.analysis_history)
    ):
        feedback_choice = st.radio(
            "Was the AI classification correct?",
            ["Select an option", "Yes, it is correct", "No, it is incorrect"],
            key="feedback_choice",
        )

        corrected_category = st.selectbox(
            "If it was incorrect, choose the correct category",
            [
                "Not needed",
                "Plastic",
                "Paper",
                "Glass",
                "Metal",
                "Organic",
                "E-waste",
                "Textile",
                "Hazardous",
                "Unknown",
            ],
            key="corrected_category",
        )

        if st.button("Save Human Validation"):
            if feedback_choice == "Select an option":
                st.warning("Please choose whether the AI result was correct.")

            elif (
                feedback_choice == "No, it is incorrect"
                and corrected_category == "Not needed"
            ):
                st.warning("Please choose the correct waste category.")

            else:
                current_item = st.session_state.analysis_history[latest_index]

                if feedback_choice == "Yes, it is correct":
                    current_item["Feedback"] = "Correct"
                    current_item["Corrected Category"] = current_item["Category"]
                else:
                    current_item["Feedback"] = "Incorrect"
                    current_item["Corrected Category"] = corrected_category

                st.success("Human validation saved successfully.")
                st.rerun()


# -------------------- HISTORY AND REPORT --------------------

st.divider()
st.header("Analysis History")

if st.session_state.analysis_history:
    st.dataframe(
    st.session_state.analysis_history,
    width="stretch",
)

    report_csv = create_history_csv(st.session_state.analysis_history)

    st.download_button(
        label="Download analysis report (CSV)",
        data=report_csv,
        file_name="ecosort_analysis_report.csv",
        mime="text/csv",
    )
else:
    st.write("No waste images have been analysed in this session yet.")


# -------------------- CHATBOT --------------------

st.divider()
st.header("EcoSort Assistant")

st.write("Ask a simple question about recycling or waste disposal.")

chat_question = st.text_input(
    "Your question",
    placeholder="Example: Can I recycle a glass bottle?",
)

if st.button("Ask EcoSort Assistant"):
    if not chat_question.strip():
        st.warning("Please type a question first.")

    else:
        with st.spinner("EcoSort Assistant is preparing an answer..."):
            chat_answer = answer_chat_question(chat_question)

        if chat_answer:
            st.session_state.chat_history.append(
                {
                    "Question": chat_question,
                    "Answer": chat_answer,
                }
            )

# Display chatbot messages from the current session.
for message in reversed(st.session_state.chat_history):
    with st.chat_message("user"):
        st.write(message["Question"])

    with st.chat_message("assistant"):
        st.write(message["Answer"])


# -------------------- PROJECT LIMITATION --------------------

st.divider()

st.caption(
    "EcoSort AI is an educational demonstration created with Python, "
    "Streamlit, and Google Gemini Vision. AI recommendations should be "
    "verified against local waste-management rules."
)