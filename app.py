"""
SlowMA - Slow Looking Art Education App
Main application server

Run this file to start the app: python3 app.py
Then open your browser to: http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from pathlib import Path
import json
import base64
from datetime import datetime
import os
from werkzeug.utils import secure_filename

# Import our backend modules
from backend.slow_looking_engine import SlowLookingEngine
from backend.user_assessment import UserAssessment
from backend.activity_generator import ActivityGenerator
from backend.data_manager import DataManager

# Initialize Flask app
app = Flask(__name__, template_folder='frontend/templates', static_folder='frontend/static')
app.config['SECRET_KEY'] = 'slow-looking-dev-key'
app.config['UPLOAD_FOLDER'] = Path('uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create necessary directories
Path('uploads').mkdir(exist_ok=True)
Path('data/gallery').mkdir(parents=True, exist_ok=True)

# Initialize backend systems
engine = SlowLookingEngine()
user_assessment = UserAssessment()
activity_gen = ActivityGenerator()
data_manager = DataManager()

# Load or create user profile
user_profile = data_manager.load_user_profile()


@app.route('/')
def index():
    """Landing page with upload button"""
    return render_template('index.html', 
                         user=user_profile,
                         notifications=user_assessment.get_notifications(user_profile))


@app.route('/upload', methods=['POST'])
def upload_artwork():
    """Handle artwork image upload"""
    if 'artwork' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['artwork']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save uploaded file
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    filepath = app.config['UPLOAD_FOLDER'] / unique_filename
    file.save(filepath)
    
    # Check if at museum (simulated for prototype - will use GPS in mobile app)
    at_museum = request.form.get('at_museum') == 'true'
    
    # Update user stats
    if at_museum:
        user_profile['museum_visits'] += 1
        data_manager.check_and_award_badge(user_profile, 'museum_visitor')
    
    return jsonify({
        'success': True,
        'filepath': str(filepath),
        'at_museum': at_museum
    })


@app.route('/analyze', methods=['POST'])
def analyze_artwork():
    """Analyze artwork and create personalized walkthrough"""
    data = request.json
    filepath = Path(data['filepath'])
    
    if not filepath.exists():
        return jsonify({'error': 'File not found'}), 404
    
    # Get user's current Housen stage for personalization
    housen_stage = user_profile['housen_stage']
    housen_substage = user_profile['housen_substage']
    
    # Create personalized journey
    try:
        journey = engine.create_journey(
            filepath, 
            housen_stage=housen_stage,
            housen_substage=housen_substage
        )
        
        # Store journey in session
        journey_id = journey['journey_id']
        journey['image_path'] = str(filepath)
        journey['at_museum'] = data.get('at_museum', False)
        journey['started_at'] = datetime.now().isoformat()
        
        # Save journey for this session
        data_manager.save_active_journey(journey)
        
        return jsonify({
            'success': True,
            'journey_id': journey_id,
            'journey': journey
        })
        
    except Exception as e:
        print(f"Error analyzing artwork: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/walkthrough/<journey_id>')
def walkthrough(journey_id):
    """Display walkthrough interface"""
    journey = data_manager.load_active_journey(journey_id)
    if not journey:
        return "Journey not found", 404
    
    return render_template('walkthrough.html', 
                         journey=journey,
                         user_stage=f"{user_profile['housen_stage']}.{user_profile['housen_substage']}")


@app.route('/walkthrough/step/<journey_id>/<int:step_num>', methods=['POST'])
def complete_step(journey_id, step_num):
    """Record step completion and timing"""
    data = request.json
    time_spent = data.get('time_spent', 0)
    
    # Update user stats
    user_profile['total_time_seconds'] += time_spent
    data_manager.save_user_profile(user_profile)
    
    # Check for time-based badges
    data_manager.check_and_award_badge(user_profile, 'time_spent')
    
    return jsonify({'success': True})


@app.route('/reflection/<journey_id>')
def reflection(journey_id):
    """Generate and display reflection activities"""
    journey = data_manager.load_active_journey(journey_id)
    if not journey:
        return "Journey not found", 404
    
    # Generate reflection activities based on journey and user level
    activities = activity_gen.generate_activities(
        journey=journey,
        housen_stage=user_profile['housen_stage'],
        housen_substage=user_profile['housen_substage']
    )
    
    # Store activities with journey
    journey['reflection_activities'] = activities
    data_manager.save_active_journey(journey)
    
    return render_template('reflection.html', 
                         journey=journey,
                         activities=activities)


@app.route('/reflection/submit/<journey_id>', methods=['POST'])
def submit_reflection(journey_id):
    """Assess user's reflection responses and update Housen stage"""
    data = request.json
    responses = data.get('responses', {})
    
    # Load journey
    journey = data_manager.load_active_journey(journey_id)
    if not journey:
        return jsonify({'error': 'Journey not found'}), 404
    
    # Assess responses
    assessment_result = user_assessment.assess_responses(
        responses=responses,
        journey=journey,
        current_stage=user_profile['housen_stage'],
        current_substage=user_profile['housen_substage']
    )
    
    # Update user profile
    old_stage = f"{user_profile['housen_stage']}.{user_profile['housen_substage']}"
    user_profile['housen_stage'] = assessment_result['new_stage']
    user_profile['housen_substage'] = assessment_result['new_substage']
    new_stage = f"{user_profile['housen_stage']}.{user_profile['housen_substage']}"
    
    # Track progression
    user_profile['stage_history'].append({
        'date': datetime.now().isoformat(),
        'stage': new_stage,
        'change': assessment_result['change']
    })
    
    # Update engagement quality tracking
    user_profile['recent_quality_scores'].append(assessment_result['quality_score'])
    if len(user_profile['recent_quality_scores']) > 10:
        user_profile['recent_quality_scores'].pop(0)
    
    # Update journey completion count
    user_profile['journeys_completed'] += 1
    user_profile['last_activity'] = datetime.now().isoformat()
    
    # Check for badges
    data_manager.check_and_award_badge(user_profile, 'quality_engagement')
    data_manager.check_and_award_badge(user_profile, 'stage_progression')
    
    # Save journey to gallery
    journey['responses'] = responses
    journey['assessment'] = assessment_result
    journey['completed_at'] = datetime.now().isoformat()
    data_manager.save_to_gallery(journey, user_profile)
    
    # Save updated profile
    data_manager.save_user_profile(user_profile)
    
    # Check if stage changed for notification
    stage_changed = old_stage != new_stage
    improvement = assessment_result['change'] == 'progression'
    
    return jsonify({
        'success': True,
        'assessment': assessment_result,
        'stage_changed': stage_changed,
        'improvement': improvement,
        'new_stage': new_stage,
        'feedback': assessment_result.get('feedback', '')
    })


@app.route('/gallery')
def gallery():
    """Display user's saved journeys"""
    journeys = data_manager.load_gallery(user_profile)
    return render_template('gallery.html', 
                         journeys=journeys,
                         total=len(journeys))


@app.route('/gallery/<journey_id>')
def view_journey(journey_id):
    """View a specific saved journey"""
    journey = data_manager.load_gallery_journey(journey_id, user_profile)
    if not journey:
        return "Journey not found", 404
    
    return render_template('journey_detail.html', journey=journey)


@app.route('/profile')
def profile():
    """Display user profile with stats and badges"""
    # Calculate stats
    stats = {
        'journeys_completed': user_profile['journeys_completed'],
        'total_time_minutes': round(user_profile['total_time_seconds'] / 60, 1),
        'museum_visits': user_profile['museum_visits'],
        'current_streak': user_assessment.calculate_streak(user_profile),
        'badges_earned': len(user_profile['badges']),
        'stage': f"{user_profile['housen_stage']}.{user_profile['housen_substage']}"
    }
    
    # Get Housen stage info
    stage_info = user_assessment.get_stage_description(
        user_profile['housen_stage'],
        user_profile['housen_substage']
    )
    
    return render_template('profile.html', 
                         user=user_profile,
                         stats=stats,
                         stage_info=stage_info)


@app.route('/api/check_inactivity')
def check_inactivity():
    """Check for inactivity-based regression"""
    regressed = user_assessment.check_inactivity_regression(user_profile)
    if regressed:
        data_manager.save_user_profile(user_profile)
    
    return jsonify({
        'regressed': regressed,
        'current_stage': f"{user_profile['housen_stage']}.{user_profile['housen_substage']}"
    })


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded images"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/tutorial')
def tutorial():
    """Show slow looking tutorial for new users"""
    return render_template('tutorial.html')


@app.route('/tutorial/complete', methods=['POST'])
def complete_tutorial():
    """Mark tutorial as completed"""
    user_profile['tutorial_completed'] = True
    data_manager.save_user_profile(user_profile)
    return jsonify({'success': True})


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("SlowMA - Slow Looking Art Education App")
    print("="*60)
    print("\nStarting server...")
    print("Open your browser to: http://localhost:5001")
    print("\nPress Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5001)