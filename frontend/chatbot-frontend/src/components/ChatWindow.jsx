import React, { useEffect, useRef, useState, useCallback } from 'react';
import Message from './Message';

export default function ChatWindow({ messages }) {
  const listRef = useRef(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  const isNearBottom = useCallback((el) => {
    if (!el) return true;
    const threshold = 8; // px
    return el.scrollHeight - el.clientHeight - el.scrollTop <= threshold;
  }, []);

  const scrollToBottom = useCallback((smooth = true) => {
    const el = listRef.current;
    if (!el) return;
    if (typeof el.scrollTo === 'function') {
      el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
    } else {
      el.scrollTop = el.scrollHeight;
    }
  }, []);

  // Track scroll position to decide whether to auto-scroll and whether to show the pill
  const onScroll = useCallback(() => {
    const el = listRef.current;
    setIsAtBottom(isNearBottom(el));
  }, [isNearBottom]);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    // Set initial position
    setIsAtBottom(isNearBottom(el));
  }, [isNearBottom]);

  useEffect(() => {
    // Auto-scroll only if user is already at bottom
    if (isAtBottom) {
      scrollToBottom(false);
    }
  }, [messages, isAtBottom, scrollToBottom]);

  return (
    <main className="chat-main" role="main" aria-label="Chat area">
      <div
        className="messages"
        ref={listRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        onScroll={onScroll}
      >
        <div className="messages-inner">
          {messages.length === 0 ? (
            <div className="parchment msg" aria-live="polite">Start your quest by sending a message…</div>
          ) : (
            messages.map((m) => (
              <Message key={m.id} role={m.role} content={m.content} timestamp={m.ts} />
            ))
          )}
        </div>
        {!isAtBottom && (
          <button
            type="button"
            className="scroll-to-latest"
            onClick={() => scrollToBottom(true)}
            aria-label="Scroll to latest messages"
          >
            ↓ Latest
          </button>
        )}
      </div>
    </main>
  );
}
