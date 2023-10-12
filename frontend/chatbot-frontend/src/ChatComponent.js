import React, { useState } from 'react';
import axios from 'axios';
import './ChatComponent.css';  // Assuming you place the CSS in a file named ChatComponent.css in the same directory

function ChatComponent() {
    const [messages, setMessages] = useState([]);
    const [userInput, setUserInput] = useState('');

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault(); // To prevent any default action (like form submission if wrapped inside a form)
            handleSend();
        }
    };

    const handleSend = async () => {
        // Create a new array with the user's message at the beginning
        const newUserMessage = [{ type: 'user', content: "Me: " + userInput }];
        const updatedMessages = [...newUserMessage, ...messages];
    
        setUserInput('');
        setMessages(updatedMessages);
    
        try {
            const response = await axios.post('http://localhost:8000/chat', {
                user_input: userInput
            });
    
            // Add the bot's response to the updated messages array
            setMessages([{ type: 'bot', content: response.data.response }, ...updatedMessages]);
        } catch (error) {
            console.error('Failed to get response from bot:', error);
        }
    };
    
    

    return (
        <div className="chat-container">
            <div className="message-container">
                {messages.map((msg, index) => (
                    <div key={index} className={`message ${msg.type}`}>
                        {msg.content}
                    </div>
                ))}
            </div>
            <div className="input-container">
                <input 
                    style={{width: '80%'}} 
                    value={userInput} 
                    onChange={e => setUserInput(e.target.value)} 
                    onKeyDown={handleKeyDown} 
                />
                <button onClick={handleSend}>Send</button>
            </div>
        </div>
    );
}

export default ChatComponent;
