from dotenv import load_dotenv
from flask import Flask, render_template, request
from PyPDF2 import PdfReader
import google.generativeai as genai
import os
import mysql.connector
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

app = Flask(__name__,static_folder="static",template_folder="templates")
model_embedding = SentenceTransformer('all-MiniLM-L6-v2')

# Carrega as variáveis de ambiente
load_dotenv()
api_key = os.getenv('GENAI_API_KEY')
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')


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

# Cria a tabela se ela não existir
with conn.cursor() as cursor:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pdf_content (
        id INT AUTO_INCREMENT PRIMARY KEY,
        filename VARCHAR(255),
        content TEXT,
        vector TEXT
    )
    """)
    conn.commit()  # Garante que a criação da tabela é persistida

def extract_text_from_pdf(pdf_path):
    """Extrai texto de um arquivo PDF."""
    text = ''
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PdfReader(pdf_file)
        text = ''.join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
    return text

def vetorizar_texto(texto):
    """Vetoriza o texto usando um modelo de embedding."""
    return model_embedding.encode(texto)

def carregar_pdfs(diretorio):
    """
    Carrega PDFs de um diretório, extrai texto, vetoriza e armazena no banco de dados.
    Retorna os conteúdos e vetores processados.
    """
    # Certifique-se de que a conexão está aberta
    if not conn.is_connected():
        conn.reconnect()

    processed_data = []

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
                        conn.commit()
                        print(f"Arquivo {filename} inserido no banco de dados.")
                    else:
                        print(f"O arquivo {filename} já existe no banco de dados. Ignorando inserção.")
                else:
                    print(f"Vetor vazio ou inválido para o arquivo {filename}, não será inserido no BD.")

        # Após a inserção, buscar os conteúdos e vetores já armazenados
        cursor.execute("SELECT content, vector FROM pdf_content")
        rows = cursor.fetchall()

        for row in rows:
            content, vector_str = row
            if vector_str:  # Certifique-se de que o vetor não é None
                vector = np.array(vector_str.split(','), dtype=float)
            else:
                vector = np.array([])  # Comportamento desejado para vetores None
            processed_data.append((content, vector))

    return processed_data  # Retorna a lista de conteúdos e vetores processados


# Não se esqueça de fechar a conexão quando terminar
conn.close()


# Rota para a página inicial
@app.route('/')
def index():
    return render_template('index.html')


contexto = []


system_prompt = """
    Você é um chatbot especialista em compliance. Sua função é ajudar os usuários a encontrar informações relevantes sobre compliance com base nas informações que você tem no seu sistema.

  
    Diretrizes Gerais:


    1.IMPORTANTE: Responder apenas a perguntas ou dúvidas relacionadas a compliance.
    2.IMPORTANTE: Quando o usuário fizer uma pergunta que não seja sobre compliance,voce deve responder educadamente, informando que só pode fornecer informações e respostas relacionadas a esse tema.
    3.MAIS IMPORTANTE: Responda às perguntas retornando exatamente o conteúdo relevante encontrado nos PDFs disponíveis no sistema.
    4.IMPORTANTE: Responda de forma natural, precisa e completa, fornecendo informações específicas.
    5.IMPORTANTE: Se a pergunta não estiver clara ou for vaga, peça mais detalhes ao usuário e reforce que responde apenas a questões sobre compliance.
    6.IMPORTANTE: Evite respostas vagas ou genéricas. Sempre forneça informações específicas e completas.
    7.IMPORTANTE: Não inclua nas respostas informações que não estejam presentes nos PDFs.
    8.IMPORTANTE: Não crie informações falsas ou inventadas.
    9.IMPORTANTE: Foque diretamente na informação solicitada e evite adicionar informações irrelevantes.
    10.IMPORTANTE: Se não encontrar a resposta nos PDFs, informe ao usuário que a informação não está disponível e sugira consultar outras fontes para mais detalhes.
    11.IMPORTANTE: Quando solicitado "Me forneça mais detalhes ou informações sobre essa resposta fornecida", use o contexto da conversa e forneça mais informações relevantes encontradas nos PDFs.
    12.IMPORTANTE: Caso receba perguntas que não estejam relacionadas a compliance, peça desculpas e explique que o chatbot só pode responder a perguntas relacionadas a compliance.
    13.IMPORTANTE: Responda mensagens de boas-vindas de forma natural e agradável.
    14.IMPORTANTE: Responda mensagens de agradecimento de forma natural e agradável 
    15.IMPORTANTE: Ao final de cada resposta, indique de qual PDF a informação foi retirada.
    16.IMPORTANTE: Não mencionar o PDF ao final de mensagens de boas-vindas e mensagens de agradecimento feitas por voce.

"""



def gerar_resposta(prompt, contexto):


    # Vetoriza a pergunta do usuário
    vetor_pergunta = vetorizar_texto(prompt)
    
    # Recupera o conteúdo dos PDFs e seus vetores do banco de dados
    pdf_content_vetores = []
    if conn.is_connected():
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

    # Incluir o contexto da conversa no prompt, limitando-se ao último tópico se necessário
    conversa_anterior = "\n".join(contexto) if contexto else "Nenhuma conversa anterior."
    
    # Adiciona a pergunta atual ao contexto
    conversa_anterior += f"\nUsuário: {prompt}"

    # Monta o prompt completo
    full_prompt = (
        f"Diretrizes Gerais:\n{system_prompt}\n\n"
        f"Conteúdo dos PDFs relevantes:\n{pdf_content_relevante}\n\n"
        f"Histórico da conversa:\n{conversa_anterior}\n\n"
        f"Pergunta atual, responda sempre de forma completa, precisa e detalhada:. {prompt}\n\n"
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