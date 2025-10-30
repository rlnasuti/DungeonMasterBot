import React, { useEffect, useRef, useState, useCallback, useLayoutEffect } from 'react';
import Message from './Message';

export default function ChatWindow({ messages }) {
  // Scroll container
  const listRef = useRef(null);
  // Sentinel element that sits at the very end of the list
  const bottomRef = useRef(null);
  // Track whether we should auto-scroll when new messages arrive
  const pinnedToBottomRef = useRef(true);

  const [isAtBottom, setIsAtBottom] = useState(true);
  const [needsSpacer, setNeedsSpacer] = useState(false);
  // Track previous message count to detect 0 -> >0 transition
  const prevCountRef = useRef(messages.length);

  const computeNeedsSpacer = useCallback(() => {
    const el = listRef.current;
    if (!el) return false;
    // If content height is within ~64px of the viewport height, treat as "short"
    // Padding/borders/fonts can make scrollHeight just barely exceed clientHeight.
    const slack = 64; // px
    return el.scrollHeight - el.clientHeight <= slack;
  }, []);

  // Fallback pixel threshold check (used on manual scroll)
  const nearBottom = useCallback((el) => {
    if (!el) return true;
    // Allow a small threshold so minor layout changes don't flip the flag
    const threshold = 24; // px
    return el.scrollHeight - (el.scrollTop + el.clientHeight) <= threshold;
  }, []);

  const scrollToBottom = useCallback((smooth = true) => {
    pinnedToBottomRef.current = true;
    setIsAtBottom(true);
    // Prefer the sentinel; it is more reliable with dynamic heights
    const sentinel = bottomRef.current;
    if (sentinel?.scrollIntoView) {
      sentinel.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'end' });
      return;
    }
    const el = listRef.current;
    if (el) {
      if (typeof el.scrollTo === 'function') {
        el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
      } else {
        el.scrollTop = el.scrollHeight;
      }
    }
  }, []);

  // Manual scroll handler to set the "stuck" state
  const onScroll = useCallback(() => {
    const el = listRef.current;
    const atBottom = nearBottom(el);
    setIsAtBottom(atBottom);
    pinnedToBottomRef.current = atBottom;
    setNeedsSpacer(computeNeedsSpacer());
  }, [nearBottom, computeNeedsSpacer]);

  // IntersectionObserver to track whether the bottom sentinel is visible
  useEffect(() => {
    const el = listRef.current;
    const sentinel = bottomRef.current;
    if (!el || !sentinel || !('IntersectionObserver' in window)) {
      // Initialize state with the fallback computation
      const atBottom = nearBottom(el);
      setIsAtBottom(atBottom);
      pinnedToBottomRef.current = atBottom;
      setNeedsSpacer(computeNeedsSpacer());
      return;
    }

    // Observe within the scrolling container
    const io = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        // We consider ourselves "at bottom" when the sentinel is at least partially visible
        setIsAtBottom(entry.isIntersecting);
      },
      { root: el, threshold: 0.01 }
    );

    io.observe(sentinel);
    // Also initialize using current geometry
    const atBottomInitial = nearBottom(el);
    setIsAtBottom(atBottomInitial);
    pinnedToBottomRef.current = atBottomInitial;
    setNeedsSpacer(computeNeedsSpacer());

    return () => {
      io.disconnect();
    };
  }, [nearBottom, computeNeedsSpacer]);

  useEffect(() => {
    const el = listRef.current;
    if (!el || !('ResizeObserver' in window)) {
      setNeedsSpacer(computeNeedsSpacer());
      return;
    }
    const ro = new ResizeObserver(() => {
      setNeedsSpacer(computeNeedsSpacer());
    });
    ro.observe(el);
    // Also observe font/layout changes after messages update
    setNeedsSpacer(computeNeedsSpacer());
    return () => ro.disconnect();
  }, [messages, computeNeedsSpacer]);

  // Keep anchored to bottom when new messages arrive IF already at bottom
  useEffect(() => {
    if (pinnedToBottomRef.current) {
      // Use rAF so we scroll after the DOM paints the new message
      requestAnimationFrame(() => scrollToBottom(false));
    }
  }, [messages, scrollToBottom]);

  // Force bottom alignment when messages go from 0 -> >0
  useEffect(() => {
    if (prevCountRef.current === 0 && messages.length > 0) {
      requestAnimationFrame(() => scrollToBottom(false));
    }
    prevCountRef.current = messages.length;
  }, [messages, scrollToBottom]);

  // Initial positioning on first mount
  useEffect(() => {
    // Ensure we start at bottom on first render
    requestAnimationFrame(() => scrollToBottom(false));
  }, [scrollToBottom]);

  useLayoutEffect(() => {
    setNeedsSpacer(computeNeedsSpacer());
  }, [computeNeedsSpacer]);

  return (
    <main className="chat-main" role="main" aria-label="Chat area">
      <div
        className="messages"
        ref={listRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        onScroll={onScroll}
        style={{ overflowAnchor: 'none' }}
      >
        {needsSpacer && <div className="spacer" aria-hidden="true" />}
        {messages.length === 0 ? (
          <div className="parchment msg" aria-live="polite">
            Start your quest by sending a message…
          </div>
        ) : (
          messages.map((m) => (
            <Message key={m.id} role={m.role} content={m.content} timestamp={m.ts} />
          ))
        )}
        {/* Bottom sentinel for robust "at bottom" detection */}
        <div ref={bottomRef} aria-hidden="true" style={{ height: 1 }} />
      </div>

      {!isAtBottom && (
        <button
          type="button"
          className="scroll-pill"
          onClick={() => scrollToBottom(true)}
          aria-label="Scroll to latest messages"
        >
          New messages ↓
        </button>
      )}
    </main>
  );
}
