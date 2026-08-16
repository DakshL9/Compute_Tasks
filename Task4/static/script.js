/**
 * script.js — NutriBuddy Client-Side Logic
 *
 * This file controls all browser-side behaviour:
 * - Sending messages and images to the Flask backend via fetch()
 * - Displaying user and assistant messages in the chat
 * - Managing the image attachment preview
 * - Loading indicator ("NutriBuddy is thinking...")
 * - Starter prompt chips
 * - New Chat reset (no page reload)
 * - Random Quick Tip on page load
 *
 * No API keys. No Groq. All requests go to /api/chat.
 * The browser never sees your API key.
 */

'use strict';

/* =====================================================================
   QUICK NUTRITION TIPS
   A curated, evidence-based set of tips. One is randomly chosen on
   page load. This uses NO API call — it's just local data.
   ===================================================================== */
const NUTRITION_TIPS = [
    "Include a source of protein and fiber in your meals to help make them more filling.",
    "Drinking water before meals can help you avoid overeating.",
    "A palm-sized portion of protein, a fist of vegetables, and a cupped hand of carbs is a simple visual guide to balanced plates.",
    "Eating slowly and chewing thoroughly improves digestion and helps you recognize fullness.",
    "Whole fruits are better than juices — they have more fiber and less sugar per serving.",
    "A small handful of nuts makes an excellent nutrient-dense snack between meals.",
    "Colorful plates typically mean more varied micronutrients — aim for 3+ colors per meal.",
    "Preparing meals at home gives you control over portion sizes, oil, salt, and quality.",
    "Sleep deprivation can increase hunger hormones, making healthy eating harder.",
    "Legumes (lentils, chickpeas, beans) are affordable, high-protein, high-fiber staples.",
];

/* =====================================================================
   DOM REFERENCES
   ===================================================================== */
const chatContainer       = document.getElementById('chat-container');
const chatForm            = document.getElementById('chat-form');
const messageInput        = document.getElementById('message-input');
const sendBtn             = document.getElementById('send-btn');
const attachBtn           = document.getElementById('attach-btn');
const imageInput          = document.getElementById('image-input');
const imagePreviewBox     = document.getElementById('image-preview-container');
const imagePreview        = document.getElementById('image-preview');
const imageFilename       = document.getElementById('image-filename');
const removeImageBtn      = document.getElementById('remove-image-btn');
const newChatBtn          = document.getElementById('new-chat-btn');
const starterPrompts      = document.getElementById('starter-prompts');
const promptChips         = document.querySelectorAll('.prompt-chip');
const quickTipText        = document.getElementById('quick-tip-text');
const quickTipCard        = document.getElementById('quick-tip-card');

/* =====================================================================
   STATE
   ===================================================================== */
let isWaiting = false;          // true while waiting for the backend
let selectedFile = null;        // the File object the user picked
let conversationStarted = false; // hides starter prompts after first message

/* =====================================================================
   INITIALISATION
   ===================================================================== */
function init() {
    // Pick a random quick tip
    quickTipText.textContent = NUTRITION_TIPS[Math.floor(Math.random() * NUTRITION_TIPS.length)];

    // Auto-resize textarea as user types
    messageInput.addEventListener('input', autoResize);

    // Submit on Enter, newline on Shift+Enter
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!isWaiting) chatForm.requestSubmit();
        }
    });

    // Attach button opens file picker
    attachBtn.addEventListener('click', () => imageInput.click());

    // File selected
    imageInput.addEventListener('change', handleFileSelected);

    // Remove image button
    removeImageBtn.addEventListener('click', clearImage);

    // Form submit
    chatForm.addEventListener('submit', handleSubmit);

    // New Chat button
    newChatBtn.addEventListener('click', handleNewChat);

    // Starter prompt chips
    promptChips.forEach(chip => {
        chip.addEventListener('click', () => {
            messageInput.value = chip.dataset.prompt;
            messageInput.focus();
            autoResize();
        });
    });
}

/* =====================================================================
   TEXTAREA AUTO-RESIZE
   The <textarea> grows with content so it feels like a modern chat input.
   ===================================================================== */
function autoResize() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 140) + 'px';
}

/* =====================================================================
   FILE SELECTION HANDLING
   When a user selects a file via the 📎 button, show a preview.
   We do NOT upload it yet — upload happens only when Send is pressed.
   ===================================================================== */
function handleFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Quick client-side validation (server also validates)
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
        showError('Please select a JPG, PNG, or WEBP image file.');
        imageInput.value = '';
        return;
    }

    if (file.size > 20 * 1024 * 1024) { // 20MB
        showError('The selected image is too large. Please choose a file under 20MB.');
        imageInput.value = '';
        return;
    }

    selectedFile = file;

    // Show preview using a FileReader (reads file locally, no network)
    const reader = new FileReader();
    reader.onload = (e) => {
        imagePreview.src = e.target.result;
        imageFilename.textContent = file.name;
        imagePreviewBox.classList.remove('hidden');
    };
    reader.readAsDataURL(file);
}

function clearImage() {
    selectedFile = null;
    imageInput.value = '';
    imagePreviewBox.classList.add('hidden');
    imagePreview.src = '';
}

/* =====================================================================
   SUBMIT HANDLER
   Builds FormData with text + optional image and POSTs to /api/chat.
   ===================================================================== */
async function handleSubmit(e) {
    e.preventDefault();
    if (isWaiting) return;

    const text = messageInput.value.trim();

    if (!text && !selectedFile) {
        messageInput.focus();
        return;
    }

    // Hide starter prompts once the first message is sent
    if (!conversationStarted) {
        conversationStarted = true;
        starterPrompts.classList.add('hidden');
        quickTipCard.classList.add('hidden');
    }

    // Display user's message in the chat immediately
    addUserMessage(text, selectedFile ? imagePreview.src : null);

    // Reset input
    const userText = text;
    const userFile = selectedFile;
    messageInput.value = '';
    autoResize();
    clearImage();

    // Disable controls while waiting
    setWaiting(true);

    // Show "NutriBuddy is thinking..." indicator
    const loadingEl = addLoadingMessage();

    // Build multipart form data
    // Why multipart/form-data? Because we need to send both text AND a binary
    // image file in the same HTTP request. JSON can't carry raw binary data
    // efficiently — multipart is the browser's native format for file uploads.
    const formData = new FormData();
    if (userText) formData.append('message', userText);
    if (userFile) formData.append('image', userFile, userFile.name);

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            body: formData,
            // Note: do NOT set Content-Type header manually for multipart/form-data.
            // The browser sets it automatically, including the required boundary string.
        });

        const data = await response.json();
        loadingEl.remove();

        if (data.status === 'success') {
            addAssistantMessage(data.reply);
        } else {
            addErrorMessage(data.error || 'Something went wrong. Please try again.');
        }

    } catch (networkError) {
        // This fires if Flask isn't running or the network is down
        loadingEl.remove();
        addErrorMessage('Unable to connect to the server. Is the Flask backend running?');
    }

    setWaiting(false);
    scrollToBottom();
}

/* =====================================================================
   NEW CHAT
   Tells the backend to clear history and resets the UI without reloading.
   ===================================================================== */
async function handleNewChat() {
    if (isWaiting) return;

    try {
        await fetch('/api/new-chat', { method: 'POST' });
    } catch (_) {
        // Even if the server call fails, clear the UI so the user can start fresh
    }

    // Remove all chat messages from the DOM
    chatContainer.innerHTML = '';

    // Rebuild the initial state (quick tip, welcome message, starter prompts)
    rebuildInitialUI();

    conversationStarted = false;
    clearImage();
    messageInput.value = '';
    autoResize();
}

function rebuildInitialUI() {
    // Quick tip card
    const tip = NUTRITION_TIPS[Math.floor(Math.random() * NUTRITION_TIPS.length)];
    const tipCard = document.createElement('div');
    tipCard.id = 'quick-tip-card';
    tipCard.className = 'quick-tip-card';
    tipCard.innerHTML = `
        <span class="tip-icon">💡</span>
        <div class="tip-content">
            <strong>Quick Tip:</strong>
            <span>${tip}</span>
        </div>`;
    chatContainer.appendChild(tipCard);

    // Welcome message
    const welcomeMsg = createAssistantBubble(
        `Hey there! I'm <strong>NutriBuddy</strong>, your AI Nutrition Coach.<br><br>Ask me any nutrition question, or share a photo of your meal for a quick estimation and feedback!`
    );
    chatContainer.appendChild(welcomeMsg);

    // Starter prompts
    const promptsHtml = `
        <div id="starter-prompts" class="starter-prompts">
            <p class="prompts-title">Try asking:</p>
            <div class="prompts-grid">
                <button class="prompt-chip" data-prompt="High-protein breakfast ideas for busy mornings">🍳 High-protein breakfast ideas</button>
                <button class="prompt-chip" data-prompt="Help me build a balanced lunch with rice and vegetables">🥗 Help me build a balanced lunch</button>
                <button class="prompt-chip" data-prompt="What are some healthy, low-sugar afternoon snacks?">🍎 What are some healthy snacks?</button>
            </div>
        </div>`;
    chatContainer.insertAdjacentHTML('beforeend', promptsHtml);

    // Re-attach click events to new prompt chips
    chatContainer.querySelectorAll('.prompt-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            messageInput.value = chip.dataset.prompt;
            messageInput.focus();
            autoResize();
        });
    });
}

/* =====================================================================
   MESSAGE RENDERING
   ===================================================================== */
function addUserMessage(text, imageSrc) {
    const msgEl = document.createElement('div');
    msgEl.className = 'message user-message';

    let content = '';
    if (imageSrc) {
        content += `<img class="attached-image" src="${imageSrc}" alt="Attached meal photo">`;
    }
    if (text) {
        content += escapeHtml(text);
    }
    if (!text && imageSrc) {
        content += `<em style="opacity:0.7">📷 Meal photo sent for analysis</em>`;
    }

    msgEl.innerHTML = `<div class="bubble">${content}</div>`;
    chatContainer.appendChild(msgEl);
    scrollToBottom();
}

function createAssistantBubble(htmlContent) {
    const msgEl = document.createElement('div');
    msgEl.className = 'message assistant-message';
    msgEl.innerHTML = `
        <div class="avatar">🥗</div>
        <div class="bubble">${htmlContent}</div>`;
    return msgEl;
}

function addAssistantMessage(text) {
    const msgEl = createAssistantBubble(formatMarkdown(text));
    chatContainer.appendChild(msgEl);
    scrollToBottom();
}

function addLoadingMessage() {
    const msgEl = document.createElement('div');
    msgEl.className = 'message assistant-message loading-message';
    msgEl.innerHTML = `
        <div class="avatar">🥗</div>
        <div class="bubble">
            NutriBuddy is thinking
            <div class="loading-dots" aria-label="Loading">
                <span></span><span></span><span></span>
            </div>
        </div>`;
    chatContainer.appendChild(msgEl);
    scrollToBottom();
    return msgEl;
}

function addErrorMessage(errorText) {
    const msgEl = document.createElement('div');
    msgEl.className = 'message assistant-message error-message';
    msgEl.innerHTML = `
        <div class="avatar">⚠️</div>
        <div class="bubble">${escapeHtml(errorText)}</div>`;
    chatContainer.appendChild(msgEl);
    scrollToBottom();
}

function showError(text) {
    addErrorMessage(text);
}

/* =====================================================================
   UTILITY HELPERS
   ===================================================================== */
function setWaiting(state) {
    isWaiting = state;
    sendBtn.disabled = state;
    attachBtn.disabled = state;
    messageInput.disabled = state;
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Minimal markdown-to-HTML formatter for assistant responses.
 * Handles: bold (**text**), newlines, bullet points.
 * We keep this simple — full markdown parsing is out of scope.
 */
function formatMarkdown(text) {
    return escapeHtml(text)
        // Bold: **text** → <strong>text</strong>
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // Bullet lines: "• item" or "- item" at line start
        .replace(/^[•\-]\s+(.+)$/gm, '<li>$1</li>')
        // Wrap consecutive <li> in <ul>
        .replace(/(<li>.*<\/li>\n?)+/g, (block) => `<ul>${block}</ul>`)
        // Convert double newlines to paragraph breaks
        .replace(/\n\n/g, '<br><br>')
        // Convert remaining single newlines to <br>
        .replace(/\n/g, '<br>');
}

/* =====================================================================
   BOOTSTRAP
   ===================================================================== */
document.addEventListener('DOMContentLoaded', init);
