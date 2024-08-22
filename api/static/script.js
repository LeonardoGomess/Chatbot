document.addEventListener('DOMContentLoaded', function() {
    const messages = document.getElementById('messages');
    const chatbox = document.getElementById('chatbox');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message');
    const languageSelect = document.getElementById('language-select');

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
        modal1.style.display = 'flex'; // Mostra o segundo modal
        modal2.style.display = 'none'; // Oculta o primeiro modal
    });
    // Função para carregar idiomas do arquivo JSON
    function loadLanguages() {
        fetch('/static/languages.json')  // Caminho relativo à raiz do projeto
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(languages => {
                console.log('Languages loaded:', languages);  // Verifique o conteúdo do JSON no console
                languageSelect.innerHTML = '';  // Limpa o dropdown
                // Adiciona o placeholder
                const placeholderOption = document.createElement('option');
                placeholderOption.value = '';
                placeholderOption.disabled = true;
                placeholderOption.selected = true;
                placeholderOption.textContent = 'Traduzir Página 🌐';
                languageSelect.appendChild(placeholderOption);
                // Adiciona as opções de idiomas
                languages.forEach(language => {
                    const option = document.createElement('option');
                    option.value = language.code;
                    option.textContent = language.name;
                    languageSelect.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Erro ao carregar os idiomas:', error);
            });
    }
  
    loadLanguages();
  
    chatbox.scrollTop = chatbox.scrollHeight;
  
    chatForm.addEventListener('submit', function(event) {
        event.preventDefault();
    
        const userMessage = messageInput.value.trim();
        if (userMessage !== '') {
            const messageElement = createMessageElement(userMessage, 'user-message');
            messages.appendChild(messageElement);
            messageInput.value = '';
    
            // Adiciona a animação de "digitando"
            const typingMessageElement = createMessageElement('...', 'chatbot-message');
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
                const responseElement = createMessageElement(chatbotResponse, 'chatbot-message');
                messages.appendChild(responseElement);
                chatbox.scrollTop = chatbox.scrollHeight;
    
                // Traduzir a nova mensagem do chatbot após adicioná-la
                translateMessages(languageSelect.value);
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
    
        if (className === 'chatbot-message') {
            const botImage = document.createElement('img');
            botImage.src = 'static/eva_capa.png';
            messageElement.appendChild(botImage);
    
            const messageText = document.createElement('div');
            messageText.classList.add('typing-animation');
            messageElement.appendChild(messageText);
    
            typeText(messageText, text, 0);
        } else {
            const messageText = document.createElement('div');
            messageText.textContent = text;
            messageElement.appendChild(messageText);
        }
    
        return messageElement;
    }
    
  
    function typeText(element, text, index) {
        const typingSpeed = 5; // Velocidade de digitação em milissegundos
        if (index < text.length) {
            element.textContent += text.charAt(index);
            setTimeout(() => typeText(element, text, index + 1), typingSpeed);
        } else {
            // Remove a animação de "digitando" quando a digitação estiver completa
            element.classList.remove('typing-animation');
            translateMessages(languageSelect.value);
        }
    }
    
  
    languageSelect.addEventListener('change', function() {
        const selectedLanguage = this.value;
        translateMessages(selectedLanguage);
    });
  
    function translateMessages(targetLanguage) {
        if (!targetLanguage) return;  // Verifica se um idioma foi selecionado
  
        const messages = document.querySelectorAll('.chat-message');
        messages.forEach(message => {
            if (message.classList.contains('user-message')) {
                const originalText = message.textContent;
                translateText(originalText, targetLanguage).then(translatedText => {
                    message.textContent = translatedText;
                });
            } else if (message.classList.contains('chatbot-message')) {
                const messageText = message.querySelector('.typing-animation').textContent;
                translateText(messageText, targetLanguage).then(translatedText => {
                    message.querySelector('.typing-animation').textContent = translatedText;
                });
            }
        });
    }
  
    function translateText(text, targetLanguage) {
        const apiKey = '';
        const url = `https://translation.googleapis.com/language/translate/v2?key=${apiKey}`;
        
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                q: text,
                target: targetLanguage
            })
        })
        .then(response => response.json())
        .then(data => data.data.translations[0].translatedText)
        .catch(error => {
            console.error('Erro ao traduzir:', error);
            return text;  // Retorna o texto original se houver um erro
        });
    }
  });