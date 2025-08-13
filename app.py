from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import requests
import urllib.parse
import base64
import secrets
import os
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(16))

# Spotify API configuration
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = 'http://localhost:5000/callback'
SPOTIFY_SCOPE = 'user-follow-read playlist-modify-public playlist-modify-private user-read-private'

class SpotifyAPI:
    def __init__(self):
        self.base_url = 'https://api.spotify.com/v1'
    
    def get_auth_url(self):
        """Generate Spotify authorization URL"""
        state = secrets.token_urlsafe(16)
        session['oauth_state'] = state
        
        params = {
            'client_id': SPOTIFY_CLIENT_ID,
            'response_type': 'code',
            'redirect_uri': SPOTIFY_REDIRECT_URI,
            'scope': SPOTIFY_SCOPE,
            'state': state
        }
        
        auth_url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"
        return auth_url
    
    def get_access_token(self, code):
        """Exchange authorization code for access token"""
        auth_header = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
        
        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': SPOTIFY_REDIRECT_URI
        }
        
        response = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=data)
        return response.json()
    
    def refresh_access_token(self, refresh_token):
        """Refresh the access token"""
        auth_header = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
        
        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        response = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=data)
        return response.json()
    
    def make_request(self, endpoint, access_token, params=None):
        """Make authenticated request to Spotify API"""
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(f"{self.base_url}{endpoint}", headers=headers, params=params)
        
        if response.status_code == 401:
            # Token expired, need to refresh
            return None
        
        return response.json()
    
    def get_followed_artists(self, access_token, limit=50):
        """Get user's followed artists"""
        artists = []
        after = None
        
        while True:
            params = {'type': 'artist', 'limit': limit}
            if after:
                params['after'] = after
            
            data = self.make_request('/me/following', access_token, params)
            if not data:
                break
            
            artists.extend(data['artists']['items'])
            
            if not data['artists']['next']:
                break
            
            after = data['artists']['cursors']['after']
        
        return artists
    
    def get_related_artists(self, access_token, artist_id):
        """Get related artists (Fans also like)"""
        data = self.make_request(f'/artists/{artist_id}/related-artists', access_token)
        return data['artists'] if data else []
    
    def get_artist_albums(self, access_token, artist_id, limit=20):
        """Get artist's recent albums and singles"""
        params = {
            'include_groups': 'album,single',
            'market': 'US',
            'limit': limit
        }
        data = self.make_request(f'/artists/{artist_id}/albums', access_token, params)
        return data['items'] if data else []
    
    def get_album_tracks(self, access_token, album_id):
        """Get tracks from an album"""
        data = self.make_request(f'/albums/{album_id}/tracks', access_token)
        return data['items'] if data else []
    
    def create_playlist(self, access_token, user_id, name, description):
        """Create a new playlist"""
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        data = {
            'name': name,
            'description': description,
            'public': False
        }
        
        response = requests.post(
            f"{self.base_url}/users/{user_id}/playlists",
            headers=headers,
            json=data
        )
        return response.json()
    
    def add_tracks_to_playlist(self, access_token, playlist_id, track_uris):
        """Add tracks to playlist"""
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        
        # Spotify allows max 100 tracks per request
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i+100]
            data = {'uris': batch}
            
            requests.post(
                f"{self.base_url}/playlists/{playlist_id}/tracks",
                headers=headers,
                json=data
            )
    
    def get_user_profile(self, access_token):
        """Get user profile information"""
        return self.make_request('/me', access_token)

spotify_api = SpotifyAPI()

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/login')
def login():
    """Redirect to Spotify authorization"""
    auth_url = spotify_api.get_auth_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    """Handle Spotify authorization callback"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        return f"Authorization failed: {error}"
    
    if not state or state != session.get('oauth_state'):
        return "Invalid state parameter"
    
    # Exchange code for tokens
    token_data = spotify_api.get_access_token(code)
    
    if 'access_token' in token_data:
        session['access_token'] = token_data['access_token']
        session['refresh_token'] = token_data.get('refresh_token')
        session['token_expires_at'] = datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))
        
        return redirect(url_for('dashboard'))
    else:
        return f"Failed to get access token: {token_data}"

@app.route('/dashboard')
def dashboard():
    """Main dashboard after authentication"""
    if 'access_token' not in session:
        return redirect(url_for('login'))
    
    # Get user profile
    user_profile = spotify_api.get_user_profile(session['access_token'])
    if not user_profile:
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', user=user_profile)

@app.route('/generate-playlist', methods=['POST'])
def generate_playlist():
    """Generate playlist with recent releases from followed and related artists"""
    if 'access_token' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    access_token = session['access_token']
    
    try:
        # Get followed artists
        followed_artists = spotify_api.get_followed_artists(access_token)
        print(f"Found {len(followed_artists)} followed artists")
        
        # Collect all artists (followed + related)
        all_artists = set()
        for artist in followed_artists:
            all_artists.add(artist['id'])
            
            # Get related artists (limit to 5 per followed artist to avoid too many)
            related_artists = spotify_api.get_related_artists(access_token, artist['id'])
            for related in related_artists[:5]:  # Limit to 5 related artists per followed artist
                all_artists.add(related['id'])
        
        print(f"Total artists to check: {len(all_artists)}")
        
        # Get recent releases (last 7 days)
        one_week_ago = datetime.now() - timedelta(days=7)
        recent_tracks = []
        
        for artist_id in list(all_artists)[:50]:  # Limit to 50 artists to avoid rate limits
            albums = spotify_api.get_artist_albums(access_token, artist_id, limit=10)
            
            for album in albums:
                # Check if album was released in the last week
                release_date = datetime.strptime(album['release_date'], '%Y-%m-%d' if len(album['release_date']) == 10 else '%Y')
                
                if release_date >= one_week_ago:
                    tracks = spotify_api.get_album_tracks(access_token, album['id'])
                    for track in tracks:
                        recent_tracks.append({
                            'uri': track['uri'],
                            'name': track['name'],
                            'artist': album['artists'][0]['name'],
                            'album': album['name'],
                            'release_date': album['release_date']
                        })
        
        if not recent_tracks:
            return jsonify({'message': 'No recent releases found from the last week'})
        
        # Create playlist
        user_profile = spotify_api.get_user_profile(access_token)
        playlist_name = f"Weekly Discoveries - {datetime.now().strftime('%Y-%m-%d')}"
        playlist_description = f"Recent releases from your followed artists and their related artists (last 7 days). Generated on {datetime.now().strftime('%Y-%m-%d')}"
        
        playlist = spotify_api.create_playlist(
            access_token,
            user_profile['id'],
            playlist_name,
            playlist_description
        )
        
        # Add tracks to playlist
        track_uris = [track['uri'] for track in recent_tracks]
        spotify_api.add_tracks_to_playlist(access_token, playlist['id'], track_uris)
        
        return jsonify({
            'success': True,
            'playlist_name': playlist_name,
            'playlist_url': playlist['external_urls']['spotify'],
            'tracks_added': len(recent_tracks),
            'tracks': recent_tracks[:10]  # Return first 10 tracks for preview
        })
        
    except Exception as e:
        print(f"Error generating playlist: {str(e)}")
        return jsonify({'error': f'Failed to generate playlist: {str(e)}'}), 500

@app.route('/logout')
def logout():
    """Clear session and logout"""
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables")
        exit(1)
    
    app.run(debug=True, port=5000)
