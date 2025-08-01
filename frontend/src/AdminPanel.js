import React, { useState, useEffect } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_URL = `${BACKEND_URL}/api`;

function AdminPanel() {
  const [videoUrl, setVideoUrl] = useState('');
  const [currentSession, setCurrentSession] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [adminKey, setAdminKey] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Check for existing session
  useEffect(() => {
    fetchCurrentSession();
  }, []);

  const fetchCurrentSession = async () => {
    try {
      const response = await fetch(`${API_URL}/youtube/current-session`);
      if (response.ok) {
        const data = await response.json();
        setCurrentSession(data.session);
      }
    } catch (error) {
      console.error('Error fetching current session:', error);
    }
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    // Simple admin key check (in production, use proper auth)
    if (adminKey === 'admin123' || adminKey === process.env.REACT_APP_ADMIN_KEY) {
      setIsAuthenticated(true);
      setMessage('');
    } else {
      setMessage('Invalid admin key');
    }
  };

  const handleSetVideo = async (e) => {
    e.preventDefault();
    
    if (!videoUrl.trim()) {
      setMessage('Please enter a valid YouTube URL');
      return;
    }

    setIsLoading(true);
    setMessage('');

    try {
      const response = await fetch(`${API_URL}/youtube/set-video`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          video_url: videoUrl,
          admin_user: 'admin' // In production, use actual user
        }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setMessage(`✅ Video set successfully: ${data.title}`);
        setCurrentSession({
          video_id: data.video_id,
          title: data.title,
          duration: data.duration,
          is_live: data.is_live,
          created_at: new Date().toISOString()
        });
        setVideoUrl('');
      } else {
        setMessage(`❌ Error: ${data.error || 'Failed to set video'}`);
      }
    } catch (error) {
      setMessage(`❌ Network error: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartProcessing = async () => {
    if (!currentSession) {
      setMessage('No video session available');
      return;
    }

    setIsProcessing(true);
    setMessage('');

    try {
      const response = await fetch(`${API_URL}/youtube/start-processing`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          video_id: currentSession.video_id
        }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setMessage('✅ Processing started successfully');
      } else {
        setMessage(`❌ Error starting processing: ${data.error || 'Unknown error'}`);
      }
    } catch (error) {
      setMessage(`❌ Network error: ${error.message}`);
    }
  };

  const handleStopProcessing = async () => {
    try {
      const response = await fetch(`${API_URL}/youtube/stop-processing`, {
        method: 'POST',
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setMessage('⏹️ Processing stopped');
        setIsProcessing(false);
      } else {
        setMessage(`❌ Error stopping processing: ${data.error || 'Unknown error'}`);
      }
    } catch (error) {
      setMessage(`❌ Network error: ${error.message}`);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white flex items-center justify-center">
        <div className="bg-black/30 backdrop-blur-sm rounded-xl border border-purple-500/20 p-8 w-full max-w-md">
          <div className="text-center mb-6">
            <div className="w-12 h-12 bg-gradient-to-r from-purple-500 to-blue-500 rounded-lg flex items-center justify-center mx-auto mb-4">
              <span className="text-white font-bold text-lg">🔐</span>
            </div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
              Admin Panel
            </h1>
            <p className="text-gray-400 text-sm mt-2">Enter admin key to continue</p>
          </div>

          <form onSubmit={handleAuth} className="space-y-4">
            <div>
              <input
                type="password"
                value={adminKey}
                onChange={(e) => setAdminKey(e.target.value)}
                placeholder="Admin key"
                className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600/30 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-purple-500/50"
                required
              />
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 rounded-lg font-semibold transition-colors"
            >
              Login
            </button>

            {message && (
              <div className="text-red-400 text-sm text-center">
                {message}
              </div>
            )}
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white">
      {/* Header */}
      <div className="bg-black/30 backdrop-blur-sm border-b border-purple-500/20 p-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-blue-500 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">⚙️</span>
            </div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
              YouTube Live Admin
            </h1>
          </div>
          
          <a
            href="/youtube-live"
            className="px-4 py-2 bg-gradient-to-r from-red-500 to-purple-500 hover:from-red-600 hover:to-purple-600 rounded-lg text-sm transition-colors"
          >
            View Live Page
          </a>
        </div>
      </div>

      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Current Session */}
        {currentSession && (
          <div className="bg-black/30 backdrop-blur-sm rounded-xl border border-purple-500/20 p-6">
            <h2 className="text-xl font-semibold text-purple-300 mb-4">Current Video Session</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <div className="text-sm text-gray-400">Title</div>
                <div className="text-white font-medium">{currentSession.title}</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Video ID</div>
                <div className="text-white font-mono text-sm">{currentSession.video_id}</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Status</div>
                <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${
                  currentSession.is_live 
                    ? 'bg-red-500/20 text-red-300 border border-red-500/30' 
                    : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                }`}>
                  {currentSession.is_live ? '🔴 Live' : '📹 Static'}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Created</div>
                <div className="text-white text-sm">
                  {new Date(currentSession.created_at).toLocaleString()}
                </div>
              </div>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={handleStartProcessing}
                disabled={isProcessing}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  isProcessing
                    ? 'bg-gray-600/50 text-gray-400 cursor-not-allowed'
                    : 'bg-green-600 hover:bg-green-700 text-white'
                }`}
              >
                {isProcessing ? '⏳ Processing...' : '▶️ Start Processing'}
              </button>

              <button
                onClick={handleStopProcessing}
                disabled={!isProcessing}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  !isProcessing
                    ? 'bg-gray-600/50 text-gray-400 cursor-not-allowed'
                    : 'bg-red-600 hover:bg-red-700 text-white'
                }`}
              >
                ⏹️ Stop Processing
              </button>
            </div>
          </div>
        )}

        {/* Set New Video */}
        <div className="bg-black/30 backdrop-blur-sm rounded-xl border border-purple-500/20 p-6">
          <h2 className="text-xl font-semibold text-purple-300 mb-4">Set YouTube Video</h2>
          
          <form onSubmit={handleSetVideo} className="space-y-4">
            <div>
              <label htmlFor="videoUrl" className="block text-sm font-medium text-gray-300 mb-2">
                YouTube Video URL
              </label>
              <input
                type="url"
                id="videoUrl"
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600/30 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-purple-500/50"
                required
              />
              <p className="text-xs text-gray-500 mt-1">
                Supports YouTube videos and live streams
              </p>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className={`px-6 py-3 rounded-lg font-semibold transition-colors ${
                isLoading
                  ? 'bg-gray-600/50 text-gray-400 cursor-not-allowed'
                  : 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white'
              }`}
            >
              {isLoading ? (
                <div className="flex items-center">
                  <div className="animate-spin w-4 h-4 border-2 border-gray-300 border-t-transparent rounded-full mr-2"></div>
                  Setting Video...
                </div>
              ) : (
                'Set Video'
              )}
            </button>
          </form>
        </div>

        {/* Message Display */}
        {message && (
          <div className={`p-4 rounded-lg border ${
            message.includes('✅') 
              ? 'bg-green-500/20 border-green-500/30 text-green-300'
              : message.includes('❌')
              ? 'bg-red-500/20 border-red-500/30 text-red-300'
              : 'bg-blue-500/20 border-blue-500/30 text-blue-300'
          }`}>
            {message}
          </div>
        )}

        {/* Instructions */}
        <div className="bg-black/20 backdrop-blur-sm rounded-xl border border-purple-500/20 p-6">
          <h3 className="text-lg font-semibold text-purple-300 mb-3">Instructions</h3>
          <div className="space-y-2 text-sm text-gray-400">
            <p>1. Enter a YouTube video URL (works with both regular videos and live streams)</p>
            <p>2. Click "Set Video" to configure the video for fact-checking</p>
            <p>3. Click "Start Processing" to begin audio transcription and fact-checking</p>
            <p>4. Users can view live fact-checks on the public page</p>
            <p>5. Use "Stop Processing" to halt fact-checking when done</p>
          </div>
          
          <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <p className="text-yellow-300 text-sm">
              <strong>Note:</strong> Make sure you have configured your OpenAI API key for Whisper transcription 
              and Perplexity API key for fact-checking in the backend environment.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminPanel;