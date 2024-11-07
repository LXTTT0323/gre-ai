from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import pytesseract
from PIL import Image
from io import BytesIO
from openai import OpenAI
from functools import lru_cache
import json
import logging

# 配置 Tesseract OCR 路径（对于 Windows）
#os.environ['TESSDATA_PREFIX'] = r'C:\Program Files\Tesseract-OCR\tessdata'
#pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# 初始化 FastAPI app
app = FastAPI()

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "https://gre-ai-cbdb67695e84.herokuapp.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 OpenAI 客户端
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 定义问题输入的 Pydantic 模型
class Question(BaseModel):
    query: str

# 向 GPT 提问的端点
@app.post("/ask")
async def ask_gpt(question: Question):
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": question.query}],
            max_tokens=150,
            temperature=0.7
        )
        return {"answer": response.choices[0].message.content}
    except Exception as e:
        print(f"Error in ask_gpt: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 分析图像并回答问题的端点
@app.post("/analyze-image")
async def analyze_image(file: UploadFile = File(...), question: str = Form(...)):
    try:
        contents = await file.read()
        image = Image.open(BytesIO(contents))
        try:
            extracted_text = preprocess_gre_text(pytesseract.image_to_string(image))
        except Exception as e:
            logging.error(f"Tesseract error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Tesseract error: {str(e)}")
        
        gre_prompt = f"""
        You are an expert GRE tutor. Analyze the following GRE question and provide a detailed explanation:

        Question: {question}

        Question text from image:
        {extracted_text}

        Please provide your analysis in the following format:

        1. Correct Answer:
           - State the correct answer(s)
           - Explain why this is correct, referencing specific parts of the passage

        2. Step-by-step Explanation:
           - Break down the reasoning process
           - Highlight key phrases or concepts from the passage that lead to the answer

        3. Key Concepts and Strategies:
           - Identify the main concepts tested in this question
           - Provide strategies for approaching similar questions

        4. Common Mistakes to Avoid:
           - List potential misinterpretations or traps
           - Explain why these are incorrect

        5. Follow-up Discussion:
           - Pose 1 related questions to deepen understanding
           - Provide brief answers to these follow-up questions

        Ensure all explanations are based strictly on the information provided in the passage. If there's ambiguity, acknowledge it and explain potential interpretations.
        """
        
        answer = get_gpt_response(gre_prompt)
        return {"answer": answer}
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 分析 GRE verbal 问题的端点
@app.post("/analyze-gre-verbal")
async def analyze_gre_verbal(
    file: UploadFile = File(...), 
    question: str = Form(...), 
    conversation_history: str = Form(default="[]")
):
    try:
        contents = await file.read()
        image = Image.open(BytesIO(contents))
        try:
            extracted_text = preprocess_gre_text(pytesseract.image_to_string(image))
            logger.info(f"Extracted text: {extracted_text}")
        except Exception as e:
            logger.error(f"Tesseract error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Tesseract error: {str(e)}")
        
        conversation = json.loads(conversation_history)
        
        prompt = create_gre_prompt(extracted_text, question, conversation)
        
        response = get_gpt_response(prompt)
        
        logger.info(f"Question: {question}")
        logger.info(f"GPT Response: {response}")
        
        return HTMLResponse(content=response, status_code=200)
    except Exception as e:
        logger.error(f"Error in analyze_gre_verbal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 分析 GRE quant 问题的端点
@app.post("/analyze-gre-quant")
async def analyze_gre_quant(file: UploadFile = File(...), question: str = Form(...)):
    try:
        contents = await file.read()
        image = Image.open(BytesIO(contents))
        try:
            extracted_text = preprocess_gre_text(pytesseract.image_to_string(image))
        except Exception as e:
            logging.error(f"Tesseract error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Tesseract error: {str(e)}")
        
        quant_prompt = f"""
        As an expert GRE quantitative tutor, analyze the following GRE math question:

        Question: {question}

        Question text from image:
        {extracted_text}

        Please provide your analysis in the following structured format:

        1. Correct Answer:
           - State the correct answer
           - Briefly explain why it's correct

        2. Step-by-step Solution:
           - Break down the problem-solving process
           - Show all work and calculations
           - Explain each step clearly

        3. Key Mathematical Concepts:
           - List the main mathematical concepts involved
           - Briefly explain how they apply to this problem

        4. Alternative Solution Methods:
           - If applicable, provide other ways to solve the problem
           - Explain the pros and cons of each method

        5. Common Mistakes and Pitfalls:
           - Identify potential errors students might make
           - Explain how to avoid these mistakes

        6. Time-saving Tips:
           - Provide strategies for solving this type of problem quickly
           - Mention any relevant shortcuts or estimation techniques

        7. Similar Practice Question:
           - Provide a new quantitative question of similar difficulty and type
           - Include the correct answer and a brief explanation

        Format each section with clear headings and use bullet points or numbering for clarity. Use LaTeX notation for mathematical expressions where appropriate.
        """
        
        response = get_gpt_response(quant_prompt)
        return {"answer": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 分析 GRE writing 问题的端点
@app.post("/analyze-gre-writing")
async def analyze_gre_writing(file: UploadFile = File(...), question: str = Form(...)):
    try:
        contents = await file.read()
        image = Image.open(BytesIO(contents))
        try:
            extracted_text = preprocess_gre_text(pytesseract.image_to_string(image))
        except Exception as e:
            logging.error(f"Tesseract error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Tesseract error: {str(e)}")
        
        writing_prompt = f"""
        As an expert GRE analytical writing tutor, analyze the following GRE writing prompt:

        Prompt: {question}

        Prompt text from image:
        {extracted_text}

        Please provide your analysis in the following structured format:

        1. Prompt Analysis:
           - Identify the type of essay required (Issue or Argument)
           - List key elements to address in the response
           - Explain the main focus or challenge of this prompt

        2. Essay Structure:
           - Provide a suggested outline for a high-scoring essay, including:
             a) Introduction with a clear thesis statement
             b) Main body paragraphs with topic sentences and key points
             c) Conclusion

        3. Key Arguments and Examples:
           - List potential arguments or examples to include
           - Explain how they support the essay's main points

        4. Common Pitfalls:
           - Identify typical mistakes in GRE writing tasks
           - Provide tips on how to avoid these issues

        5. Time Management:
           - Offer a suggested time breakdown for planning, writing, and reviewing
           - Include strategies for efficient writing within the time constraint

        6. Writing Style Tips:
           - Provide advice on improving clarity and coherence
           - Suggest ways to demonstrate sophisticated writing skills

        7. Sample Paragraph:
           - Write a brief example paragraph demonstrating effective writing for this prompt
           - Explain the strengths of this paragraph

        Format each section with clear headings and use bullet points or numbering for clarity.
        """
        
        response = get_gpt_response(writing_prompt)
        return {"answer": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def create_gre_prompt(extracted_text, question, conversation, correct_answer=None):
    conversation_context = "\n".join([f"{item['role']}: {item['content']}" for item in conversation])
    
    correct_answer_prompt = f"\nThe user has indicated that the correct answer is: {correct_answer}" if correct_answer else ""
    
    prompt = f"""
    You are an expert GRE tutor. Analyze the following GRE question and provide a detailed explanation.
    Take into account the entire conversation history when formulating your response.
    {correct_answer_prompt}

    Image text:
    {extracted_text}

    Conversation history:
    {conversation_context}

    Current question: {question}

    Please provide your analysis in the following format:

    <h2>1. Correct Answer</h2>
    State the correct answer(s) for each blank or part of the question. If the user has provided a correct answer, acknowledge it and explain why it's correct.

    <h2>2. Explanation</h2>
    Provide a detailed explanation of the answer, including:
    - The meaning of the correct words
    - How they fit into the context of the sentence or passage
    - Why other options are incorrect (if applicable)
    - Any relevant grammatical or vocabulary rules

    <h2>3. Key Concepts and Strategies</h2>
    <ul>
      <li>Identify the main concepts tested in this question</li>
      <li>Provide strategies for approaching similar questions</li>
    </ul>

    <h2>4. Common Mistakes to Avoid</h2>
    <ul>
      <li>List potential misinterpretations or traps</li>
      <li>Explain why these are incorrect</li>
    </ul>

    <h2>5. Practice and Improvement</h2>
    <ul>
      <li>Suggest related areas the user might want to study further</li>
      <li>Provide a similar practice question or scenario to reinforce the concept</li>
    </ul>

    Ensure your response is coherent with the entire conversation history and builds upon previous explanations.
    Use appropriate HTML tags to structure your response for better readability.
    """
    
    return prompt

def preprocess_gre_text(extracted_text: str) -> str:
    replacements = {
        '×': '*',
        '÷': '/',
        '—': '-',
    }
    for old, new in replacements.items():
        extracted_text = extracted_text.replace(old, new)
    
    extracted_text = ''.join(char for char in extracted_text if ord(char) < 128)
    
    return extracted_text

@lru_cache(maxsize=100)
def get_gpt_response(prompt: str):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful GRE tutor assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.7
    )
    return response.choices[0].message.content

# 提供静态文件（前端文件）
frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 当脚本直接执行时使用 Uvicorn 运行 FastAPI 应用
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.get("/tesseract-version")
def get_tesseract_version():
    try:
        version = pytesseract.get_tesseract_version()
        return {"version": version}
    except Exception as e:
        logger.error(f"Error getting Tesseract version: {str(e)}")
        return {"error": str(e)}
