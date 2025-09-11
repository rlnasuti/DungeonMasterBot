import React, { useCallback } from 'react';

export default function Composer({ value, setValue, onSend, disabled, inputRef }) {
  const handleKeyDown = useCallback((e) => {
    const isEnter = e.key === 'Enter';
    const isMeta = e.metaKey || e.ctrlKey; // Cmd on macOS or Ctrl on others
    if ((isEnter && !e.shiftKey) || (isEnter && isMeta)) {
      e.preventDefault();
      if (value.trim()) onSend();
    }
  }, [onSend, value]);

  return (
    <footer className="composer" role="contentinfo" aria-label="Message composer">
      <textarea
        aria-label="Message input"
        placeholder="Speak your will, adventurer…"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        ref={inputRef}
      />
      <button
        type="button"
        className="send-btn"
        aria-label="Send message"
        onClick={onSend}
        disabled={disabled || !value.trim()}
      >
        Send
      </button>
    </footer>
  );
}
