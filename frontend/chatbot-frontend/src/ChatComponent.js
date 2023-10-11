import React, { useState } from 'react';
import axios from 'axios';

function ChatComponent() {
    const [messages, setMessages] = useState([]);
    const [userInput, setUserInput] = useState('');

    const handleSend = async () => {
        const response = await axios.post('http://localhost:8000/chat', {
            user_input: userInput
        });
        setMessages([...messages, { type: 'user', content: userInput }, { type: 'bot', content: response.data.response }]);
        setUserInput('');
    };

    return (
        <div>
            <div>
                {messages.map((msg, index) => (
                    <div key={index} className={msg.type}>
                        {msg.content}
                    </div>
                ))}
            </div>
            <div>
                <input value={userInput} onChange={e => setUserInput(e.target.value)} />
                <button onClick={handleSend}>Send</button>
            </div>
        </div>
    );
}

export default ChatComponent;