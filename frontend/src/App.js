import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';
import ReactMarkdown from 'react-markdown';
import { PaperAirplaneIcon, PaperClipIcon } from '@heroicons/react/24/outline';

const API_URL = 'https://api.rexia.uk/v1/chat/completions';
const API_KEY = 'QaMMC2AuXaHgoBZxej7TcB4o8_QozPnNbb7cHO-B3g8';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const [files, setFiles] = useState([]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const { getRootProps, getInputProps } = useDropzone({
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.gif', '.webp'],
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx']
    },
    onDrop: acceptedFiles => {
      setFiles(prev => [...prev, ...acceptedFiles]);
    }
  });

  const processFile = async (file) => {
    if (file.type.startsWith('image/')) {
      return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          resolve(reader.result);
        };
        reader.readAsDataURL(file);
      });
    }
    // TODO: Add PDF and Word document processing
    return null;
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() && files.length === 0) return;

    const newMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, newMessage]);
    setInput('');
    setIsLoading(true);

    try {
      let content = input;

      // Process files if any
      if (files.length > 0) {
        const processedFiles = await Promise.all(files.map(processFile));
        const validFiles = processedFiles.filter(Boolean);
        
        if (validFiles.length > 0) {
          content = validFiles.map(file => 
            `${content}\n<image>${file}</image>`
          ).join('\n');
        }
      }

      const response = await axios.post(API_URL, {
        model: 'llama3.2-vision:latest',
        messages: [...messages, { role: 'user', content }]
      }, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${API_KEY}`
        }
      });

      const assistantMessage = response.data.choices[0].message;
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, there was an error processing your request.'
      }]);
    }

    setIsLoading(false);
    setFiles([]);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
          <h1 className="text-2xl font-bold text-gray-900">Vision Chat</h1>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col h-[calc(100vh-8rem)]">
          <div className="flex-1 overflow-y-auto py-4 space-y-4">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                <div
                  className={`max-w-lg rounded-lg px-4 py-2 ${
                    message.role === 'user'
                      ? 'bg-blue-500 text-white'
                      : 'bg-white text-gray-900 shadow'
                  }`}
                >
                  <ReactMarkdown className="prose">
                    {message.content}
                  </ReactMarkdown>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="max-w-lg rounded-lg px-4 py-2 bg-white text-gray-900 shadow">
                  <div className="flex space-x-2">
                    <div className="animate-bounce">●</div>
                    <div className="animate-bounce delay-100">●</div>
                    <div className="animate-bounce delay-200">●</div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="py-4">
            <form onSubmit={sendMessage} className="flex flex-col space-y-2">
              <div {...getRootProps()} className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center">
                <input {...getInputProps()} />
                <p className="text-gray-500">
                  Drag & drop files here, or click to select
                </p>
                {files.length > 0 && (
                  <div className="mt-2">
                    {files.map((file, index) => (
                      <div key={index} className="text-sm text-gray-600">
                        {file.name}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex space-x-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Type your message..."
                  className="flex-1 rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
                <button
                  type="submit"
                  disabled={isLoading}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg shadow-sm text-white bg-blue-500 hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                >
                  <PaperAirplaneIcon className="h-5 w-5" />
                </button>
              </div>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
