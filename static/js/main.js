const themeToggle = document.querySelector('[data-theme-toggle]');
if (themeToggle) {
    const updateThemeToggle = () => {
        const isDark = document.documentElement.dataset.theme === 'dark';
        themeToggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
        themeToggle.setAttribute('title', isDark ? 'Switch to light mode' : 'Switch to dark mode');
    };
    updateThemeToggle();
    themeToggle.addEventListener('click', () => {
        const nextTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = nextTheme;
        localStorage.setItem('kisanqueue-theme', nextTheme);
        updateThemeToggle();
    });
}

const chatToggle = document.querySelector('[data-chat-toggle]');
const chatPanel = document.querySelector('[data-chat-panel]');
const chatClose = document.querySelector('[data-chat-close]');
const chatForm = document.querySelector('[data-chat-form]');
const chatInput = document.querySelector('[data-chat-input]');
const chatMessages = document.querySelector('[data-chat-messages]');
const chatStatus = document.querySelector('[data-chat-status]');
const chatMic = document.querySelector('[data-chat-mic]');
const chatVoice = document.querySelector('[data-chat-voice]');
const chatHistory = [];
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

const speakChatText = (content) => {
    if (!chatVoice?.checked || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(content);
    utterance.lang = document.documentElement.lang === 'hi' ? 'hi-IN' : document.documentElement.lang === 'kn' ? 'kn-IN' : 'en-IN';
    utterance.rate = 0.9;
    utterance.pitch = 1;
    window.speechSynthesis.speak(utterance);
};

const appendChatMessage = (role, content, className = '') => {
    const message = document.createElement('div');
    message.className = `chat-message chat-message-${className || role}`;
    message.textContent = content;
    if (role === 'assistant' && !className) {
        const speak = document.createElement('button');
        speak.type = 'button';
        speak.className = 'chat-speak-button';
        speak.textContent = 'Listen';
        speak.setAttribute('aria-label', 'Read this answer aloud');
        speak.addEventListener('click', () => {
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(new SpeechSynthesisUtterance(content));
            }
        });
        message.appendChild(speak);
    }
    chatMessages.appendChild(message);
    chatMessages.scrollTop = chatMessages.scrollHeight;
};

if (chatToggle && chatPanel && chatForm && chatInput && chatMessages) {
    const setChatOpen = (open) => {
        chatPanel.hidden = !open;
        chatToggle.setAttribute('aria-expanded', String(open));
        if (open) chatInput.focus();
    };
    chatToggle.addEventListener('click', () => setChatOpen(chatPanel.hidden));
    if (chatClose) chatClose.addEventListener('click', () => setChatOpen(false));
    if (chatMic) {
        if (!SpeechRecognition) {
            chatMic.disabled = true;
            chatMic.title = 'Speech input is not supported in this browser';
        } else {
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = document.documentElement.lang === 'hi' ? 'hi-IN' : document.documentElement.lang === 'kn' ? 'kn-IN' : 'en-IN';
            recognition.onstart = () => {
                chatMic.classList.add('farmer-chat-mic-active');
                chatStatus.textContent = 'Listening...';
            };
            recognition.onaudiostart = () => { chatStatus.textContent = 'Listening... speak now'; };
            recognition.onsoundstart = () => { chatStatus.textContent = 'Hearing you...'; };
            recognition.onresult = (event) => {
                chatInput.value = event.results[0][0].transcript;
                chatStatus.textContent = 'Sending your question...';
                chatForm.requestSubmit();
            };
            recognition.onerror = (event) => {
                const messages = {
                    'not-allowed': 'Allow microphone access for this site, then try again',
                    'service-not-allowed': 'Browser speech service is blocked',
                    'no-speech': 'No speech detected - try again',
                    'audio-capture': 'No microphone was detected',
                    'network': 'Speech service needs a network connection'
                };
                chatStatus.textContent = messages[event.error] || 'Microphone unavailable';
            };
            recognition.onend = () => chatMic.classList.remove('farmer-chat-mic-active');
            chatMic.addEventListener('click', () => {
                chatStatus.textContent = 'Starting microphone...';
                try { recognition.start(); } catch (error) { chatStatus.textContent = 'Mic is already listening'; }
            });
        }
    }
    chatForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const message = chatInput.value.trim();
        if (!message) return;
        appendChatMessage('user', message);
        chatHistory.push({role: 'user', content: message});
        chatInput.value = '';
        chatInput.disabled = true;
        chatStatus.textContent = 'Thinking...';
        try {
            const response = await fetch('/farmer/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                body: JSON.stringify({
                    message,
                    history: chatHistory.slice(-8),
                    language: document.documentElement.lang || 'en'
                })
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error || 'The assistant is unavailable.');
            appendChatMessage('assistant', payload.reply);
            chatHistory.push({role: 'assistant', content: payload.reply});
            speakChatText(payload.reply);
            chatStatus.textContent = 'AI support';
        } catch (error) {
            appendChatMessage('assistant', error.message || 'The assistant is temporarily unavailable.', 'error');
            chatStatus.textContent = 'Try again';
        } finally {
            chatInput.disabled = false;
            chatInput.focus();
        }
    });
}

// Registers the service worker for web push notifications, if the browser
// supports it. This is best-effort: if VAPID keys aren't configured on the
// server, subscription will simply be skipped, and notifications still work
// via the in-app panel and email fallback.
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/js/service-worker.js').catch(() => {
            // Silently ignore - push notifications are an enhancement, not required.
        });
    });
}

const translations = {
    hi: {
        'Farmer Procurement': 'किसान खरीद', 'mandi operations': 'मंडी संचालन', 'Login': 'लॉग इन', 'Register': 'पंजीकरण',
        'Dashboard': 'डैशबोर्ड', 'Book Slot': 'स्लॉट बुक करें', 'History': 'इतिहास', 'Mandi Prices': 'मंडी भाव',
        'Notifications': 'सूचनाएं', 'Logout': 'लॉग आउट', 'Queue Dashboard': 'कतार डैशबोर्ड', 'Manage Slots': 'स्लॉट प्रबंधन',
        'Analytics': 'विश्लेषण', 'Prices': 'मंडी भाव', 'Audit Log': 'ऑडिट लॉग', 'Language': 'भाषा',
        'Farmer workspace': 'किसान कार्यक्षेत्र', 'Welcome back,': 'वापसी पर स्वागत है,', 'Upcoming Slot': 'आगामी स्लॉट',
        'Recent History': 'हाल का इतिहास', 'You have no upcoming procurement slot booked.': 'आपने अभी तक कोई खरीद स्लॉट बुक नहीं किया है।',
        'Book a Slot': 'स्लॉट बुक करें', 'View full history →': 'पूरा इतिहास देखें →', 'Procurement History': 'खरीद इतिहास',
        'Date': 'तारीख', 'Centre': 'केंद्र', 'Crop': 'फसल', 'Qty (kg)': 'मात्रा (किलो)', 'Token': 'टोकन',
        'Status': 'स्थिति', 'Payment': 'भुगतान', 'Timeline': 'समयरेखा', 'PDF': 'पीडीएफ', 'No bookings yet.': 'अभी कोई बुकिंग नहीं है।',
        'Book a Procurement Slot': 'खरीद स्लॉट बुक करें', 'Crop Type': 'फसल का प्रकार', 'Select crop': 'फसल चुनें',
        'Quantity (kg)': 'मात्रा (किलो)', 'Procurement Centre': 'खरीद केंद्र', 'Select centre': 'केंद्र चुनें',
        'Available Date & Time Slot': 'उपलब्ध तारीख और समय स्लॉट', 'Select a centre first': 'पहले केंद्र चुनें',
        'No slots available': 'कोई स्लॉट उपलब्ध नहीं है', 'Confirm Booking': 'बुकिंग की पुष्टि करें',
        'Live Queue Status': 'लाइव कतार स्थिति', 'Now Serving': 'अभी सेवा में', 'Your Token': 'आपका टोकन',
        "It's your turn — please proceed to the counter!": 'आपकी बारी है — कृपया काउंटर पर जाएं!',
        'Procurement completed': 'खरीद पूरी हुई', 'Marked as no-show': 'अनुपस्थित के रूप में दर्ज',
        'Estimated wait:': 'अनुमानित प्रतीक्षा:', 'minutes': 'मिनट', 'View Full Timeline': 'पूरी समयरेखा देखें',
        'Procurement & Payment Tracker': 'खरीद और भुगतान ट्रैकर', 'Payment received': 'भुगतान प्राप्त',
        'Notifications': 'सूचनाएं', 'Telegram Updates': 'टेलीग्राम अपडेट', 'Unlink Telegram': 'टेलीग्राम हटाएं',
        'Open Telegram & Link Account': 'टेलीग्राम खोलें और खाता जोड़ें', 'No notifications yet.': 'अभी कोई सूचना नहीं है।',
        'Operations desk': 'संचालन डेस्क', "Today's queue, at a glance.": 'आज की कतार, एक नज़र में।',
        'Move farmers through procurement with a clear live queue, fast check-in, and payment visibility.': 'लाइव कतार, तेज चेक-इन और स्पष्ट भुगतान जानकारी के साथ खरीद प्रक्रिया चलाएं।',
        'Now serving': 'अभी सेवा में', 'Serve next token →': 'अगला टोकन सेवा में लें →', 'Farmer': 'किसान',
        'Mobile': 'मोबाइल', 'Actions': 'कार्रवाई', 'No bookings for this centre/date.': 'इस केंद्र और तारीख के लिए कोई बुकिंग नहीं है।',
        'Performance pulse': 'प्रदर्शन सारांश', 'Live database view': 'लाइव डेटाबेस दृश्य', 'Total bookings': 'कुल बुकिंग',
        'Completed': 'पूरी हुई', 'No-shows': 'अनुपस्थित', 'Pending payments': 'लंबित भुगतान', 'Total Payments Processed': 'कुल संसाधित भुगतान',
        'Bookings per Centre': 'केंद्र के अनुसार बुकिंग', 'Centre throughput': 'केंद्र का प्रदर्शन', 'Bookings by centre': 'केंद्र के अनुसार बुकिंग',
        'Market prices & MSP': 'बाजार भाव और एमएसपी', 'Add price': 'भाव जोड़ें', 'Market price': 'बाजार भाव',
        'MSP': 'एमएसपी', 'Updated': 'अपडेट किया गया', 'Staff action history': 'कर्मचारी कार्रवाई इतिहास',
        'When': 'समय', 'Actor': 'कर्ता', 'Action': 'कार्रवाई', 'Entity': 'इकाई', 'Details': 'विवरण',
        'Slot Management': 'स्लॉट प्रबंधन', 'Add / Update a Slot': 'स्लॉट जोड़ें / अपडेट करें', 'Capacity': 'क्षमता',
        'Save Slot': 'स्लॉट सेव करें', 'Check In': 'चेक-इन', 'Confirm check-in': 'चेक-इन की पुष्टि करें',
        'Enter your registered mobile number. We\'ll send a one-time code to verify it\'s you.': 'अपना पंजीकृत मोबाइल नंबर दर्ज करें। पहचान सत्यापित करने के लिए एक बार का कोड भेजा जाएगा।',
        'Mobile Number': 'मोबाइल नंबर', 'Send OTP': 'ओटीपी भेजें', 'New here?': 'नए उपयोगकर्ता हैं?', 'Create your account': 'अपना खाता बनाएं',
        'Full Name': 'पूरा नाम', 'Email': 'ईमेल', 'Account Type': 'खाता प्रकार', 'Already have an account?': 'पहले से खाता है?',
        'Verify OTP': 'ओटीपी सत्यापित करें', 'One-Time Password': 'एक बार का पासवर्ड', 'Verify & Continue': 'सत्यापित करें और आगे बढ़ें',
        'Resend OTP': 'ओटीपी फिर भेजें', 'Farmer Procurement System': 'किसान खरीद प्रणाली', 'completed': 'पूरा हुआ', 'paid': 'भुगतान हुआ', 'pending': 'लंबित', 'booked': 'बुक किया गया', 'serving': 'सेवा में', 'cancelled': 'रद्द', 'no_show': 'अनुपस्थित', 'Crop:': 'फसल:', 'Quantity:': 'मात्रा:', 'Token Number:': 'टोकन नंबर:', 'Estimated wait:': 'अनुमानित प्रतीक्षा:', 'Wheat': 'गेहूं', 'Rice (Paddy)': 'धान', 'Maize': 'मक्का', 'Soybean': 'सोयाबीन', 'Cotton': 'कपास', 'Sugarcane': 'गन्ना', 'Other': 'अन्य', 'mandi prices': 'मंडी भाव', 'live market board': 'लाइव मंडी भाव', 'compare today\'s market rate with the government MSP floor.': 'आज के बाजार भाव की सरकारी एमएसपी सीमा से तुलना करें।', 'book a slot': 'स्लॉट बुक करें', 'procurement centres': 'खरीद केंद्र', 'choose a location': 'स्थान चुनें', 'per quintal': 'प्रति क्विंटल', 'msp floor': 'एमएसपी सीमा', 'above MSP': 'एमएसपी से अधिक', 'below MSP': 'एमएसपी से कम', 'First update': 'पहला अपडेट', 'Updated': 'अपडेट किया गया', 'Select a centre': 'केंद्र चुनें', 'slot booking · queue operations · fair payments': 'स्लॉट बुकिंग · कतार संचालन · उचित भुगतान', 'Farmer-first procurement': 'किसानों के लिए आसान खरीद', 'Sell with clarity.': 'स्पष्टता से बेचें।', 'Move with confidence.': 'विश्वास के साथ आगे बढ़ें।', 'A calmer way to reach the market.': 'बाजार तक पहुंचने का आसान तरीका।', 'Secure access': 'सुरक्षित प्रवेश', 'One small step': 'एक छोटा कदम', 'to your market day.': 'आपके बाजार दिवस की ओर।'
    },
    kn: {
        'Farmer Procurement': 'ರೈತ ಖರೀದಿ', 'mandi operations': 'ಮಾರುಕಟ್ಟೆ ಕಾರ್ಯಾಚರಣೆ', 'Login': 'ಲಾಗಿನ್', 'Register': 'ನೋಂದಣಿ',
        'Dashboard': 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್', 'Book Slot': 'ಸ್ಲಾಟ್ ಬುಕ್ ಮಾಡಿ', 'History': 'ಇತಿಹಾಸ', 'Mandi Prices': 'ಮಾರುಕಟ್ಟೆ ದರ',
        'Notifications': 'ಸೂಚನೆಗಳು', 'Logout': 'ಲಾಗ್ ಔಟ್', 'Queue Dashboard': 'ಸರದಿ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್', 'Manage Slots': 'ಸ್ಲಾಟ್ ನಿರ್ವಹಣೆ',
        'Analytics': 'ವಿಶ್ಲೇಷಣೆ', 'Prices': 'ಮಾರುಕಟ್ಟೆ ದರ', 'Audit Log': 'ಆಡಿಟ್ ದಾಖಲೆ', 'Language': 'ಭಾಷೆ',
        'Farmer workspace': 'ರೈತ ಕಾರ್ಯಕ್ಷೇತ್ರ', 'Welcome back,': 'ಮರಳಿ ಸ್ವಾಗತ,', 'Upcoming Slot': 'ಮುಂದಿನ ಸ್ಲಾಟ್',
        'Recent History': 'ಇತ್ತೀಚಿನ ಇತಿಹಾಸ', 'You have no upcoming procurement slot booked.': 'ನೀವು ಇನ್ನೂ ಯಾವುದೇ ಖರೀದಿ ಸ್ಲಾಟ್ ಬುಕ್ ಮಾಡಿಲ್ಲ.',
        'Book a Slot': 'ಸ್ಲಾಟ್ ಬುಕ್ ಮಾಡಿ', 'View full history →': 'ಪೂರ್ಣ ಇತಿಹಾಸ ನೋಡಿ →', 'Procurement History': 'ಖರೀದಿ ಇತಿಹಾಸ',
        'Date': 'ದಿನಾಂಕ', 'Centre': 'ಕೇಂದ್ರ', 'Crop': 'ಬೆಳೆ', 'Qty (kg)': 'ಪ್ರಮಾಣ (ಕೆಜಿ)', 'Token': 'ಟೋಕನ್',
        'Status': 'ಸ್ಥಿತಿ', 'Payment': 'ಪಾವತಿ', 'Timeline': 'ಸಮಯರೇಖೆ', 'PDF': 'ಪಿಡಿಎಫ್', 'No bookings yet.': 'ಇನ್ನೂ ಯಾವುದೇ ಬುಕಿಂಗ್ ಇಲ್ಲ.',
        'Book a Procurement Slot': 'ಖರೀದಿ ಸ್ಲಾಟ್ ಬುಕ್ ಮಾಡಿ', 'Crop Type': 'ಬೆಳೆಯ ವಿಧ', 'Select crop': 'ಬೆಳೆ ಆಯ್ಕೆಮಾಡಿ',
        'Quantity (kg)': 'ಪ್ರಮಾಣ (ಕೆಜಿ)', 'Procurement Centre': 'ಖರೀದಿ ಕೇಂದ್ರ', 'Select centre': 'ಕೇಂದ್ರ ಆಯ್ಕೆಮಾಡಿ',
        'Available Date & Time Slot': 'ಲಭ್ಯವಿರುವ ದಿನಾಂಕ ಮತ್ತು ಸಮಯದ ಸ್ಲಾಟ್', 'Select a centre first': 'ಮೊದಲು ಕೇಂದ್ರ ಆಯ್ಕೆಮಾಡಿ',
        'No slots available': 'ಯಾವುದೇ ಸ್ಲಾಟ್ ಲಭ್ಯವಿಲ್ಲ', 'Confirm Booking': 'ಬುಕಿಂಗ್ ದೃಢೀಕರಿಸಿ',
        'Live Queue Status': 'ಲೈವ್ ಸರದಿ ಸ್ಥಿತಿ', 'Now Serving': 'ಈಗ ಸೇವೆಯಲ್ಲಿ', 'Your Token': 'ನಿಮ್ಮ ಟೋಕನ್',
        "It's your turn — please proceed to the counter!": 'ನಿಮ್ಮ ಸರದಿ ಬಂದಿದೆ — ದಯವಿಟ್ಟು ಕೌಂಟರ್‌ಗೆ ಹೋಗಿ!',
        'Procurement completed': 'ಖರೀದಿ ಪೂರ್ಣಗೊಂಡಿದೆ', 'Marked as no-show': 'ಹಾಜರಾಗಿಲ್ಲ ಎಂದು ಗುರುತಿಸಲಾಗಿದೆ',
        'Estimated wait:': 'ಅಂದಾಜು ಕಾಯುವಿಕೆ:', 'minutes': 'ನಿಮಿಷ', 'View Full Timeline': 'ಪೂರ್ಣ ಸಮಯರೇಖೆ ನೋಡಿ',
        'Procurement & Payment Tracker': 'ಖರೀದಿ ಮತ್ತು ಪಾವತಿ ಟ್ರ್ಯಾಕರ್', 'Payment received': 'ಪಾವತಿ ಸ್ವೀಕರಿಸಲಾಗಿದೆ',
        'Telegram Updates': 'ಟೆಲಿಗ್ರಾಂ ಅಪ್‌ಡೇಟ್‌ಗಳು', 'Unlink Telegram': 'ಟೆಲಿಗ್ರಾಂ ಸಂಪರ್ಕ ತೆಗೆದುಹಾಕಿ',
        'Open Telegram & Link Account': 'ಟೆಲಿಗ್ರಾಂ ತೆರೆಯಿರಿ ಮತ್ತು ಖಾತೆ ಜೋಡಿಸಿ', 'No notifications yet.': 'ಇನ್ನೂ ಯಾವುದೇ ಸೂಚನೆಗಳಿಲ್ಲ.',
        'Operations desk': 'ಕಾರ್ಯಾಚರಣೆ ಡೆಸ್ಕ್', "Today's queue, at a glance.": 'ಇಂದಿನ ಸರದಿ, ಒಂದೇ ನೋಟದಲ್ಲಿ.',
        'Move farmers through procurement with a clear live queue, fast check-in, and payment visibility.': 'ಸ್ಪಷ್ಟ ಲೈವ್ ಸರದಿ, ವೇಗದ ಚೆಕ್-ಇನ್ ಮತ್ತು ಪಾವತಿ ಮಾಹಿತಿಯೊಂದಿಗೆ ಖರೀದಿ ಪ್ರಕ್ರಿಯೆ ನಡೆಸಿ.',
        'Now serving': 'ಈಗ ಸೇವೆಯಲ್ಲಿ', 'Serve next token →': 'ಮುಂದಿನ ಟೋಕನ್ ಸೇವೆಗೆ →', 'Farmer': 'ರೈತ',
        'Mobile': 'ಮೊಬೈಲ್', 'Actions': 'ಕಾರ್ಯಗಳು', 'No bookings for this centre/date.': 'ಈ ಕೇಂದ್ರ ಮತ್ತು ದಿನಾಂಕಕ್ಕೆ ಯಾವುದೇ ಬುಕಿಂಗ್ ಇಲ್ಲ.',
        'Performance pulse': 'ಕಾರ್ಯಕ್ಷಮತೆ ಸಾರಾಂಶ', 'Live database view': 'ಲೈವ್ ಡೇಟಾಬೇಸ್ ನೋಟ', 'Total bookings': 'ಒಟ್ಟು ಬುಕಿಂಗ್',
        'Completed': 'ಪೂರ್ಣಗೊಂಡವು', 'No-shows': 'ಹಾಜರಾಗದವರು', 'Pending payments': 'ಬಾಕಿ ಪಾವತಿಗಳು', 'Total Payments Processed': 'ಒಟ್ಟು ಪ್ರಕ್ರಿಯೆಗೊಂಡ ಪಾವತಿ',
        'Bookings per Centre': 'ಕೇಂದ್ರದ ಪ್ರಕಾರ ಬುಕಿಂಗ್', 'Centre throughput': 'ಕೇಂದ್ರದ ಕಾರ್ಯಕ್ಷಮತೆ', 'Bookings by centre': 'ಕೇಂದ್ರದ ಪ್ರಕಾರ ಬುಕಿಂಗ್',
        'Market prices & MSP': 'ಮಾರುಕಟ್ಟೆ ದರ ಮತ್ತು ಎಂಎಸ್‌ಪಿ', 'Add price': 'ದರ ಸೇರಿಸಿ', 'Market price': 'ಮಾರುಕಟ್ಟೆ ದರ',
        'MSP': 'ಎಂಎಸ್‌ಪಿ', 'Updated': 'ಅಪ್‌ಡೇಟ್ ಮಾಡಲಾಗಿದೆ', 'Staff action history': 'ಸಿಬ್ಬಂದಿ ಕಾರ್ಯ ಇತಿಹಾಸ',
        'When': 'ಸಮಯ', 'Actor': 'ಕರ್ತೃ', 'Action': 'ಕಾರ್ಯ', 'Entity': 'ಘಟಕ', 'Details': 'ವಿವರಗಳು',
        'Slot Management': 'ಸ್ಲಾಟ್ ನಿರ್ವಹಣೆ', 'Add / Update a Slot': 'ಸ್ಲಾಟ್ ಸೇರಿಸಿ / ಅಪ್‌ಡೇಟ್ ಮಾಡಿ', 'Capacity': 'ಸಾಮರ್ಥ್ಯ',
        'Save Slot': 'ಸ್ಲಾಟ್ ಉಳಿಸಿ', 'Check In': 'ಚೆಕ್-ಇನ್', 'Confirm check-in': 'ಚೆಕ್-ಇನ್ ದೃಢೀಕರಿಸಿ',
        'Enter your registered mobile number. We\'ll send a one-time code to verify it\'s you.': 'ನಿಮ್ಮ ನೋಂದಾಯಿತ ಮೊಬೈಲ್ ಸಂಖ್ಯೆಯನ್ನು ನಮೂದಿಸಿ. ನಿಮ್ಮ ಗುರುತನ್ನು ಪರಿಶೀಲಿಸಲು ಒಮ್ಮೆ ಬಳಕೆಯ ಕೋಡ್ ಕಳುಹಿಸಲಾಗುತ್ತದೆ.',
        'Mobile Number': 'ಮೊಬೈಲ್ ಸಂಖ್ಯೆ', 'Send OTP': 'ಒಟಿಪಿ ಕಳುಹಿಸಿ', 'New here?': 'ಹೊಸ ಬಳಕೆದಾರರೇ?', 'Create your account': 'ನಿಮ್ಮ ಖಾತೆ ರಚಿಸಿ',
        'Full Name': 'ಪೂರ್ಣ ಹೆಸರು', 'Email': 'ಇಮೇಲ್', 'Account Type': 'ಖಾತೆ ಪ್ರಕಾರ', 'Already have an account?': 'ಈಗಾಗಲೇ ಖಾತೆ ಇದೆಯೇ?',
        'Verify OTP': 'ಒಟಿಪಿ ಪರಿಶೀಲಿಸಿ', 'One-Time Password': 'ಒಮ್ಮೆ ಬಳಕೆಯ ಪಾಸ್‌ವರ್ಡ್', 'Verify & Continue': 'ಪರಿಶೀಲಿಸಿ ಮತ್ತು ಮುಂದುವರಿಯಿರಿ',
        'Resend OTP': 'ಒಟಿಪಿ ಮತ್ತೆ ಕಳುಹಿಸಿ', 'Farmer Procurement System': 'ರೈತ ಖರೀದಿ ವ್ಯವಸ್ಥೆ', 'completed': 'ಪೂರ್ಣಗೊಂಡಿದೆ', 'paid': 'ಪಾವತಿಸಲಾಗಿದೆ', 'pending': 'ಬಾಕಿ', 'booked': 'ಬುಕ್ ಮಾಡಲಾಗಿದೆ', 'serving': 'ಸೇವೆಯಲ್ಲಿ', 'cancelled': 'ರದ್ದಾಗಿದೆ', 'no_show': 'ಹಾಜರಾಗಿಲ್ಲ', 'Crop:': 'ಬೆಳೆ:', 'Quantity:': 'ಪ್ರಮಾಣ:', 'Token Number:': 'ಟೋಕನ್ ಸಂಖ್ಯೆ:', 'Estimated wait:': 'ಅಂದಾಜು ಕಾಯುವಿಕೆ:', 'Wheat': 'ಗೋಧಿ', 'Rice (Paddy)': 'ಭತ್ತ', 'Maize': 'ಮೆಕ್ಕೆಜೋಳ', 'Soybean': 'ಸೋಯಾಬೀನ್', 'Cotton': 'ಹತ್ತಿ', 'Sugarcane': 'ಕಬ್ಬು', 'Other': 'ಇತರೆ', 'mandi prices': 'ಮಾರುಕಟ್ಟೆ ದರ', 'live market board': 'ಲೈವ್ ಮಾರುಕಟ್ಟೆ ದರ', 'compare today\'s market rate with the government MSP floor.': 'ಇಂದಿನ ಮಾರುಕಟ್ಟೆ ದರವನ್ನು ಸರ್ಕಾರಿ ಎಂಎಸ್‌ಪಿ ಮಿತಿಯೊಂದಿಗೆ ಹೋಲಿಸಿ.', 'book a slot': 'ಸ್ಲಾಟ್ ಬುಕ್ ಮಾಡಿ', 'procurement centres': 'ಖರೀದಿ ಕೇಂದ್ರಗಳು', 'choose a location': 'ಸ್ಥಳ ಆಯ್ಕೆಮಾಡಿ', 'per quintal': 'ಪ್ರತಿ ಕ್ವಿಂಟಲ್', 'msp floor': 'ಎಂಎಸ್‌ಪಿ ಮಿತಿ', 'above MSP': 'ಎಂಎಸ್‌ಪಿಗಿಂತ ಹೆಚ್ಚು', 'below MSP': 'ಎಂಎಸ್‌ಪಿಗಿಂತ ಕಡಿಮೆ', 'First update': 'ಮೊದಲ ಅಪ್‌ಡೇಟ್', 'Updated': 'ಅಪ್‌ಡೇಟ್ ಮಾಡಲಾಗಿದೆ', 'Select a centre': 'ಕೇಂದ್ರ ಆಯ್ಕೆಮಾಡಿ', 'slot booking · queue operations · fair payments': 'ಸ್ಲಾಟ್ ಬುಕಿಂಗ್ · ಸರದಿ ಕಾರ್ಯಾಚರಣೆ · ನ್ಯಾಯಯುತ ಪಾವತಿಗಳು', 'Farmer-first procurement': 'ರೈತರಿಗಾಗಿ ಸುಲಭ ಖರೀದಿ', 'Sell with clarity.': 'ಸ್ಪಷ್ಟವಾಗಿ ಮಾರಾಟ ಮಾಡಿ.', 'Move with confidence.': 'ವಿಶ್ವಾಸದಿಂದ ಮುಂದುವರಿಯಿರಿ.', 'A calmer way to reach the market.': 'ಮಾರುಕಟ್ಟೆ ತಲುಪಲು ಸುಲಭವಾದ ಮಾರ್ಗ.', 'Secure access': 'ಸುರಕ್ಷಿತ ಪ್ರವೇಶ', 'One small step': 'ಒಂದು ಸಣ್ಣ ಹೆಜ್ಜೆ', 'to your market day.': 'ನಿಮ್ಮ ಮಾರುಕಟ್ಟೆ ದಿನದತ್ತ.'
    }
};

const extraTranslations = {
    hi: {
        'Farmer portal': 'किसान पोर्टल', 'Staff console': 'कर्मचारी कंसोल', 'System online': 'सिस्टम ऑनलाइन', 'Login': 'लॉग इन', 'Register': 'पंजीकरण',
        'Farmer-first procurement': 'किसानों के लिए आसान खरीद', 'A better mandi day': 'बेहतर मंडी दिवस', 'Sell with clarity.': 'स्पष्टता से बेचें।', 'Move with confidence.': 'विश्वास के साथ आगे बढ़ें।', 'Your crop.': 'आपकी फसल।', 'Your turn.': 'आपकी बारी।', 'Secure access': 'सुरक्षित प्रवेश', 'One small step': 'एक छोटा कदम', 'to your market day.': 'आपके बाजार दिवस की ओर।',
        'Book a mandi slot, follow your token, and keep your payment journey visible from field to counter.': 'मंडी स्लॉट बुक करें, अपना टोकन देखें और खेत से काउंटर तक भुगतान की जानकारी पाएं।', 'Create your farmer account to reserve a slot, see market prices, and get queue updates without the waiting-room guesswork.': 'स्लॉट आरक्षित करने, बाजार भाव देखने और कतार अपडेट पाने के लिए किसान खाता बनाएं।', 'Use the one-time code sent to your registered number. Your booking and payment history stay tied to your account.': 'अपने पंजीकृत नंबर पर भेजा गया एक बार का कोड दर्ज करें। आपकी बुकिंग और भुगतान इतिहास आपके खाते से जुड़े रहेंगे।', 'A calmer way to reach the market.': 'बाजार तक पहुंचने का आसान तरीका।', 'Simple booking. Fair visibility.': 'सरल बुकिंग। स्पष्ट जानकारी।',
        'Choose crop and centre': 'फसल और केंद्र चुनें', 'Check mandi prices': 'मंडी भाव देखें', 'Compare market and MSP': 'बाजार भाव और एमएसपी की तुलना करें', 'Open updates': 'अपडेट खोलें', 'Queue and payment alerts': 'कतार और भुगतान अलर्ट', 'Upcoming Slot': 'आगामी स्लॉट', 'Recent History': 'हाल का इतिहास', 'Live Queue Status': 'लाइव कतार स्थिति', 'Track Progress': 'प्रगति देखें', 'PDF Receipt': 'पीडीएफ रसीद', 'Cancel Booking': 'बुकिंग रद्द करें', 'You have no upcoming procurement slot booked.': 'आपने अभी तक कोई खरीद स्लॉट बुक नहीं किया है।', 'No past procurement history yet.': 'अभी कोई पुराना खरीद इतिहास नहीं है।', 'View full history →': 'पूरा इतिहास देखें →', 'New booking →': 'नई बुकिंग →',
        'Plan your mandi visit': 'अपनी मंडी यात्रा की योजना बनाएं', 'Book a procurement slot': 'खरीद स्लॉट बुक करें', 'Select your crop, preferred centre, and a time that works for your harvest day.': 'अपनी फसल, पसंदीदा केंद्र और सुविधाजनक समय चुनें।', 'Step 1 of 1': 'चरण 1 / 1', 'Tell us about your harvest': 'अपनी फसल के बारे में बताएं', 'We use this to prepare your procurement visit.': 'इससे आपकी खरीद यात्रा तैयार की जाएगी।', 'Confirm booking': 'बुकिंग की पुष्टि करें', 'Select a slot': 'स्लॉट चुनें', 'No slots available': 'कोई स्लॉट उपलब्ध नहीं है', 'left': 'बाकी', 'available': 'उपलब्ध', 'e.g. 09:00 - 11:00': 'उदाहरण: 09:00 - 11:00',
        'Your records': 'आपके रिकॉर्ड', 'Every slot, token, payment, and receipt in one calm timeline.': 'हर स्लॉट, टोकन, भुगतान और रसीद एक जगह।', 'Stay in the loop': 'अपडेट से जुड़े रहें', 'Queue calls, payment confirmations, and updates from your centre.': 'कतार कॉल, भुगतान पुष्टि और केंद्र के अपडेट।', 'Live updates': 'लाइव अपडेट', 'Your market-day view': 'आपके बाजार दिवस का दृश्य', 'Keep an eye on the counter from wherever you are.': 'जहां भी हों, काउंटर की स्थिति देखें।', 'One clear journey': 'एक स्पष्ट यात्रा', 'Follow each step from your booked slot to the final payment.': 'बुक किए गए स्लॉट से अंतिम भुगतान तक हर चरण देखें।',
        'Operations desk': 'संचालन डेस्क', "Today's queue": 'आज की कतार', 'Keep the centre moving with a clear live queue, fast check-in, and payment visibility.': 'लाइव कतार, तेज चेक-इन और भुगतान जानकारी के साथ केंद्र को सुचारु रखें।', 'Live operations': 'लाइव संचालन', 'Serve next token →': 'अगला टोकन सेवा में लें →', 'Mark Paid': 'भुगतान दर्ज करें', 'No-Show': 'अनुपस्थित', 'No bookings for this centre/date.': 'इस केंद्र और तारीख के लिए कोई बुकिंग नहीं है।', 'No procurement centres configured yet.': 'अभी कोई खरीद केंद्र configured नहीं है।',
        'Centre planning': 'केंद्र योजना', 'Slot management': 'स्लॉट प्रबंधन', 'Shape the day around real capacity and farmer demand.': 'क्षमता और किसान मांग के अनुसार दिन की योजना बनाएं।', 'Add / Update a Slot': 'स्लॉट जोड़ें / अपडेट करें', 'Time Slot': 'समय स्लॉट', 'Save': 'सेव करें', 'Booked': 'बुक किए गए', 'Available': 'उपलब्ध', 'Capacity': 'क्षमता',
        'Staff control': 'कर्मचारी नियंत्रण', 'Publish the prices farmers use to plan their procurement visit.': 'किसानों की खरीद योजना के लिए बाजार भाव प्रकाशित करें।', 'Crop type': 'फसल का प्रकार', 'Market name': 'बाजार का नाम', 'MSP / qtl': 'एमएसपी / क्विंटल', 'Market / qtl': 'बाजार / क्विंटल', 'Add price': 'भाव जोड़ें',
        'Accountability': 'जवाबदेही', 'Staff action history': 'कर्मचारी कार्रवाई इतिहास', 'A durable record of changes made across the centre.': 'केंद्र में किए गए बदलावों का स्थायी रिकॉर्ड।', 'System': 'सिस्टम', 'No staff actions recorded.': 'अभी कोई कर्मचारी कार्रवाई दर्ज नहीं है।', 'QR check-in': 'क्यूआर चेक-इन', 'Checked in at': 'चेक-इन समय', 'Confirm check-in': 'चेक-इन की पुष्टि करें', 'Get instant updates on Telegram instead of waiting for email.': 'ईमेल की प्रतीक्षा के बजाय टेलीग्राम पर तुरंत अपडेट पाएं।', 'Telegram linking is not configured yet.': 'टेलीग्राम लिंकिंग अभी configured नहीं है।', 'Unlink Telegram': 'टेलीग्राम हटाएं', 'No notifications yet.': 'अभी कोई सूचना नहीं है।',
        'We sent a 6-digit code to': 'हमने 6 अंकों का कोड भेजा है:', 'Enter OTP': 'ओटीपी दर्ज करें', "Didn't get it?": 'कोड नहीं मिला?', 'optional, used for email notifications': 'वैकल्पिक, ईमेल सूचनाओं के लिए', 'Admin / Centre Staff (demo only)': 'व्यवस्थापक / केंद्र कर्मचारी (केवल डेमो)', 'In production, admin/staff accounts would be provisioned separately, not self-registered.': 'उत्पादन में कर्मचारी खाते अलग से बनाए जाएंगे।', 'e.g. 9876543210': 'उदाहरण: 9876543210',
        'No data yet.': 'अभी कोई डेटा नहीं है।', 'Bookings by centre': 'केंद्र के अनुसार बुकिंग', 'bookings': 'बुकिंग', 'Live database view': 'लाइव डेटाबेस दृश्य', 'Performance pulse': 'प्रदर्शन सारांश', 'Small signals for faster decisions across every centre.': 'हर केंद्र के लिए तेज निर्णय हेतु छोटे संकेत।', 'Total Payments Processed': 'कुल संसाधित भुगतान', 'Bookings per Centre': 'केंद्र के अनुसार बुकिंग', 'Centre throughput': 'केंद्र का प्रदर्शन', 'No bookings yet.': 'अभी कोई बुकिंग नहीं है।', 'Slot booking · queue operations · fair payments': 'स्लॉट बुकिंग · कतार संचालन · उचित भुगतान'
    },
    kn: {
        'Farmer portal': 'ರೈತ ಪೋರ್ಟಲ್', 'Staff console': 'ಸಿಬ್ಬಂದಿ ಕಾನ್ಸೋಲ್', 'System online': 'ಸಿಸ್ಟಮ್ ಆನ್‌ಲೈನ್', 'Farmer-first procurement': 'ರೈತರಿಗಾಗಿ ಸುಲಭ ಖರೀದಿ', 'A better mandi day': 'ಉತ್ತಮ ಮಾರುಕಟ್ಟೆ ದಿನ', 'Sell with clarity.': 'ಸ್ಪಷ್ಟವಾಗಿ ಮಾರಾಟ ಮಾಡಿ.', 'Move with confidence.': 'ವಿಶ್ವಾಸದಿಂದ ಮುಂದುವರಿಯಿರಿ.', 'Your crop.': 'ನಿಮ್ಮ ಬೆಳೆ.', 'Your turn.': 'ನಿಮ್ಮ ಸರದಿ.', 'Secure access': 'ಸುರಕ್ಷಿತ ಪ್ರವೇಶ', 'One small step': 'ಒಂದು ಸಣ್ಣ ಹೆಜ್ಜೆ', 'to your market day.': 'ನಿಮ್ಮ ಮಾರುಕಟ್ಟೆ ದಿನದತ್ತ.',
        'Book a mandi slot, follow your token, and keep your payment journey visible from field to counter.': 'ಮಾರುಕಟ್ಟೆ ಸ್ಲಾಟ್ ಬುಕ್ ಮಾಡಿ, ನಿಮ್ಮ ಟೋಕನ್ ನೋಡಿ ಮತ್ತು ಹೊಲದಿಂದ ಕೌಂಟರ್‌ವರೆಗೆ ಪಾವತಿ ಮಾಹಿತಿ ಪಡೆಯಿರಿ.', 'Create your farmer account to reserve a slot, see market prices, and get queue updates without the waiting-room guesswork.': 'ಸ್ಲಾಟ್ ಕಾಯ್ದಿರಿಸಲು, ಮಾರುಕಟ್ಟೆ ದರ ನೋಡಲು ಮತ್ತು ಸರದಿ ಅಪ್‌ಡೇಟ್ ಪಡೆಯಲು ರೈತ ಖಾತೆ ರಚಿಸಿ.', 'Use the one-time code sent to your registered number. Your booking and payment history stay tied to your account.': 'ನಿಮ್ಮ ನೋಂದಾಯಿತ ಸಂಖ್ಯೆಗೆ ಕಳುಹಿಸಿದ ಒಮ್ಮೆ ಬಳಕೆಯ ಕೋಡ್ ಬಳಸಿ. ನಿಮ್ಮ ಬುಕಿಂಗ್ ಮತ್ತು ಪಾವತಿ ಇತಿಹಾಸ ಖಾತೆಗೆ ಜೋಡಿಸಲಾಗುತ್ತದೆ.', 'A calmer way to reach the market.': 'ಮಾರುಕಟ್ಟೆ ತಲುಪಲು ಸುಲಭವಾದ ಮಾರ್ಗ.', 'Simple booking. Fair visibility.': 'ಸರಳ ಬುಕಿಂಗ್. ಸ್ಪಷ್ಟ ಮಾಹಿತಿ.',
        'Choose crop and centre': 'ಬೆಳೆ ಮತ್ತು ಕೇಂದ್ರ ಆಯ್ಕೆಮಾಡಿ', 'Check mandi prices': 'ಮಾರುಕಟ್ಟೆ ದರ ನೋಡಿ', 'Compare market and MSP': 'ಮಾರುಕಟ್ಟೆ ದರ ಮತ್ತು ಎಂಎಸ್‌ಪಿ ಹೋಲಿಸಿ', 'Open updates': 'ಅಪ್‌ಡೇಟ್ ತೆರೆಯಿರಿ', 'Queue and payment alerts': 'ಸರದಿ ಮತ್ತು ಪಾವತಿ ಎಚ್ಚರಿಕೆಗಳು', 'Upcoming Slot': 'ಮುಂದಿನ ಸ್ಲಾಟ್', 'Recent History': 'ಇತ್ತೀಚಿನ ಇತಿಹಾಸ', 'Live Queue Status': 'ಲೈವ್ ಸರದಿ ಸ್ಥಿತಿ', 'Track Progress': 'ಪ್ರಗತಿ ನೋಡಿ', 'PDF Receipt': 'ಪಿಡಿಎಫ್ ರಸೀದಿ', 'Cancel Booking': 'ಬುಕಿಂಗ್ ರದ್ದುಮಾಡಿ', 'View full history →': 'ಪೂರ್ಣ ಇತಿಹಾಸ ನೋಡಿ →', 'New booking →': 'ಹೊಸ ಬುಕಿಂಗ್ →', 'No past procurement history yet.': 'ಇನ್ನೂ ಹಳೆಯ ಖರೀದಿ ಇತಿಹಾಸ ಇಲ್ಲ.',
        'Plan your mandi visit': 'ನಿಮ್ಮ ಮಾರುಕಟ್ಟೆ ಭೇಟಿಯ ಯೋಜನೆ', 'Book a procurement slot': 'ಖರೀದಿ ಸ್ಲಾಟ್ ಬುಕ್ ಮಾಡಿ', 'Select your crop, preferred centre, and a time that works for your harvest day.': 'ನಿಮ್ಮ ಬೆಳೆ, ಇಷ್ಟದ ಕೇಂದ್ರ ಮತ್ತು ಅನುಕೂಲಕರ ಸಮಯ ಆಯ್ಕೆಮಾಡಿ.', 'Step 1 of 1': 'ಹಂತ 1 / 1', 'Tell us about your harvest': 'ನಿಮ್ಮ ಬೆಳೆಯ ಬಗ್ಗೆ ತಿಳಿಸಿ', 'We use this to prepare your procurement visit.': 'ನಿಮ್ಮ ಖರೀದಿ ಭೇಟಿಯನ್ನು ಸಿದ್ಧಪಡಿಸಲು ಇದನ್ನು ಬಳಸುತ್ತೇವೆ.', 'Confirm booking': 'ಬುಕಿಂಗ್ ದೃಢೀಕರಿಸಿ', 'Select a slot': 'ಸ್ಲಾಟ್ ಆಯ್ಕೆಮಾಡಿ', 'No slots available': 'ಯಾವುದೇ ಸ್ಲಾಟ್ ಲಭ್ಯವಿಲ್ಲ', 'left': 'ಉಳಿದಿದೆ', 'available': 'ಲಭ್ಯವಿದೆ', 'e.g. 09:00 - 11:00': 'ಉದಾ: 09:00 - 11:00',
        'Your records': 'ನಿಮ್ಮ ದಾಖಲೆಗಳು', 'Every slot, token, payment, and receipt in one calm timeline.': 'ಪ್ರತಿ ಸ್ಲಾಟ್, ಟೋಕನ್, ಪಾವತಿ ಮತ್ತು ರಸೀದಿ ಒಂದೇ ಸ್ಥಳದಲ್ಲಿ.', 'Stay in the loop': 'ಅಪ್‌ಡೇಟ್‌ಗಳೊಂದಿಗೆ ಇರಿ', 'Queue calls, payment confirmations, and updates from your centre.': 'ಸರದಿ ಕರೆಗಳು, ಪಾವತಿ ದೃಢೀಕರಣಗಳು ಮತ್ತು ಕೇಂದ್ರದ ಅಪ್‌ಡೇಟ್‌ಗಳು.', 'Live updates': 'ಲೈವ್ ಅಪ್‌ಡೇಟ್‌ಗಳು', 'Your market-day view': 'ನಿಮ್ಮ ಮಾರುಕಟ್ಟೆ ದಿನದ ನೋಟ', 'Keep an eye on the counter from wherever you are.': 'ನೀವು ಎಲ್ಲಿದ್ದರೂ ಕೌಂಟರ್ ಸ್ಥಿತಿ ನೋಡಿ.', 'One clear journey': 'ಒಂದು ಸ್ಪಷ್ಟ ಪ್ರಯಾಣ', 'Follow each step from your booked slot to the final payment.': 'ಬುಕ್ ಮಾಡಿದ ಸ್ಲಾಟ್‌ನಿಂದ ಅಂತಿಮ ಪಾವತಿವರೆಗೆ ಪ್ರತಿ ಹಂತ ನೋಡಿ.',
        'Operations desk': 'ಕಾರ್ಯಾಚರಣೆ ಡೆಸ್ಕ್', "Today's queue": 'ಇಂದಿನ ಸರದಿ', 'Keep the centre moving with a clear live queue, fast check-in, and payment visibility.': 'ಲೈವ್ ಸರದಿ, ವೇಗದ ಚೆಕ್-ಇನ್ ಮತ್ತು ಪಾವತಿ ಮಾಹಿತಿಯೊಂದಿಗೆ ಕೇಂದ್ರವನ್ನು ಸುಗಮವಾಗಿ ನಡೆಸಿ.', 'Live operations': 'ಲೈವ್ ಕಾರ್ಯಾಚರಣೆ', 'Serve next token →': 'ಮುಂದಿನ ಟೋಕನ್ ಸೇವೆಗೆ →', 'Mark Paid': 'ಪಾವತಿ ದಾಖಲಿಸಿ', 'No-Show': 'ಹಾಜರಾಗಿಲ್ಲ', 'No bookings for this centre/date.': 'ಈ ಕೇಂದ್ರ ಮತ್ತು ದಿನಾಂಕಕ್ಕೆ ಯಾವುದೇ ಬುಕಿಂಗ್ ಇಲ್ಲ.', 'No procurement centres configured yet.': 'ಇನ್ನೂ ಯಾವುದೇ ಖರೀದಿ ಕೇಂದ್ರ ಹೊಂದಿಸಲಾಗಿಲ್ಲ.',
        'Centre planning': 'ಕೇಂದ್ರ ಯೋಜನೆ', 'Slot management': 'ಸ್ಲಾಟ್ ನಿರ್ವಹಣೆ', 'Shape the day around real capacity and farmer demand.': 'ನಿಜವಾದ ಸಾಮರ್ಥ್ಯ ಮತ್ತು ರೈತರ ಬೇಡಿಕೆಯ ಆಧಾರದ ಮೇಲೆ ದಿನವನ್ನು ಯೋಜಿಸಿ.', 'Add / Update a Slot': 'ಸ್ಲಾಟ್ ಸೇರಿಸಿ / ಅಪ್‌ಡೇಟ್ ಮಾಡಿ', 'Time Slot': 'ಸಮಯದ ಸ್ಲಾಟ್', 'Save': 'ಉಳಿಸಿ', 'Booked': 'ಬುಕ್ ಮಾಡಲಾಗಿದೆ', 'Available': 'ಲಭ್ಯವಿದೆ', 'Capacity': 'ಸಾಮರ್ಥ್ಯ',
        'Staff control': 'ಸಿಬ್ಬಂದಿ ನಿಯಂತ್ರಣ', 'Publish the prices farmers use to plan their procurement visit.': 'ರೈತರು ತಮ್ಮ ಖರೀದಿ ಭೇಟಿಯನ್ನು ಯೋಜಿಸಲು ಬಳಸುವ ದರಗಳನ್ನು ಪ್ರಕಟಿಸಿ.', 'Crop type': 'ಬೆಳೆಯ ವಿಧ', 'Market name': 'ಮಾರುಕಟ್ಟೆಯ ಹೆಸರು', 'MSP / qtl': 'ಎಂಎಸ್‌ಪಿ / ಕ್ವಿಂಟಲ್', 'Market / qtl': 'ಮಾರುಕಟ್ಟೆ / ಕ್ವಿಂಟಲ್', 'Add price': 'ದರ ಸೇರಿಸಿ',
        'Accountability': 'ಹೊಣೆಗಾರಿಕೆ', 'Staff action history': 'ಸಿಬ್ಬಂದಿ ಕಾರ್ಯ ಇತಿಹಾಸ', 'A durable record of changes made across the centre.': 'ಕೇಂದ್ರದಲ್ಲಿ ಮಾಡಿದ ಬದಲಾವಣೆಗಳ ಶಾಶ್ವತ ದಾಖಲೆ.', 'System': 'ಸಿಸ್ಟಮ್', 'No staff actions recorded.': 'ಇನ್ನೂ ಯಾವುದೇ ಸಿಬ್ಬಂದಿ ಕಾರ್ಯ ದಾಖಲಾಗಿಲ್ಲ.', 'QR check-in': 'ಕ್ಯೂಆರ್ ಚೆಕ್-ಇನ್', 'Checked in at': 'ಚೆಕ್-ಇನ್ ಸಮಯ', 'Confirm check-in': 'ಚೆಕ್-ಇನ್ ದೃಢೀಕರಿಸಿ', 'Get instant updates on Telegram instead of waiting for email.': 'ಇಮೇಲ್ ಕಾಯುವ ಬದಲು ಟೆಲಿಗ್ರಾಂನಲ್ಲಿ ತಕ್ಷಣದ ಅಪ್‌ಡೇಟ್ ಪಡೆಯಿರಿ.', 'Telegram linking is not configured yet.': 'ಟೆಲಿಗ್ರಾಂ ಜೋಡಣೆ ಇನ್ನೂ ಹೊಂದಿಸಲಾಗಿಲ್ಲ.', 'Unlink Telegram': 'ಟೆಲಿಗ್ರಾಂ ಸಂಪರ್ಕ ತೆಗೆದುಹಾಕಿ', 'No notifications yet.': 'ಇನ್ನೂ ಯಾವುದೇ ಸೂಚನೆಗಳಿಲ್ಲ.',
        'We sent a 6-digit code to': 'ನಾವು 6 ಅಂಕಿಯ ಕೋಡ್ ಕಳುಹಿಸಿದ್ದೇವೆ:', 'Enter OTP': 'ಒಟಿಪಿ ನಮೂದಿಸಿ', "Didn't get it?": 'ಕೋಡ್ ಸಿಗಲಿಲ್ಲವೇ?', 'optional, used for email notifications': 'ಐಚ್ಛಿಕ, ಇಮೇಲ್ ಸೂಚನೆಗಳಿಗಾಗಿ', 'Admin / Centre Staff (demo only)': 'ನಿರ್ವಾಹಕ / ಕೇಂದ್ರ ಸಿಬ್ಬಂದಿ (ಡೆಮೋ ಮಾತ್ರ)', 'In production, admin/staff accounts would be provisioned separately, not self-registered.': 'ಉತ್ಪಾದನಾ ವ್ಯವಸ್ಥೆಯಲ್ಲಿ ಸಿಬ್ಬಂದಿ ಖಾತೆಗಳನ್ನು ಪ್ರತ್ಯೇಕವಾಗಿ ರಚಿಸಲಾಗುತ್ತದೆ.', 'e.g. 9876543210': 'ಉದಾ: 9876543210',
        'No data yet.': 'ಇನ್ನೂ ಯಾವುದೇ ಡೇಟಾ ಇಲ್ಲ.', 'Bookings by centre': 'ಕೇಂದ್ರದ ಪ್ರಕಾರ ಬುಕಿಂಗ್', 'bookings': 'ಬುಕಿಂಗ್', 'Total Payments Processed': 'ಒಟ್ಟು ಪ್ರಕ್ರಿಯೆಗೊಂಡ ಪಾವತಿ', 'Bookings per Centre': 'ಕೇಂದ್ರದ ಪ್ರಕಾರ ಬುಕಿಂಗ್', 'Centre throughput': 'ಕೇಂದ್ರದ ಕಾರ್ಯಕ್ಷಮತೆ', 'No bookings yet.': 'ಇನ್ನೂ ಯಾವುದೇ ಬುಕಿಂಗ್ ಇಲ್ಲ.', 'Slot booking · queue operations · fair payments': 'ಸ್ಲಾಟ್ ಬುಕಿಂಗ್ · ಸರದಿ ಕಾರ್ಯಾಚರಣೆ · ನ್ಯಾಯಯುತ ಪಾವತಿಗಳು'
    }
};

extraTranslations.hi['Central Procurement Centre'] = 'केंद्रीय खरीद केंद्र';
extraTranslations.hi['North Zone Mandi'] = 'उत्तर क्षेत्र मंडी';
extraTranslations.hi['Main Market Road'] = 'मुख्य बाजार मार्ग';
extraTranslations.hi['Highway Junction'] = 'हाईवे जंक्शन';
extraTranslations.hi['Your procurement appears to be complete.'] = 'आपकी खरीद पूरी हो गई लगती है।';
extraTranslations.kn['Central Procurement Centre'] = 'ಕೇಂದ್ರ ಖರೀದಿ ಕೇಂದ್ರ';
extraTranslations.kn['North Zone Mandi'] = 'ಉತ್ತರ ವಲಯ ಮಾರುಕಟ್ಟೆ';
extraTranslations.kn['Main Market Road'] = 'ಮುಖ್ಯ ಮಾರುಕಟ್ಟೆ ರಸ್ತೆ';
extraTranslations.kn['Highway Junction'] = 'ಹೈವೇ ಜಂಕ್ಷನ್';
extraTranslations.kn['Your procurement appears to be complete.'] = 'ನಿಮ್ಮ ಖರೀದಿ ಪೂರ್ಣಗೊಂಡಿದೆ ಎಂದು ತೋರುತ್ತದೆ.';

function translatePage() {
    const language = document.documentElement.lang;
    const dictionary = {...(translations[language] || {}), ...(extraTranslations[language] || {})};
    if (!dictionary) return;
    const translate = (value) => {
        const normalized = value.replace(/\s+/g, ' ').trim();
        const translatedPhrase = dictionary[normalized] || dictionary[normalized.toLowerCase()];
        if (translatedPhrase) return value.replace(normalized, translatedPhrase);
        let translated = value;
        ['Crop:', 'Quantity:', 'Token Number:', 'Estimated wait:', 'Wheat', 'Rice (Paddy)', 'Maize', 'Soybean', 'Cotton', 'Sugarcane', 'Other', 'per quintal', 'msp floor', 'above MSP', 'below MSP', 'First update', 'Updated'].forEach((phrase) => {
            const translatedPhrase = dictionary[phrase] || dictionary[phrase.toLowerCase()];
            if (translatedPhrase) translated = translated.replaceAll(phrase, translatedPhrase);
        });
        if (language === 'hi') translated = translated.replace('Welcome back,', 'वापसी पर स्वागत है,');
        if (language === 'kn') translated = translated.replace('Welcome back,', 'ಮರಳಿ ಸ್ವಾಗತ,');
        return translated;
    };
    window.translateText = translate;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    textNodes.forEach((node) => {
        if (!['SCRIPT', 'STYLE'].includes(node.parentElement?.tagName)) node.nodeValue = translate(node.nodeValue);
    });
    document.querySelectorAll('input[placeholder], button[title], [aria-label]').forEach((element) => {
        ['placeholder', 'title', 'aria-label'].forEach((attribute) => {
            if (element.hasAttribute(attribute)) element.setAttribute(attribute, translate(element.getAttribute(attribute)));
        });
    });
    const titleParts = document.title.split(' | ');
    document.title = `${translate(titleParts[0])}${titleParts[1] ? ` | ${translate(titleParts[1])}` : ''}`;
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', translatePage);
else translatePage();
