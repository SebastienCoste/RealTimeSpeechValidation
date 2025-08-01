import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import YouTubeLive from './YouTubeLive';
import AdminPanel from './AdminPanel';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_URL = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

// Generate unique session ID
const generateSessionId = () => {
  return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
};

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

function TruthSeeker() {
  const [isListening, setIsListening] = useState(false);
  const [transcription, setTranscription] = useState('');
  const [currentSentence, setCurrentSentence] = useState('');
  const [factChecks, setFactChecks] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [sessionId] = useState(() => generateSessionId());
  const [error, setError] = useState('');
  const [apiConfigured, setApiConfigured] = useState(false);

  const recognitionRef = useRef(null);
  const wsRef = useRef(null);
  const processTimeoutRef = useRef(null);

  // Initialize speech recognition
  useEffect(() => {
    if (!SpeechRecognition) {
      setError('Speech recognition not supported in this browser. Please use Chrome, Safari, or Edge.');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      console.log('Speech recognition started');
      setError('');
    };

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      if (finalTranscript) {
        setTranscription(prev => prev + finalTranscript + ' ');
        setCurrentSentence('');
        
        // Process final transcript for fact-checking
        if (finalTranscript.trim().length > 10) {
          processSentenceForFactCheck(finalTranscript.trim());
        }
      } else {
        setCurrentSentence(interimTranscript);
      }
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      if (event.error === 'not-allowed') {
        setError('Microphone access denied. Please allow microphone access and refresh the page.');
      } else if (event.error === 'no-speech') {
        setError('No speech detected. Please try speaking again.');
      } else {
        setError(`Speech recognition error: ${event.error}`);
      }
      setIsListening(false);
    };

    recognition.onend = () => {
      console.log('Speech recognition ended');
      if (isListening) {
        // Restart recognition if it should still be listening
        setTimeout(() => {
          try {
            recognition.start();
          } catch (e) {
            console.error('Error restarting recognition:', e);
            setIsListening(false);
          }
        }, 100);
      }
    };

    recognitionRef.current = recognition;

    return () => {
      if (recognition) {
        recognition.stop();
      }
    };
  }, [isListening]);

  // Initialize WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      try {
        const ws = new WebSocket(`${WS_URL}/ws/${sessionId}`);
        
        ws.onopen = () => {
          console.log('WebSocket connected');
        };

        ws.onmessage = (event) => {
          const message = JSON.parse(event.data);
          if (message.type === 'fact_check_result') {
            setFactChecks(prev => [message.data, ...prev]);
            setIsProcessing(false);
          }
        };

        ws.onclose = () => {
          console.log('WebSocket disconnected');
          // Attempt to reconnect after 3 seconds
          setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
        };

        wsRef.current = ws;
      } catch (error) {
        console.error('WebSocket connection error:', error);
      }
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [sessionId]);

  // Check API configuration
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_URL}/health`);
        const data = await response.json();
        setApiConfigured(data.perplexity_api_configured);
      } catch (error) {
        console.error('Health check error:', error);
      }
    };

    checkHealth();
  }, []);

  const processSentenceForFactCheck = useCallback((sentence) => {
    if (processTimeoutRef.current) {
      clearTimeout(processTimeoutRef.current);
    }

    setIsProcessing(true);

    // Debounce processing to avoid too many requests
    processTimeoutRef.current = setTimeout(async () => {
      try {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            type: 'transcription_update',
            text: sentence,
            is_final: true
          }));
        } else {
          // Fallback to HTTP API
          const response = await fetch(`${API_URL}/fact-check`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              statement: sentence,
              session_id: sessionId
            }),
          });

          if (response.ok) {
            const result = await response.json();
            setFactChecks(prev => [result, ...prev]);
          }
        }
      } catch (error) {
        console.error('Error processing sentence:', error);
      } finally {
        setIsProcessing(false);
      }
    }, 1000);
  }, [sessionId]);

  const toggleListening = () => {
    if (!recognitionRef.current) return;

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
        setError('');
      } catch (error) {
        console.error('Error starting recognition:', error);
        setError('Error starting speech recognition. Please try again.');
      }
    }
  };

  const clearAll = () => {
    setTranscription('');
    setCurrentSentence('');
    setFactChecks([]);
    setError('');
  };

  const getVerdictColor = (verdict) => {
    switch (verdict.toLowerCase()) {
      case 'true':
        return 'text-green-400 bg-green-900/20 border-green-500/30';
      case 'false':
        return 'text-red-400 bg-red-900/20 border-red-500/30';
      case 'partially true':
        return 'text-yellow-400 bg-yellow-900/20 border-yellow-500/30';
      default:
        return 'text-gray-400 bg-gray-900/20 border-gray-500/30';
    }
  };

  const getVerdictIcon = (verdict) => {
    switch (verdict.toLowerCase()) {
      case 'true':
        return '✓';
      case 'false':
        return '✗';
      case 'partially true':
        return '⚠';
      default:
        return '?';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white">
      {/* Header */}
      <div className="bg-black/30 backdrop-blur-sm border-b border-purple-500/20 p-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-blue-500 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">TS</span>
            </div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
              TruthSeeker
            </h1>
          </div>
          
          <div className="flex items-center space-x-3">
            {!apiConfigured && (
              <div className="text-xs bg-orange-500/20 text-orange-300 px-2 py-1 rounded-full border border-orange-500/30">
                Demo Mode - Add Perplexity API Key
              </div>
            )}
            <button
              onClick={clearAll}
              className="px-4 py-2 bg-slate-700/50 hover:bg-slate-600/50 rounded-lg text-sm transition-colors border border-slate-600/30"
            >
              Clear All
            </button>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-500/20 border-b border-red-500/30 p-4">
          <div className="max-w-4xl mx-auto text-red-300 text-sm">
            ⚠ {error}
          </div>
        </div>
      )}

      <div className="max-w-4xl mx-auto p-4 space-y-4">
        {/* Control Button */}
        <div className="text-center">
          <button
            onClick={toggleListening}
            disabled={!SpeechRecognition}
            className={`w-20 h-20 rounded-full border-4 transition-all duration-300 flex items-center justify-center text-2xl font-bold ${
              isListening
                ? 'bg-red-500 border-red-400 hover:bg-red-600 shadow-lg shadow-red-500/25 animate-pulse'
                : 'bg-gradient-to-r from-purple-600 to-blue-600 border-purple-400 hover:from-purple-700 hover:to-blue-700 shadow-lg shadow-purple-500/25'
            } ${!SpeechRecognition ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105'}`}
          >
            {isListening ? '🛑' : '🎤'}
          </button>
          <p className="mt-2 text-sm text-gray-300">
            {isListening ? 'Listening... Click to stop' : 'Click to start listening'}
          </p>
        </div>

        {/* Split Screen Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-[70vh]">
          {/* Left Panel - Transcription */}
          <div className="bg-black/30 backdrop-blur-sm rounded-xl border border-purple-500/20 p-6 overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-purple-300">Live Transcription</h2>
              {isListening && (
                <div className="flex items-center space-x-2 text-green-400">
                  <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                  <span className="text-sm">Recording</span>
                </div>
              )}
            </div>
            
            <div className="flex-1 overflow-y-auto space-y-3">
              {/* Final transcription */}
              {transcription && (
                <div className="text-gray-200 leading-relaxed">
                  {transcription}
                </div>
              )}
              
              {/* Current sentence being spoken */}
              {currentSentence && (
                <div className="text-gray-400 italic border-l-2 border-purple-500 pl-3">
                  {currentSentence}
                </div>
              )}
              
              {/* Processing indicator */}
              {isProcessing && (
                <div className="flex items-center space-x-2 text-blue-400">
                  <div className="animate-spin w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full"></div>
                  <span className="text-sm">Fact-checking...</span>
                </div>
              )}
              
              {/* Placeholder when not transcribing */}
              {!transcription && !currentSentence && (
                <div className="text-center text-gray-500 mt-20">
                  <div className="text-4xl mb-4">🎙️</div>
                  <p>Start speaking to see transcription here</p>
                </div>
              )}
            </div>
          </div>

          {/* Right Panel - Fact Checks */}
          <div className="bg-black/30 backdrop-blur-sm rounded-xl border border-purple-500/20 p-6 overflow-hidden flex flex-col">
            <h2 className="text-lg font-semibold text-purple-300 mb-4">Fact-Check Results</h2>
            
            <div className="flex-1 overflow-y-auto space-y-4">
              {factChecks.map((check, index) => (
                <div
                  key={index}
                  className={`p-4 rounded-lg border ${getVerdictColor(check.verdict)} transition-all duration-300 hover:scale-[1.02]`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-lg">{getVerdictIcon(check.verdict)}</span>
                      <span className="font-semibold">{check.verdict}</span>
                    </div>
                    <div className="text-xs opacity-75">
                      {Math.round(check.confidence_score * 100)}% confidence
                    </div>
                  </div>
                  
                  <div className="text-sm text-gray-300 mb-2 font-medium">
                    "{check.statement}"
                  </div>
                  
                  <div className="text-xs text-gray-400 leading-relaxed">
                    {check.explanation}
                  </div>
                  
                  {check.sources && check.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-600/30">
                      <div className="text-xs text-gray-500 mb-1">Sources:</div>
                      {check.sources.slice(0, 2).map((source, i) => (
                        <div key={i} className="text-xs text-blue-400 hover:text-blue-300">
                          <a href={source.url} target="_blank" rel="noopener noreferrer" className="truncate block">
                            {source.title}
                          </a>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              
              {factChecks.length === 0 && (
                <div className="text-center text-gray-500 mt-20">
                  <div className="text-4xl mb-4">🔍</div>
                  <p>Fact-check results will appear here</p>
                  <p className="text-sm mt-2">Speak complete sentences to trigger fact-checking</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-xs text-gray-500 pt-4 border-t border-gray-700/30">
          <p>
            TruthSeeker v1.0 - Real-time fact-checking powered by AI
            {!apiConfigured && (
              <span className="block mt-1 text-orange-400">
                Currently running in demo mode. Add your Perplexity API key for full functionality.
              </span>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<TruthSeeker />} />
          <Route path="/youtube-live" element={<YouTubeLive />} />
          <Route path="/admin" element={<AdminPanel />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;