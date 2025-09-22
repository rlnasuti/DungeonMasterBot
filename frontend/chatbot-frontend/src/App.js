import React, { useEffect, useRef, useState } from 'react';
import './App.css';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import Composer from './components/Composer';
import axios from 'axios';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [debug, setDebug] = useState(false);
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

  const seedMessages = (count = 30) => {
    const now = Date.now();
    const seeded = Array.from({ length: count }, (_, i) => ({
      id: `${now}-${i}`,
      role: i % 2 === 0 ? 'dm' : 'me',
      content: i % 2 === 0 ? 'The DM is silent… (seed)' : 'Seeded message',
      ts: now + i * 1000,
    }));
    setMessages(seeded);
  };

  const clearMessages = () => setMessages([]);

  // Keyboard shortcut: Shift+D toggles debug borders in development
  useEffect(() => {
    const onKey = (e) => {
      if ((e.key === 'D' || e.key === 'd') && e.shiftKey) {
        setDebug((d) => !d);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className={`layout ${debug ? 'debug' : ''}`}>
      <Sidebar />
      <ChatWindow messages={messages} />
      <Composer value={input} setValue={setInput} onSend={handleSend} disabled={sending} inputRef={inputRef} />
      {process.env.NODE_ENV !== 'production' && (
        <div className="debug-controls" role="group" aria-label="Debug controls">
          <button
            type="button"
            className="debug-toggle"
            aria-label="Toggle debug borders (Shift+D)"
            aria-pressed={debug}
            onClick={() => setDebug((d) => !d)}
            title="Toggle debug borders (Shift+D)"
          >
            {debug ? 'Debug: on' : 'Debug: off'}
          </button>
          <button type="button" className="debug-pill" onClick={() => seedMessages(40)} title="Seed 40 messages">Seed</button>
          <button type="button" className="debug-pill" onClick={clearMessages} title="Clear messages">Clear</button>
        </div>
      )}
    </div>
  );
}

export default App;
