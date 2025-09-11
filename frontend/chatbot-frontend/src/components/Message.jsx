import React from 'react';

export default function Message({ role = 'dm', content, timestamp }) {
  const isMe = role === 'me';
  const author = isMe ? 'Me' : 'DM';
  const time = timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
  return (
    <div className={`msg parchment ${isMe ? 'me' : 'dm'}`} role="group" aria-label={`${author} message`}>
      <div className="author">{author}</div>
      <div className="content">{content}</div>
      {time && <div className="time" aria-hidden="true">{time}</div>}
    </div>
  );
}

