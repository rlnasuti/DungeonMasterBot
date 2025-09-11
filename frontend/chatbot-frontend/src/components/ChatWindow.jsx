import React, { useEffect, useRef } from 'react';
import Message from './Message';

export default function ChatWindow({ messages }) {
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <main className="chat-main" role="main" aria-label="Chat messages">
      <div className="messages" ref={listRef}>
        {messages.length === 0 ? (
          <div className="parchment msg" aria-live="polite">Start your quest by sending a message…</div>
        ) : (
          messages.map((m) => (
            <Message key={m.id} role={m.role} content={m.content} timestamp={m.ts} />
          ))
        )}
      </div>
    </main>
  );
}

