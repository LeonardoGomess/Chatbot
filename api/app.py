from dotenv import load_dotenv
from flask import Flask, render_template, request
from PyPDF2 import PdfReader
import google.generativeai as genai
import os
import psycopg2  # Biblioteca para PostgreSQL
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

app = Flask(__name__, static_folder="static", template_folder="templates")
model_embedding = SentenceTransformer('all-MiniLM-L6-v2')

# Carrega as variáveis de ambiente
load_dotenv()
api_key = os.getenv('GENAI_API_KEY')
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')


def vetorizar_texto(texto):
    return model_embedding.encode(texto)

# Função para extrair texto de PDFs
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PdfReader(pdf_file)
        text = ''.join([page.extract_text() for page in pdf_reader.pages])
    return text

# Configuração do banco de dados PostgreSQL
config = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'dbname': os.getenv('DB_DATABASE'),  # PostgreSQL usa 'dbname' ao invés de 'database'
    'port': int(os.getenv('DB_PORT'))
}

# Cria a conexão com o banco de dados PostgreSQL
conn = psycopg2.connect(**config)
conn.autocommit = True  # Habilita commit automático para cada operação
cursor = conn.cursor()

# Cria a tabela se ela não existir
cursor.execute("""
CREATE TABLE IF NOT EXISTS pdf_content (
    id SERIAL PRIMARY KEY,  -- SERIAL em vez de AUTO_INCREMENT
    filename VARCHAR(255),
    content TEXT,
    vector TEXT  -- PostgreSQL lida com TEXT sem o limite como no MySQL
)
""")

cursor.close()


def carregar_pdfs(diretorio):
    # Certifique-se de que a conexão está aberta
    if conn.closed:
        conn.reset()

    with conn.cursor() as cursor:
        for filename in os.listdir(diretorio):
            if filename.endswith('.pdf'):
                pdf_path = os.path.join(diretorio, filename)
                
                # Extração e vetorização
                text = extract_text_from_pdf(pdf_path)[:100000]
                vetor = vetorizar_texto(text)  # Vetoriza o conteúdo do PDF

                if vetor is not None and len(vetor) > 0:
                    vetor_str = ','.join(map(str, vetor.tolist()))
                    cursor.execute("SELECT 1 FROM pdf_content WHERE filename = %s", (filename,))
                    if cursor.fetchone() is None:
                        cursor.execute(
                            "INSERT INTO pdf_content (filename, content, vector) VALUES (%s, %s, %s)",
                            (filename, text, vetor_str)
                        )
                else:
                    print(f"Vetor vazio ou inválido para o arquivo {filename}, não será inserido no BD")

        # Após a inserção, buscar os conteúdos e vetores já armazenados
        cursor.execute("SELECT content, vector FROM pdf_content")
        rows = cursor.fetchall()

        processed_data = []
        for row in rows:
            content, vector_str = row
            if vector_str:  # Certifique-se de que o vetor não é None
                vector = np.array(vector_str.split(','), dtype=float)
            else:
                vector = np.array([])  # Ou outro comportamento desejado para vetores None
            processed_data.append((content, vector))
        
        return processed_data

# Rota para a página inicial
@app.route('/')
def index():
    return render_template('index.html')


contexto = []


system_prompt = """
    Você é um chatbot especialista em compliance...
    (continua igual)
"""


def gerar_resposta(prompt, contexto):
    # Vetoriza a pergunta do usuário
    vetor_pergunta = vetorizar_texto(prompt)
    
    # Recupera o conteúdo dos PDFs e seus vetores do banco de dados
    pdf_content_vetores = []
    if not conn.closed:
        with conn.cursor() as cursor:
            cursor.execute("SELECT content, vector FROM pdf_content")
            pdf_rows = cursor.fetchall()
            pdf_content_vetores = [
                (row[0], np.array(row[1].split(','), dtype=float)) for row in pdf_rows
            ]

    # Calcula a similaridade entre a pergunta e o conteúdo dos PDFs
    similaridades = [
        (conteudo, cosine_similarity([vetor_pergunta], [vetor])[0][0])
        for conteudo, vetor in pdf_content_vetores
    ]
    
    # Ordena os resultados pela similaridade
    similaridades.sort(key=lambda x: x[1], reverse=True)

    # Use o conteúdo mais relevante para construir o prompt
    pdf_content_relevante = similaridades[0][0] if similaridades else "Nenhum conteúdo relevante encontrado."

    # Adiciona a pergunta atual ao contexto
    conversa_anterior = "\n".join(contexto) if contexto else "Nenhuma conversa anterior."
    
    conversa_anterior += f"\nUsuário: {prompt}"

    full_prompt = (
        f"Diretrizes Gerais:\n{system_prompt}\n\n"
        f"Conteúdo dos PDFs relevantes:\n{pdf_content_relevante}\n\n"
        f"Histórico da conversa:\n{conversa_anterior}\n\n"
        f"Pergunta atual, responda sempre de forma completa, precisa e detalhada:. {prompt}\n\n"
    )
    
    response = model.generate_content(full_prompt)
    
    return response.text


def atualizar_contexto(contexto, pergunta, resposta, limite=5):
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
