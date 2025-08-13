# Spotify Playlist Generator

A web application that connects to your Spotify account, analyzes your followed artists and their "Fans also like" sections, then generates playlists with songs released in the previous week.

## Features

- 🎵 **Spotify Integration**: Secure OAuth authentication
- 👥 **Artist Analysis**: Scans followed artists and related artists
- 📅 **Recent Releases**: Finds songs from the last 7 days
- 🎧 **Auto Playlists**: Creates private playlists in your account
- 🌐 **Web Interface**: Beautiful responsive design

## Quick Start

### 1. Setup Spotify Developer App
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications)
2. Create new app
3. Add redirect URI: `http://localhost:5000/callback`
4. Note your Client ID and Client Secret

### 2. Run the App
```bash
# Clone this repo
git clone YOUR_REPO_URL
cd your-repo-name

# Install dependencies
pip3 install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your Spotify credentials

# Run the app
python3 app.py
