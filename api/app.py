from dotenv import load_dotenv
from flask import Flask, render_template, request
from PyPDF2 import PdfReader
import google.generativeai as genai
import os
import mysql.connector


app = Flask(__name__,static_folder="static",template_folder="templates")

# Carrega as variáveis de ambiente
load_dotenv()
api_key = os.getenv('GENAI_API_KEY')
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')


# Função para extrair texto e PDFs
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PdfReader(pdf_file)
        text = ''.join([page.extract_text() for page in pdf_reader.pages])
    return text

# Configuração do banco de dados MySQL
config = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_DATABASE'),
    'port': int(os.getenv('DB_PORT'))
}

# Cria a conexão com o banco de dados
conn = mysql.connector.connect(**config)
cursor = conn.cursor()

# Cria a tabela se ela não existir
cursor.execute("""
    CREATE TABLE IF NOT EXISTS pdf_content (
        id INT AUTO_INCREMENT PRIMARY KEY,
        filename VARCHAR(255),
        content TEXT(100000)
    )
""")

cursor.close()


# Função para carregar PDFs e inserir no banco de dados
# def carregar_pdfs(diretorio):
#     for filename in os.listdir(diretorio):
#         if filename.endswith('.pdf'):
#             pdf_path = os.path.join(diretorio, filename) 
#             text = extract_text_from_pdf(pdf_path)[:100000]

#             cursor.execute("SELECT 1 FROM pdf_content WHERE filename = %s", (filename,))
#             if cursor.fetchone() is None:
#                 cursor.execute("INSERT INTO pdf_content (filename, content) VALUES (%s, %s)", (filename, text))
#                 conn.commit()

#     cursor.execute("SELECT content FROM pdf_content")
#     return [row[0] for row in cursor]

def carregar_pdfs(diretorio):
    # Ensure the connection is open
    if not conn.is_connected():
        conn.reconnect()  # Reconnect if the connection was lost
    
    with conn.cursor() as cursor:
        for filename in os.listdir(diretorio):
            if filename.endswith('.pdf'):
                pdf_path = os.path.join(diretorio, filename) 
                text = extract_text_from_pdf(pdf_path)[:100000]

                cursor.execute("SELECT 1 FROM pdf_content WHERE filename = %s", (filename,))
                if cursor.fetchone() is None:
                    cursor.execute("INSERT INTO pdf_content (filename, content) VALUES (%s, %s)", (filename, text))
                    conn.commit()

        cursor.execute("SELECT content FROM pdf_content")
        return [row[0] for row in cursor]


# Rota para a página inicial
@app.route('/')
def index():
    return render_template('index.html')


contexto = []

system_prompt = """
    Você é um chatbot especialista em compliance. Sua função é ajudar os usuários a encontrar informações relevantes sobre compliance com base nas informaçoes que voce tem.

    **Diretrizes Gerais:**

    1. **IMPORTANTE:** Responda às perguntas de forma natural e precisa.
    2  **IMPORTANTE:** Em casos de perguntas ou informacoes pedidas sem sentido e sem contexto , faça: uma resposta para que o usuario de mais informaçoes sobre oque ele precisa.
    3. **IMPORTANTE:** Evite dar respostas vagas ou genéricas. Sempre forneça informações específicas e relevantes.
    4. **IMPORTANTE:** Não inclua nas respostas informações que não estejam nos PDFs.
    5. **IMPORTANTE:** Não crie informações falsas ou inventadas. Responda apenas com base nos dados que você possui.
    6.  **IMPORTANTE:** Não fique mensionando os PDFs.
    7. **IMPORTANTE:** Foque diretamente na informação solicitada, sem adicionar informações irrelevantes.
    8. **IMPORTANTE:** Se for solicitado um resumo, forneça um resumo conciso e direto das informações. 
    9. **IMPORTANTE:** Se não encontrar a resposta nos PDFs, indique outras fontes onde o usuário possa encontrar a informação.
    10. **IMPORTANTE:** Quando solicitado: "Me forneça mais detalhes ou informações sobre essa resposta fornecida", use o contexto da conversa e forneça mais informações relevantes que você conseguir encontrar nos PDFs.
    11. **IMPORTANTE:** Caso receba perguntas que não estejam relacionadas a compliance, responda com uma mensagem de desculpas;
    12. **IMPORTANTE:** Responda mensagens de boas-vindas de forma natural e agradável. 
    13. **IMPORTANTE:** Responda mensagens de agradecimentos de forma natural e agradável.

"""


def gerar_resposta(prompt, contexto):
    # Recupera o contexto da última resposta, se houver
    ultima_resposta = ""
    if contexto and contexto[-1].startswith("Chatbot:"):
        ultima_resposta = contexto[-1].split("Chatbot:")[1].strip()

    # Recupera o conteúdo dos PDFs do banco de dados
    pdf_content = ""
    if conn.is_connected():
        with conn.cursor() as cursor:
            cursor.execute("SELECT content FROM pdf_content")
            pdf_rows = cursor.fetchall()
            pdf_content = " ".join(row[0] for row in pdf_rows)



    # Cria o prompt baseado na última resposta e na pergunta atual
    if ultima_resposta:
        # Adiciona o contexto da última resposta e o conteúdo dos PDFs
        full_prompt = (
            f"Diretrizes Gerais:{system_prompt}\n\n"
            f"Contexto da última resposta: {ultima_resposta}\n\n"
            f"Conteúdo dos PDFs:\n{pdf_content}\n\n"
            f"Pergunta atual: {prompt}\n\n"
        )
    else:
        # Contexto inicial com o conteúdo dos PDFs
        full_prompt = (
            f"Diretrizes Gerais:{system_prompt}\n\n"
            f"Conteúdo dos PDFs:\n{pdf_content}\n\n"
            f"Pergunta atual: {prompt}\n\n"
        )
    
    # Gera a resposta usando o modelo
    response = model.generate_content(full_prompt)
    return response.text



def atualizar_contexto(contexto, pergunta, resposta, limite=5):
    """
    Atualiza o contexto da conversa com a nova pergunta e resposta.
    
    :param contexto: Lista contendo o histórico da conversa.
    :param pergunta: Pergunta atual feita pelo usuário.
    :param resposta: Resposta gerada pelo chatbot.
    :param limite: Número máximo de mensagens a manter no contexto.
    :return: Lista atualizada com o novo contexto.
    """
    # Adiciona a nova pergunta e resposta ao contexto
    contexto.append(f"Usuário: {pergunta}")
    contexto.append(f"Chatbot: {resposta}")
    
    # Limita o número de mensagens no contexto
    if len(contexto) > limite * 2:
        contexto = contexto[-limite * 2:]  # Mantém apenas as últimas mensagens

    return contexto


# Rota para o chat
@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.form.get('message')
    if user_message:
        pdfs = carregar_pdfs('api/static')
        contexto.append(f"Usuário: {user_message}")

        # Passa o contexto para a função gerar_resposta
        response = gerar_resposta(user_message, contexto)
        contexto.append(f"Chatbot: {response}")

        return response
    return "Por favor, digite uma mensagem."

if __name__ == '__main__':
    app.run(debug=True)