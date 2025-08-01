import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_URL = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

function YouTubeLive() {
  const [videoSession, setVideoSession] = useState(null);
  const [factChecks, setFactChecks] = useState([]);
  const [transcriptSegments, setTranscriptSegments] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  // Initialize WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      try {
        const ws = new WebSocket(`${WS_URL}/ws/youtube-live`);
        
        ws.onopen = () => {
          console.log('YouTube Live WebSocket connected');
          setIsConnected(true);
          setError('');
          
          // Request current session data
          ws.send(JSON.stringify({
            type: 'get_current_session'
          }));
        };

        ws.onmessage = (event) => {
          const message = JSON.parse(event.data);
          handleWebSocketMessage(message);
        };

        ws.onclose = () => {
          console.log('YouTube Live WebSocket disconnected');
          setIsConnected(false);
          
          // Attempt to reconnect after 3 seconds
          reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = (error) => {
          console.error('YouTube Live WebSocket error:', error);
          setError('Connection error. Retrying...');
        };

        wsRef.current = ws;
      } catch (error) {
        console.error('WebSocket connection error:', error);
        setError('Failed to connect to live updates');
      }
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, []);

  // Fetch initial data
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const response = await fetch(`${API_URL}/youtube/current-session`);
        if (response.ok) {
          const data = await response.json();
          if (data.session) {
            setVideoSession(data.session);
            setFactChecks(data.fact_checks || []);
            setTranscriptSegments(data.transcript_segments || []);
          }
        }
      } catch (error) {
        console.error('Error fetching initial data:', error);
        setError('Failed to load video session');
      } finally {
        setLoading(false);
      }
    };

    fetchInitialData();
  }, []);

  const handleWebSocketMessage = (message) => {
    switch (message.type) {
      case 'current_session':
        if (message.data) {
          setVideoSession(message.data);
          setFactChecks(message.data.fact_checks || []);
          setTranscriptSegments(message.data.transcript_segments || []);
        }
        setLoading(false);
        break;
        
      case 'new_fact_check':
        setFactChecks(prev => [...prev, message.data]);
        break;
        
      case 'new_transcript':
        setTranscriptSegments(prev => [...prev, message.data]);
        break;
        
      case 'video_changed':
        setVideoSession(message.data);
        setFactChecks([]);
        setTranscriptSegments([]);
        break;
        
      case 'error':
        setError(message.message);
        break;
        
      default:
        console.log('Unknown message type:', message.type);
    }
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

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-300">Loading YouTube Live Fact-Checker...</p>
        </div>
      </div>
    );
  }

  if (!videoSession) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white">
        {/* Header */}
        <div className="bg-black/30 backdrop-blur-sm border-b border-purple-500/20 p-4">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gradient-to-r from-red-500 to-purple-500 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">YT</span>
              </div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-red-400 to-purple-400 bg-clip-text text-transparent">
                YouTube Live Fact-Checker
              </h1>
            </div>
            
            <div className="flex items-center space-x-3">
              <div className={`text-xs px-2 py-1 rounded-full border ${
                isConnected 
                  ? 'bg-green-500/20 text-green-300 border-green-500/30' 
                  : 'bg-red-500/20 text-red-300 border-red-500/30'
              }`}>
                {isConnected ? 'Connected' : 'Disconnected'}
              </div>
            </div>
          </div>
        </div>

        {/* No Video Message */}
        <div className="flex items-center justify-center min-h-[80vh]">
          <div className="text-center">
            <div className="text-6xl mb-6">📺</div>
            <h2 className="text-2xl font-bold text-white mb-4">No Video Currently Set</h2>
            <p className="text-gray-400 mb-6 max-w-md">
              An administrator needs to set a YouTube video for live fact-checking. 
              Once set, real-time fact-checks will appear here for all viewers.
            </p>
            {error && (
              <div className="bg-red-500/20 border border-red-500/30 rounded-lg p-4 text-red-300 max-w-md mx-auto">
                {error}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white">
      {/* Header */}
      <div className="bg-black/30 backdrop-blur-sm border-b border-purple-500/20 p-4">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gradient-to-r from-red-500 to-purple-500 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">YT</span>
              </div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-red-400 to-purple-400 bg-clip-text text-transparent">
                YouTube Live Fact-Checker
              </h1>
            </div>
            
            <div className="flex items-center space-x-3">
              <div className={`text-xs px-2 py-1 rounded-full border ${
                isConnected 
                  ? 'bg-green-500/20 text-green-300 border-green-500/30' 
                  : 'bg-red-500/20 text-red-300 border-red-500/30'
              }`}>
                {isConnected ? 'Live' : 'Disconnected'}
              </div>
              {videoSession.is_live && (
                <div className="flex items-center space-x-2 text-red-400">
                  <div className="w-2 h-2 bg-red-400 rounded-full animate-pulse"></div>
                  <span className="text-sm">LIVE</span>
                </div>
              )}
            </div>
          </div>
          
          {/* Video Title */}
          <h2 className="text-xl font-semibold text-white mb-2">{videoSession.title}</h2>
          <div className="flex items-center space-x-4 text-sm text-gray-400">
            <span>Started: {formatTime(videoSession.created_at)}</span>
            <span>•</span>
            <span>{factChecks.length} fact-checks</span>
            {videoSession.duration > 0 && (
              <>
                <span>•</span>
                <span>{Math.floor(videoSession.duration / 60)}m duration</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-500/20 border-b border-red-500/30 p-4">
          <div className="max-w-6xl mx-auto text-red-300 text-sm">
            ⚠ {error}
          </div>
        </div>
      )}

      <div className="max-w-6xl mx-auto p-4 space-y-6">
        {/* Video Embed */}
        <div className="aspect-video bg-black/50 rounded-xl border border-purple-500/20 overflow-hidden">
          <iframe
            width="100%"
            height="100%"
            src={`https://www.youtube.com/embed/${videoSession.video_id}?autoplay=1&mute=1`}
            title={videoSession.title}
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="w-full h-full"
          ></iframe>
        </div>

        {/* Split Layout for Transcript and Fact-Checks */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[60vh]">
          {/* Left Panel - Live Transcript */}
          <div className="bg-black/30 backdrop-blur-sm rounded-xl border border-purple-500/20 p-6 overflow-hidden flex flex-col">
            <h3 className="text-lg font-semibold text-purple-300 mb-4 flex items-center">
              📝 Live Transcript
              {isConnected && (
                <div className="ml-2 w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              )}
            </h3>
            
            <div className="flex-1 overflow-y-auto space-y-3">
              {transcriptSegments.length > 0 ? (
                transcriptSegments.map((segment, index) => (
                  <div key={index} className="p-3 bg-gray-800/30 rounded-lg border border-gray-700/30">
                    <div className="text-sm text-gray-400 mb-1">
                      {formatTime(segment.timestamp)}
                    </div>
                    <div className="text-gray-200">
                      {segment.transcript}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center text-gray-500 mt-20">
                  <div className="text-4xl mb-4">🎤</div>
                  <p>Waiting for audio transcription...</p>
                </div>
              )}
            </div>
          </div>

          {/* Right Panel - Fact-Check Results */}
          <div className="bg-black/30 backdrop-blur-sm rounded-xl border border-purple-500/20 p-6 overflow-hidden flex flex-col">
            <h3 className="text-lg font-semibold text-purple-300 mb-4">🔍 Live Fact-Checks</h3>
            
            <div className="flex-1 overflow-y-auto space-y-4">
              {factChecks.length > 0 ? (
                factChecks.map((check, index) => (
                  <div
                    key={index}
                    className={`p-4 rounded-lg border ${getVerdictColor(check.verdict)} transition-all duration-300`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <span className="text-lg">{getVerdictIcon(check.verdict)}</span>
                        <span className="font-semibold">{check.verdict}</span>
                      </div>
                      <div className="text-xs opacity-75 text-right">
                        <div>{Math.round(check.confidence_score * 100)}% confidence</div>
                        <div>{formatTime(check.created_at)}</div>
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
                ))
              ) : (
                <div className="text-center text-gray-500 mt-20">
                  <div className="text-4xl mb-4">⏳</div>
                  <p>Waiting for fact-check results...</p>
                  <p className="text-sm mt-2">Statements will be automatically verified</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Stats Footer */}
        <div className="bg-black/20 backdrop-blur-sm rounded-xl border border-purple-500/20 p-4">
          <div className="flex justify-center space-x-8 text-sm text-gray-400">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-400">{factChecks.filter(fc => fc.verdict === 'True').length}</div>
              <div>True</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-400">{factChecks.filter(fc => fc.verdict === 'False').length}</div>
              <div>False</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-400">{factChecks.filter(fc => fc.verdict === 'Partially True').length}</div>
              <div>Partial</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-400">{factChecks.filter(fc => fc.verdict === 'Unverified').length}</div>
              <div>Unverified</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default YouTubeLive;