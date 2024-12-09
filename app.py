from flask import Flask,request,render_template,send_file
import os
import pdfplumber
import docx
import csv
from werkzeug.utils import secure_filename
import google.generativeai as genai
from fpdf import FPDF
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment variable
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("No API key found. Please set GOOGLE_API_KEY environment variable.")

# Configure Gemini
genai.configure(api_key=api_key)
model = genai.GenerativeModel("models/gemini-1.5-pro")


app = Flask(__name__)
app.config["UPLOAD_FOLDERS"]="uploads/"
app.config["RESULTS_FOLDER"]="results/"
app.config["ALLOWED_EXTENSION"]={"pdf","txt","docx"}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in app.config["ALLOWED_EXTENSION"]

def extract_text_from_file(file_path):
    ext=file_path.rsplit('.',1)[1].lower()
    if ext=="pdf":
        with pdfplumber.open(file_path) as pdf:
            text ='\n'.join([page.extract_text() for page in pdf.pages])
        return text
    elif ext=="docx":
        doc = docx.Document(file_path)
        text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
        return text
    elif ext=="txt":
        with open(file_path,"r") as file:
            text = file.read()
        return text
    return None

def Questions_mcqs_generator(input_text,num_questions):
    prompt =f"""You are an AI assistant helping the user generate multiple-choice questions (MCQs) based on the following text:
    '{input_text}'
    Please generate {num_questions} MCQs from the text. Each question should have:
    - A clear question
    - Four answer options (labeled A, B, C, D)
    - The correct answer clearly indicated
    Format:
    ## MCQ
    Question: [question]
    A) [option A]
    B) [option B]
    C) [option C]
    D) [option D]
    Correct Answer: [correct option]
    """
    response = model.generate_content(prompt).text.strip()
    return response

def save_mcqs_to_file(mcqs,filename):
    result_path =os.path.join(app.config["RESULTS_FOLDER"],filename)

    with open(result_path,"w") as f:
        f.write(mcqs)

    return result_path


def create_pdf(mcqs,filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial",size=12)
    for mcq in mcqs.split("##MCQ"):
        if mcq.strip():
            pdf.multi_cell(0,10,mcq.strip())
            pdf.ln(5)
    pdf_path =os.path.join(app.config['RESULTS_FOLDER'],filename)
    pdf.output(pdf_path)
    return pdf_path


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate",methods=["POST"])
def generate():
    if 'file' not in request.files:
        return "No file part",400
    file = request.files['file']
    

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDERS"],filename)
        file.save(file_path)
        text =extract_text_from_file(file_path)

        if text:
            num_questions =int(request.form.get("num_questions"))
            mcqs=Questions_mcqs_generator(text,num_questions)
            txt_filename = f"generated_mcqs_{filename.rsplit('.',1)[0]}.txt"
            pdf_filename = f"generated_mcqs_{filename.rsplit('.',1)[0]}.pdf"
            save_mcqs_to_file(mcqs,txt_filename)
            create_pdf(mcqs,pdf_filename)
            
            return render_template("results.html",mcqs=mcqs,txt_filename=txt_filename,pdf_filename=pdf_filename)
        return "INVALID FILE FORMAT"
    
@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(app.config["RESULTS_FOLDER"],filename)
    return send_file(file_path,as_attachment=True)
    


if __name__ == "__main__":
    if not os.path.exists(app.config["UPLOAD_FOLDERS"]):
        os.makedirs(app.config["UPLOAD_FOLDERS"])
    if not os.path.exists(app.config["RESULTS_FOLDER"]):
        os.makedirs(app.config["RESULTS_FOLDER"])
        
    app.run(debug=True)
