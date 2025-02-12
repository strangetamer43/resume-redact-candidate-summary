import streamlit as st
from dotenv import load_dotenv
import fitz  # PyMuPDF
import re
import os
import google.generativeai as genai

load_dotenv()
# Configure Gemini API
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
# Regular expressions for detecting sensitive data
PHONE_REGEX = r'(\+?\d{1,4}[-.\s]?)?(\(?\d{1,4}\)?[-.\s]?)?(\d{3}[-.\s]?\d{3,4}[-.\s]?\d{3,4})\b'
EMAIL_REGEX = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
LINKEDIN_REGEX = r'\b(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9-]+/?\b'
DATE_REGEX = r'\b(0[1-9]|1[0-2])\s*[-/]\s*(19|20)\d{2}\b'  # Matches dates like MM/YYYY

def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF file."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"
    doc.close()
    return text

def mask_text_on_pdf(input_pdf_path, output_pdf_path):
    """Masks sensitive details in a PDF and saves the redacted version."""
    doc = fitz.open(input_pdf_path)
    
    for page in doc:
        text_instances = []
        full_text = page.get_text("text")
        
        for regex in [PHONE_REGEX, EMAIL_REGEX, LINKEDIN_REGEX]:
            for match in re.finditer(regex, full_text, re.IGNORECASE):
                if not re.match(DATE_REGEX, match.group()):  # Exclude dates
                    text_instances.append(match.group())

        for text in text_instances:
            text_rects = page.search_for(text)
            for rect in text_rects:
                page.add_redact_annot(rect, fill=(0, 0, 0))
        
        page.apply_redactions()
    
    doc.save(output_pdf_path)
    doc.close()

def generate_candidate_summary(candidate_info, resume_text):
    """Generates a structured candidate summary by merging form inputs with resume text."""
    base_prompt = f"""
    You are an experienced Technical Human Resource Manager.
    Based on the following details, structure the candidate's information:

    Name: {candidate_info.get("Name", "")}
    Education: {candidate_info.get("Education", "")}
    Total Work Experience: {candidate_info.get("Total Work Experience", "")}
    Relevant Work Experience: {candidate_info.get("Relevant Work Experience", "")}
    Companies worked for: {', '.join(candidate_info.get("Companies worked for", []))}
    Roles and responsibilities handled: {', '.join(candidate_info.get("Roles and responsibilities handled", []))}
    Current CTC: {candidate_info.get("Current CTC", "")}
    Expected CTC: {candidate_info.get("Expected CTC", "")}
    Notice period: {candidate_info.get("Notice period", "")}
    Current location: {candidate_info.get("Current location", "")}
    Reason for switch: {candidate_info.get("Reason for switch", "")}
    
    Additional extracted details from resume:
    {resume_text[:5000]}  # Limiting extracted text for context
    
    Don't share the contact details in the candidate summary. Prioritize the information shared in the Roles and responsibilities handled section. 
    
    Please format the output in a structured and professional manner.  Structure the summary in the format given below
    Name: 
    Education: 
    Total Work Experience: 
    Relevant Work Experience: 
    Companies worked for: 
    Roles and responsibilities handled: 
    Current CTC: 
    Expected CTC: 
    Notice period: 
    Current location: 
    Reason for switch: 
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(base_prompt)
    return response.text

# Streamlit UI
st.title("PDF Resume Redaction & Candidate Summary Tool")
st.write("Redact sensitive information from resumes and generate structured candidate profiles.")

uploaded_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])

if uploaded_file:
    input_pdf_path = f"temp_{uploaded_file.name}"
    with open(input_pdf_path, "wb") as f:
        f.write(uploaded_file.read())
    
    output_pdf_path = f"masked_{uploaded_file.name}"
    mask_text_on_pdf(input_pdf_path, output_pdf_path)
    
    with open(output_pdf_path, "rb") as f:
        st.download_button(label="Download Redacted Resume", data=f, file_name=output_pdf_path, mime="application/pdf")
    
    resume_text = extract_text_from_pdf(input_pdf_path)
    os.remove(input_pdf_path)
    os.remove(output_pdf_path)
else:
    resume_text = ""

st.subheader("Generate Candidate Summary")
st.write("Fill out the candidate details below, and the AI will generate a structured profile.")

with st.form("candidate_form"):
    candidate_info = {
        "Name": st.text_input("Name"),
        "Education": st.text_input("Education"),
        "Total Work Experience": st.text_input("Total Work Experience (in years)"),
        "Relevant Work Experience": st.text_input("Relevant Work Experience (in years)"),
        "Companies worked for": st.text_area("List of Companies (comma-separated)").split(","),
        "Roles and responsibilities handled": st.text_area("Roles and Responsibilities (one per line)").split("\n"),
        "Current CTC": st.text_input("Current CTC (LPA & Monthly)"),
        "Expected CTC": st.text_input("Expected CTC (LPA)"),
        "Notice period": st.text_input("Notice Period (Mention if negotiable)"),
        "Current location": st.text_input("Current Location"),
        "Reason for switch": st.text_area("Reason for switching job"),
    }
    submit_button = st.form_submit_button("Generate Summary")

if submit_button:
    summary = generate_candidate_summary(candidate_info, resume_text)
    st.subheader("Generated Candidate Summary")
    st.text_area("Summary", summary, height=400)
