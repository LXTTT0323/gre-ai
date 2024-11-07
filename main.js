document.addEventListener('DOMContentLoaded', () => {
    const questionInput = document.getElementById('question');
    const imageUpload = document.getElementById('imageUpload');
    const imagePreview = document.getElementById('imagePreview');
    const imagePreviewContainer = document.getElementById('imagePreviewContainer');
    const zoomOverlay = document.getElementById('zoomOverlay');
    const submitButton = document.getElementById('submit');
    const chatContainer = document.getElementById('chat-container');
    const loadingIndicator = document.getElementById('loading-indicator');

    let conversationHistory = [];

    let scale = 1;
    let isDragging = false;
    let startX, startY, translateX = 0, translateY = 0;

    // Preview image when selected
    imageUpload.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                imagePreview.style.display = 'block';
                zoomOverlay.style.display = 'flex';
                resetZoom();
            };
            reader.readAsDataURL(file);
        }
    });

    function resetZoom() {
        scale = 1;
        translateX = 0;
        translateY = 0;
        updateImageTransform();
    }

    function updateImageTransform() {
        imagePreview.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
    }

    // 缩放功能
    function zoom(delta) {
        scale += delta * 0.1;
        scale = Math.max(1, Math.min(scale, 3)); // 限制缩放范围在 1-3 倍之间
        updateImageTransform();
        imagePreview.classList.toggle('zoomed', scale > 1);
        zoomOverlay.innerHTML = scale > 1 ? '<i class="fas fa-search-minus"></i>' : '<i class="fas fa-search-plus"></i>';
    }

    // 滚轮缩放
    imagePreviewContainer.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -1 : 1;
        zoom(delta);
    });

    // 双击切换缩放
    imagePreview.addEventListener('dblclick', () => {
        if (scale > 1) {
            resetZoom();
        } else {
            zoom(10); // 直接放大到最大
        }
    });

    // 点击放大/缩小图标
    zoomOverlay.addEventListener('click', (e) => {
        e.stopPropagation();
        if (scale > 1) {
            resetZoom();
        } else {
            zoom(10);
        }
    });

    // 拖拽功能
    imagePreview.addEventListener('mousedown', (e) => {
        if (scale > 1) {
            isDragging = true;
            startX = e.clientX - translateX;
            startY = e.clientY - translateY;
            imagePreview.style.cursor = 'grabbing';
        }
    });

    document.addEventListener('mousemove', (e) => {
        if (isDragging) {
            translateX = e.clientX - startX;
            translateY = e.clientY - startY;
            updateImageTransform();
        }
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
        imagePreview.style.cursor = scale > 1 ? 'move' : 'pointer';
    });

    // 鼠标拖拽缩放
    let startDistance = 0;
    imagePreviewContainer.addEventListener('mousedown', (e) => {
        startDistance = e.clientY;
    });

    imagePreviewContainer.addEventListener('mousemove', (e) => {
        if (e.buttons === 1) { // 检查鼠标左键是否按下
            const currentDistance = e.clientY;
            const delta = (startDistance - currentDistance) / 100;
            zoom(delta);
            startDistance = currentDistance;
        }
    });

    // 鼠标悬停显示/隐藏缩放图标
    imagePreviewContainer.addEventListener('mouseenter', () => {
        zoomOverlay.style.opacity = '1';
    });

    imagePreviewContainer.addEventListener('mouseleave', () => {
        zoomOverlay.style.opacity = '0';
    });

    // Handle form submission
    submitButton.addEventListener('click', async () => {
        const question = questionInput.value.trim();
        if (!question) return;

        addMessageToChat('user', question);
        questionInput.value = '';

        const formData = new FormData();
        formData.append('file', imageUpload.files[0]);
        formData.append('question', question);
        formData.append('conversation_history', JSON.stringify(conversationHistory));

        try {
            // 显示加载指示器
            loadingIndicator.style.display = 'flex';
            // 滚动到聊天容器底部
            chatContainer.scrollTop = chatContainer.scrollHeight;

            const response = await fetch(apiUrl, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const htmlContent = await response.text();
            
            // 使用 addMessageToChat 函数来添加响应
            addMessageToChat('assistant', htmlContent);

            conversationHistory.push({ role: 'user', content: question });
            conversationHistory.push({ role: 'assistant', content: htmlContent });

        } catch (error) {
            console.error('Error:', error);
            addMessageToChat('assistant', `<p>An error occurred: ${error.message}</p>`);
        } finally {
            // 隐藏加载指示器
            loadingIndicator.style.display = 'none';
        }
    });

    function addMessageToChat(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}`;
        messageDiv.innerHTML = content;
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
});

async function submitFollowUpQuestion() {
    const followUpQuestion = document.getElementById('followUpQuestion');
    const followUpResponse = document.getElementById('followUpResponse');
    
    if (!followUpQuestion || !followUpResponse) {
        console.error('Follow-up question elements not found');
        return;
    }

    try {
        const response = await fetch('/follow-up', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ question: followUpQuestion.value, previous_context: lastResponse }),
        });
        const result = await response.json();
        followUpResponse.innerHTML = result.answer;
    } catch (error) {
        console.error('Error submitting follow-up question:', error);
        followUpResponse.innerHTML = `<p>An error occurred: ${error.message}</p>`;
    }
}

function submitFeedback(isHelpful) {
    fetch('/feedback', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ helpful: isHelpful, response: lastResponse }),
    })
    .then(() => alert('Thank you for your feedback!'))
    .catch(error => console.error('Error submitting feedback:', error));
}

const apiUrl = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://127.0.0.1:8000/analyze-gre-verbal'
    : 'https://gre-ai-cbdb67695e84.herokuapp.com/analyze-gre-verbal';
