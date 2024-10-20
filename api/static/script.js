document.addEventListener('DOMContentLoaded', function() {
    const messages = document.getElementById('messages');
    const chatbox = document.getElementById('chatbox');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message');

    const modal1 = document.getElementById('modal1');
    const modal2 = document.getElementById('modal2');
    const toModal2Button = document.getElementById('to-modal2');
    const closeModal2 = document.getElementById('back-to-modal1');
    const helpButton = document.getElementById('help-button');

    toModal2Button.addEventListener('click', () => {
        modal1.style.display = 'none';
    });

    closeModal2.addEventListener('click', () => {
        modal2.style.display = 'none';
    });

    helpButton.addEventListener('click', () => {
        modal1.style.display = 'flex'; // Mostra o primeiro modal
        modal2.style.display = 'none'; // Oculta o segundo modal
    });

    chatbox.scrollTop = chatbox.scrollHeight;

    chatForm.addEventListener('submit', function(event) {
        event.preventDefault();

        // Remove a div de perguntas frequentes ao enviar o formulário
        const frequentQuestionsDiv = document.getElementById('frequent-questions');
        if (frequentQuestionsDiv) {
            frequentQuestionsDiv.remove(); // Remove a div do DOM
        }

        const userMessage = messageInput.value.trim();
        if (userMessage !== '') {
            const messageElement = createMessageElement(userMessage, 'user-message');
            messages.appendChild(messageElement);
            messageInput.value = '';

            // Adiciona a animação de "digitando"
            const typingMessageElement = createMessageElement('Pensando...', 'chatbot-message');
            messages.appendChild(typingMessageElement);
            chatbox.scrollTop = chatbox.scrollHeight;

            fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: `message=${userMessage}`
            })
            .then(response => response.text())
            .then(chatbotResponse => {
                // Remove a mensagem de "digitando" e adiciona a resposta real
                messages.removeChild(typingMessageElement);
                typeChatbotResponse(chatbotResponse); // Chama a função para digitar a resposta
            })
            .catch(error => {
                console.error('Erro ao enviar mensagem:', error);
                // Remove a mensagem de "digitando" e adiciona uma mensagem de erro
                messages.removeChild(typingMessageElement);
                const errorElement = createMessageElement('Erro ao enviar a mensagem. Tente novamente mais tarde.', 'error-message');
                messages.appendChild(errorElement);
            });
        }
    });

    const observer = new MutationObserver(() => {
        chatbox.scrollTop = chatbox.scrollHeight;
    });

    observer.observe(messages, { childList: true });

    function createMessageElement(text, className) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message', className);

        // Substitui as quebras de linha por elementos <br>
        const formattedText = text.replace(/\n/g, '<br>');

        if (className === 'chatbot-message') {
            const botImage = document.createElement('img');
            botImage.src = 'static/eva_capa.png';
            messageElement.appendChild(botImage);

            const messageText = document.createElement('div');
            messageText.innerHTML = formattedText; // Usar innerHTML para suportar <br>
            messageElement.appendChild(messageText);
        } else {
            const messageText = document.createElement('div');
            messageText.innerHTML = formattedText; // Usar innerHTML para suportar <br>
            messageElement.appendChild(messageText);
        }

        return messageElement;
    }

    // Função para digitar a resposta do chatbot letra por letra
    function typeChatbotResponse(response) {
        const responseElement = createMessageElement('', 'chatbot-message');
        messages.appendChild(responseElement);
        chatbox.scrollTop = chatbox.scrollHeight;

        let i = 0;
        const typingSpeed = 5; 

        function type() {
            if (i < response.length) {
                const formattedText = response.slice(0, i + 1).replace(/\n/g, '<br>');
                responseElement.querySelector('div').innerHTML = formattedText; // Atualiza o texto da resposta
                i++;
                setTimeout(type, typingSpeed);
            } else {
                translateMessages(languageSelect.value); // Traduzir após a digitação completa
            }
        }

        type(); // Inicia a função de digitação
    }

    // Adicionando o menu lateral
    const menuLateral = document.getElementById('menuLateral');
    const mainContent = document.getElementById('main-content');
    const menuLateralToggle = document.getElementById('menuLateralToggle');

    menuLateralToggle.addEventListener('click', function() {
        menuLateral.classList.toggle('active');
        mainContent.classList.toggle('shifted'); // Adiciona ou remove a margem
    });

    // Deixando o menu lateral ativo
    menuLateralToggle.addEventListener("click", function() {
        this.classList.toggle("active");
    });

    // Função para preencher o campo de mensagem com o texto das perguntas frequentes
    document.querySelectorAll('.question-btn').forEach(button => {
        button.addEventListener('click', function() {
            const question = this.getAttribute('data-question');
            
            // Preenche o campo de input com a pergunta selecionada
            messageInput.value = question;

            // Remove a div que contém os botões de perguntas frequentes
            const frequentQuestionsDiv = document.getElementById('frequent-questions');
            if (frequentQuestionsDiv) {
                frequentQuestionsDiv.parentNode.removeChild(frequentQuestionsDiv); // Remove a div do DOM
            }
        });
    });

    // Baixar pdf ao clicar no botão
    document.getElementById('downloadPdfBtn').addEventListener('click', function() {
        const pdfSelect = document.getElementById('pdfSelect');
        const selectedPdf = pdfSelect.value;
        if (selectedPdf) {
            const link = document.createElement('a');
            link.href = selectedPdf;  // URL do arquivo PDF
            link.download = selectedPdf;  // Nome do arquivo para download
            link.click();
        } 
    });
});
