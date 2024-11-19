import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useDropzone } from 'react-dropzone';
import ReactMarkdown from 'react-markdown';
import { PaperAirplaneIcon } from '@heroicons/react/24/outline';

const API_URL = 'https://api.rexia.uk/v1/chat/completions';
const API_KEY = 'QaMMC2AuXaHgoBZxej7TcB4o8_QozPnNbb7cHO-B3g8';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState('');
  const streamBuffer = useRef('');
  const updateTimeoutRef = useRef(null);
  const messagesEndRef = useRef(null);
  const [files, setFiles] = useState([]);

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

  const updateStreamingMessage = (newContent) => {
    streamBuffer.current = newContent;
    if (updateTimeoutRef.current) return;

    updateTimeoutRef.current = setTimeout(() => {
      setStreamingMessage(streamBuffer.current);
      updateTimeoutRef.current = null;
    }, 50); // Update every 50ms maximum
  };

  const MessageContent = useMemo(() => ({ content, className }) => (
    <ReactMarkdown className={className}>
      {content}
    </ReactMarkdown>
  ), []);

  const scrollToBottom = () => {
    if (!messagesEndRef.current) return;
    const isNearBottom = window.innerHeight + window.scrollY >= document.documentElement.offsetHeight - 100;
    if (isNearBottom) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages.length, streamingMessage]); // Only scroll on new messages or significant streaming updates

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() && files.length === 0) return;

    try {
      setIsLoading(true);
      setMessages(prev => [...prev, { role: 'user', content: input, files }]);
      setInput('');
      setFiles([]);

      let content = input;

      // Process files if any
      if (files.length > 0) {
        const processedFiles = await Promise.all(files.map(processFile));
        const validFiles = processedFiles.filter(Boolean);
        
        if (validFiles.length > 0) {
          content = [
            { type: 'text', text: input || '' },
            ...validFiles.map(file => ({
              type: 'image_url',
              image_url: file
            }))
          ];
        }
      }

      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          'Authorization': `Bearer ${API_KEY}`
        },
        body: JSON.stringify({
          model: 'llama3.2-vision:latest',
          messages: [{ role: 'user', content }],
          stream: true
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulatedMessage = '';

      // Add initial empty assistant message
      setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;

            try {
              const parsed = JSON.parse(data);
              if (parsed.choices?.[0]?.delta?.content) {
                accumulatedMessage += parsed.choices[0].delta.content;
                // Update the last message in place
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages[newMessages.length - 1].content = accumulatedMessage;
                  return newMessages;
                });
              }
            } catch (e) {
              console.error('Error parsing SSE message:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Error details:', error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Sorry, I encountered an error while processing your request.' 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100">
      <header className="bg-white border-b border-gray-200 fixed top-0 w-full z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <svg className="h-8 w-8 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            <h1 className="text-2xl font-bold text-gray-900">Vision Chat</h1>
          </div>
          <div className="text-sm text-gray-500">Powered by Edge AI</div>
        </div>
      </header>

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-32">
        <div className="flex flex-col h-[calc(100vh-8rem)]">
          <div className="flex-1 overflow-y-auto py-4 space-y-6">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                <div
                  className={`relative max-w-lg rounded-2xl px-4 py-3 shadow-sm overflow-hidden ${
                    message.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-white text-gray-900'
                  } ${
                    message.role === 'assistant' ? 'ml-4' : 'mr-4'
                  }`}
                >
                  {message.role === 'assistant' && (
                    <div className="absolute -left-2 top-4 w-4 h-4 rotate-45 bg-white"></div>
                  )}
                  {message.role === 'user' && (
                    <div className="absolute -right-2 top-4 w-4 h-4 rotate-45 bg-blue-600"></div>
                  )}
                  <div className="overflow-hidden break-words">
                    <MessageContent 
                      content={message.content}
                      className={`prose max-w-none prose-sm ${
                        message.role === 'user' 
                          ? 'prose-invert' 
                          : 'prose-gray'
                      } prose-p:my-0 prose-headings:my-1 prose-pre:bg-gray-800 prose-pre:text-gray-100 prose-pre:overflow-x-auto prose-pre:whitespace-pre-wrap`}
                    />
                  </div>
                </div>
              </div>
            ))}
            {streamingMessage && (
              <div className="flex justify-start">
                <div className="relative max-w-lg rounded-2xl px-4 py-3 bg-white text-gray-900 shadow-sm ml-4 overflow-hidden">
                  <div className="absolute -left-2 top-4 w-4 h-4 rotate-45 bg-white"></div>
                  <div className="overflow-hidden break-words">
                    <MessageContent 
                      content={streamingMessage}
                      className="prose max-w-none prose-sm prose-gray prose-p:my-0 prose-headings:my-1 prose-pre:bg-gray-800 prose-pre:text-gray-100 prose-pre:overflow-x-auto prose-pre:whitespace-pre-wrap"
                    />
                  </div>
                </div>
              </div>
            )}
            {isLoading && !streamingMessage && (
              <div className="flex justify-start">
                <div className="relative max-w-lg rounded-2xl px-6 py-4 bg-white text-gray-900 shadow-sm ml-4">
                  <div className="absolute -left-2 top-4 w-4 h-4 rotate-45 bg-white"></div>
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"></div>
                    <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce delay-100"></div>
                    <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce delay-200"></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4">
            <div className="max-w-5xl mx-auto">
              <form onSubmit={sendMessage} className="flex flex-col space-y-4">
                <div 
                  {...getRootProps()} 
                  className={`border-2 border-dashed rounded-xl p-4 transition-colors duration-200 ${
                    files.length > 0 
                      ? 'border-blue-500 bg-blue-50' 
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <input {...getInputProps()} />
                  <div className="flex flex-col items-center justify-center text-sm">
                    <svg className="h-8 w-8 text-gray-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {files.length > 0 ? (
                      <p className="text-blue-600 font-medium">
                        {files.length} file{files.length !== 1 ? 's' : ''} selected
                      </p>
                    ) : (
                      <p className="text-gray-500">
                        Drop files here or click to select
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex space-x-4">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Type your message..."
                    className="flex-1 rounded-xl border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  />
                  <button
                    type="submit"
                    disabled={isLoading || (!input.trim() && files.length === 0)}
                    className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-xl shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
                  >
                    <PaperAirplaneIcon className="h-5 w-5" />
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
