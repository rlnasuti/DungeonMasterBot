import React, { useRef, useState } from 'react';
import './App.css';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import Composer from './components/Composer';
import axios from 'axios';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const inputRef = useRef(null);

  const pushMessage = (msg) => setMessages((prev) => [...prev, { id: `${Date.now()}-${Math.random()}`, ...msg }]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;
    setSending(true);
    setInput('');
    // Immediately return focus to textarea after state update
    if (typeof window !== 'undefined') {
      window.requestAnimationFrame(() => {
        if (inputRef.current) {
          inputRef.current.focus();
          try { inputRef.current.setSelectionRange(0, 0); } catch (_) {}
        }
      });
    }

    // Add my message
    pushMessage({ role: 'me', content: text, ts: Date.now() });

    try {
      const response = await axios.post('http://localhost:8000/chat', {
        user_input: text,
      });
      const dmText = response?.data?.response ?? '';
      pushMessage({ role: 'dm', content: dmText, ts: Date.now() });
    } catch (err) {
      console.error('Failed to get response from bot:', err);
      pushMessage({ role: 'dm', content: 'The DM is silent… (error)', ts: Date.now() });
    } finally {
      setSending(false);
      // Ensure focus returns to the textarea after send completes
      if (inputRef.current) {
        inputRef.current.focus();
        try { inputRef.current.setSelectionRange(0, 0); } catch (_) {}
      }
    }
  };

  return (
    <div className="layout">
      <Sidebar />
      <ChatWindow messages={messages} />
      <Composer value={input} setValue={setInput} onSend={handleSend} disabled={sending} inputRef={inputRef} />
    </div>
  );
}

export default App;
