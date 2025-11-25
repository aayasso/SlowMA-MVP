"""
SlowMA - Slow Looking Art Education App
Main application server

Run this file to start the app: python3 app.py
Then open your browser to: http://localhost:5001
"""

from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect
import os
from pathlib import Path
from datetime import datetime
import uuid

# Import our backend modules
from backend.slow_looking_engine import SlowLookingEngine
from backend.user_assessment import UserAssessment
from backend.activity_generator import ActivityGenerator
from backend.data_manager import DataManager
from backend.auth_manager import AuthManager

app = Flask(__name__, 
           template_folder='frontend/templates',
           static_folder='frontend/static')

# Configure session security
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize backend components
slow_looking = SlowLookingEngine()
user_assessment = UserAssessment()
activity_generator = ActivityGenerator()
data_manager = DataManager()
auth_manager = AuthManager()

# Create necessary directories
Path('uploads').mkdir(exist_ok=True)
Path('data/gallery').mkdir(parents=True, exist_ok=True)

# Load or create user profile (for local/guest mode)
user_profile = data_manager.load_user_profile()

# Seed artworks (pre-loaded for new users)
SEED_ARTWORKS = [
    {
        "id": "seed_1",
        "title": "Woman with Red Hair",
        "artist": "Amadeo Modigliani",
        "year": "1917",
        "thumbnail": "modigliani_seed.jpg"
    },
    {
        "id": "seed_2", 
        "title": "Skeleton with a Burning Cigarette",
        "artist": "Vincent van Gogh",
        "year": "1886",
        "thumbnail": "vangogh_seed.jpg"
    },
    {
        "id": "seed_3",
        "title": "The Beheading of Saint John the Baptist",
        "artist": "Caravaggio",
        "year": "1608",
        "thumbnail": "caravaggio_seed.jpg"
    },
    {
        "id": "seed_4",
        "title": "Meditative Rose",
        "artist": "Salvador Dalí",
        "year": "1958",
        "thumbnail": "dali_seed.jpg"
    }
]


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/signin')
def signin_page():
    """Sign in page"""
    return render_template('signin.html')


@app.route('/signup')
def signup_page():
    """Sign up page"""
    return render_template('signup.html')


@app.route('/auth/signup', methods=['POST'])
def auth_signup():
    """Handle sign up"""
    data = request.get_json()
    
    email = data.get('email')
    password = data.get('password')
    username = data.get('username')
    
    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password required'}), 400
    
    result = auth_manager.sign_up_email(email, password, username)
    
    return jsonify(result)


@app.route('/auth/signin', methods=['POST'])
def auth_signin():
    """Handle sign in"""
    data = request.get_json()
    
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password required'}), 400
    
    result = auth_manager.sign_in_email(email, password)
    
    if result['success']:
        # Store user session
        session['user_id'] = result['user'].id
        session['user_email'] = result['user'].email
        
        # Return success without the full session object (not JSON serializable)
        return jsonify({
            'success': True,
            'message': 'Signed in successfully'
        })
    
    return jsonify(result)


@app.route('/auth/magic-link', methods=['POST'])
def auth_magic_link():
    """Send magic link"""
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({'success': False, 'error': 'Email required'}), 400
    
    result = auth_manager.sign_in_magic_link(email)
    return jsonify(result)


@app.route('/auth/google')
def auth_google():
    """Initiate Google OAuth"""
    result = auth_manager.sign_in_google()
    return jsonify(result)


@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback"""
    # Get the user after OAuth
    user = auth_manager.get_user()
    
    if user:
        session['user_id'] = user.id
        session['user_email'] = user.email
        return redirect('/')
    else:
        return redirect('/signin?error=auth_failed')


@app.route('/auth/signout', methods=['POST'])
def auth_signout():
    """Sign out"""
    auth_manager.sign_out()
    session.clear()
    return jsonify({'success': True})


@app.route('/auth/check')
def auth_check():
    """Check if user is authenticated"""
    user = auth_manager.get_user()
    
    if user:
        profile = auth_manager.get_user_profile(user.id)
        return jsonify({
            'authenticated': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'profile': profile
            }
        })
    else:
        return jsonify({'authenticated': False})


# ============================================================================
# MAIN APP ROUTES
# ============================================================================

@app.route('/')
def index():
    """Landing page with upload button"""
    
    # Check if user is authenticated
    user = auth_manager.get_user()
    
    if user:
        # Authenticated user - load their profile
        user_profile_data = auth_manager.get_user_profile(user.id)
        if user_profile_data:
            # User has profile in database
            constellation_data = data_manager.get_constellation_data(user_profile_data, SEED_ARTWORKS)
        else:
            # New OAuth user - create profile
            user_profile_data = {
                'id': user.id,
                'email': user.email,
                'housen_stage': 1,
                'housen_substage': 1,
                'journeys_completed': 0,
                'total_time_seconds': 0
            }
            constellation_data = data_manager.get_constellation_data(user_profile_data, SEED_ARTWORKS)
    else:
        # Guest user - use local data
        user_profile_data = user_profile
        constellation_data = data_manager.get_constellation_data(user_profile, SEED_ARTWORKS)
    
    return render_template('index.html', 
                         notifications=user_assessment.get_notifications(user_profile_data),
                         constellation_data=constellation_data,
                         user=user_profile_data,
                         authenticated=user is not None)


@app.route('/upload', methods=['POST'])
def upload_artwork():
    """Handle artwork image upload"""
    if 'artwork' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['artwork']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check if at museum
    at_museum = request.form.get('at_museum') == 'true'
    
    # Save file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{file.filename}"
    filepath = os.path.join('uploads', filename)
    file.save(filepath)
    
    return jsonify({
        'success': True,
        'filepath': filepath,
        'at_museum': at_museum
    })


@app.route('/analyze', methods=['POST'])
def analyze_artwork():
    """Analyze artwork and create journey"""
    data = request.get_json()
    filepath = data.get('filepath')
    at_museum = data.get('at_museum', False)
    
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'Invalid file path'}), 400
    
    # Get current user stage
    stage = user_profile.get('housen_stage', 1)
    substage = user_profile.get('housen_substage', 1)
    
    # Create journey
    journey = slow_looking.create_journey(filepath, stage, substage)
    
    if not journey:
        return jsonify({'error': 'Failed to analyze artwork'}), 500
    
    # Save journey
    journey_id = str(uuid.uuid4())
    journey['id'] = journey_id
    journey['at_museum'] = at_museum
    
    data_manager.save_journey(user_profile['id'], journey)
    
    return jsonify({
        'success': True,
        'journey_id': journey_id
    })


@app.route('/walkthrough/<journey_id>')
def walkthrough(journey_id):
    """Display walkthrough page"""
    journey = data_manager.load_journey(user_profile['id'], journey_id)
    
    if not journey:
        return "Journey not found", 404
    
    return render_template('walkthrough.html', journey=journey)


@app.route('/reflection/<journey_id>')
def reflection(journey_id):
    """Display reflection activities page"""
    journey = data_manager.load_journey(user_profile['id'], journey_id)
    
    if not journey:
        return "Journey not found", 404
    
    # Generate reflection activities
    activities = activity_generator.generate_activities(
        journey,
        user_profile.get('housen_stage', 1),
        user_profile.get('housen_substage', 1)
    )
    
    return render_template('reflection.html', 
                         journey=journey,
                         activities=activities)


@app.route('/submit-reflection', methods=['POST'])
def submit_reflection():
    """Process reflection responses and update user progress"""
    data = request.get_json()
    journey_id = data.get('journey_id')
    responses = data.get('responses')
    
    journey = data_manager.load_journey(user_profile['id'], journey_id)
    
    if not journey:
        return jsonify({'error': 'Journey not found'}), 404
    
    # Assess responses
    assessment = user_assessment.assess_responses(
        responses,
        journey,
        user_profile.get('housen_stage', 1),
        user_profile.get('housen_substage', 1)
    )
    
    # Update user profile
    if assessment['stage_change']:
        user_profile['housen_stage'] = assessment['new_stage']
        user_profile['housen_substage'] = assessment['new_substage']
    
    user_profile['journeys_completed'] += 1
    user_profile['last_activity'] = datetime.now().isoformat()
    
    # Check for new badges
    new_badges = user_assessment.check_badges(user_profile)
    
    # Save updated profile
    data_manager.save_user_profile(user_profile)
    
    # Save reflection
    data_manager.save_reflection(user_profile['id'], journey_id, {
        'responses': responses,
        'assessment': assessment,
        'timestamp': datetime.now().isoformat()
    })
    
    return jsonify({
        'success': True,
        'assessment': assessment,
        'new_badges': new_badges,
        'profile': user_profile
    })


@app.route('/gallery')
def gallery():
    """Display gallery of completed journeys"""
    journeys = data_manager.get_all_journeys(user_profile['id'])
    
    return render_template('gallery.html', 
                         journeys=journeys,
                         user=user_profile)


@app.route('/profile')
def profile():
    """Display user profile with stats"""
    
    # Get authenticated user or use local profile
    user = auth_manager.get_user()
    if user:
        user_profile_data = auth_manager.get_user_profile(user.id)
    else:
        user_profile_data = user_profile
    
    stats = data_manager.get_user_stats(user_profile_data['id'])
    
    # Get stage information
    stage = user_profile_data.get('housen_stage', 1)
    substage = user_profile_data.get('housen_substage', 1)
    
    stage_names = {
        1: {"name": "Accountive", "full_name": "Stage I: Accountive", "description": "Beginning to notice basic elements"},
        2: {"name": "Constructive", "full_name": "Stage II: Constructive", "description": "Building understanding through observation"},
        3: {"name": "Classifying", "full_name": "Stage III: Classifying", "description": "Categorizing and analyzing art"},
        4: {"name": "Interpretive", "full_name": "Stage IV: Interpretive", "description": "Developing personal interpretations"},
        5: {"name": "Re-creative", "full_name": "Stage V: Re-creative", "description": "Synthesizing multiple perspectives"}
    }
    
    stage_info = stage_names.get(stage, stage_names[1])
    
    return render_template('profile.html',
                         user=user_profile_data,
                         stats=stats,
                         stage_info=stage_info)


@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded files"""
    return send_from_directory('uploads', filename)


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# SERVER STARTUP with Content Security Policy fix
# ============================================================================

@app.after_request
def add_header(response):
    """Add headers for development"""
    response.headers['Content-Security-Policy'] = "default-src * 'unsafe-inline' 'unsafe-eval'; script-src * 'unsafe-inline' 'unsafe-eval'; connect-src * 'unsafe-inline'; img-src * data: blob: 'unsafe-inline'; frame-src *; style-src * 'unsafe-inline';"
    return response


if __name__ == '__main__':
    print("=" * 60)
    print("SlowMA - Slow Looking Art Education App")
    print("=" * 60)
    print("Starting server...")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Determine starting port
    start_port = int(os.environ.get('PORT', os.environ.get('SLOWMA_PORT', '5001')))
    host = os.environ.get('SLOWMA_HOST', '0.0.0.0')
    
    # Try a range of ports
    max_attempts = 10
    port = start_port
    for attempt in range(max_attempts):
        try:
            print(f"Attempting to start on http://localhost:{port} (host={host}) …")
            app.run(host=host, port=port, debug=True)
            break
        except OSError as e:
            message = str(e)
            in_use = 'Address already in use' in message or 'address already in use' in message
            if in_use and attempt < max_attempts - 1:
                print(f"Port {port} in use. Trying {port + 1} …")
                port += 1
                continue
            raise