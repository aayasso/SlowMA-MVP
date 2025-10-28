/**
 * Constellation Canvas - Dynamic star visualization
 * Represents user's journey through slow looking
 */

class Constellation {
    constructor(canvasId, constellationData) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.data = constellationData;
        
        // Animation state
        this.time = 0;
        this.stars = [];
        this.companionStar = null;
        
        // Setup
        this.resize();
        this.initializeStars();
        this.animate();
        
        // Handle window resize
        window.addEventListener('resize', () => this.resize());
        
        // Handle clicks
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
    }
    
    resize() {
        this.canvas.width = this.canvas.offsetWidth;
        this.canvas.height = this.canvas.offsetHeight;
        this.centerX = this.canvas.width / 2;
        this.centerY = this.canvas.height / 2;
    }
    
    initializeStars() {
        // Create companion star (center)
        this.companionStar = {
            type: 'companion',
            x: this.centerX,
            y: this.centerY,
            baseSize: 8,
            size: 8,
            pulse: 0,
            color: this.getCompanionColor(),
            glow: 15
        };
        
        // Create seed stars (if user has < 10 journeys)
        if (this.data.journey_count < 10) {
            this.data.seed_artworks.forEach((seed, index) => {
                const angle = (Math.PI * 2 * index) / this.data.seed_artworks.length;
                const distance = Math.min(this.canvas.width, this.canvas.height) * 0.25;
                
                this.stars.push({
                    type: 'seed',
                    id: seed.id,
                    title: seed.title,
                    artist: seed.artist,
                    x: this.centerX + Math.cos(angle) * distance,
                    y: this.centerY + Math.sin(angle) * distance,
                    baseSize: 5,
                    size: 5,
                    pulse: Math.random() * Math.PI * 2,
                    color: '#ffd700', // Gold for seeds
                    shimmer: Math.random()
                });
            });
        }
        
        // Create stars for completed journeys
        this.data.journeys.forEach((journey, index) => {
            const star = this.createJourneyStar(journey, index);
            this.stars.push(star);
        });
        
        // Organize stars into constellations
        this.organizeConstellations();
    }
    
    createJourneyStar(journey, index) {
        // Position based on recency (more recent = closer to center)
        const totalJourneys = this.data.journeys.length;
        const recency = (totalJourneys - index) / totalJourneys; // 1 = most recent
        
        // Base distance from center (recent = closer)
        const minDistance = 60;
        const maxDistance = Math.min(this.canvas.width, this.canvas.height) * 0.4;
        const distance = minDistance + (1 - recency) * (maxDistance - minDistance);
        
        // Angle based on stage and constellation grouping
        const angle = this.getAngleForStage(journey.stage, index);
        
        return {
            type: 'journey',
            id: journey.journey_id,
            title: journey.artwork_title,
            artist: journey.artwork_artist,
            stage: journey.stage,
            substage: journey.substage,
            timestamp: journey.completed_at,
            x: this.centerX + Math.cos(angle) * distance,
            y: this.centerY + Math.sin(angle) * distance,
            baseSize: 4,
            size: 4,
            pulse: Math.random() * Math.PI * 2,
            color: this.getStageColor(journey.stage),
            recency: recency
        };
    }
    
    organizeConstellations() {
        // Group stars by stage
        const stageGroups = {1: [], 2: [], 3: [], 4: [], 5: []};
        
        this.stars.forEach(star => {
            if (star.type === 'journey' && star.stage) {
                stageGroups[star.stage].push(star);
            }
        });
        
        // Arrange each stage group in its own sector
        Object.keys(stageGroups).forEach(stage => {
            const stars = stageGroups[stage];
            const stageAngle = ((stage - 1) * Math.PI * 2) / 5;
            const spread = Math.PI / 3; // 60 degree spread per stage
            
            stars.forEach((star, index) => {
                const offset = (index / stars.length - 0.5) * spread;
                const angle = stageAngle + offset;
                
                // Recalculate position in constellation
                const minDistance = 60;
                const maxDistance = Math.min(this.canvas.width, this.canvas.height) * 0.4;
                const distance = minDistance + (1 - star.recency) * (maxDistance - minDistance);
                
                star.targetX = this.centerX + Math.cos(angle) * distance;
                star.targetY = this.centerY + Math.sin(angle) * distance;
            });
        });
    }
    
    getAngleForStage(stage, index) {
        // Each stage gets a sector of the circle
        const baseAngle = ((stage - 1) * Math.PI * 2) / 5;
        const jitter = (Math.random() - 0.5) * 0.3;
        return baseAngle + jitter;
    }
    
    getStageColor(stage) {
        const colors = {
            1: '#ff6b6b', // Warm orange-red (Accountive)
            2: '#4ecdc4', // Blue (Constructive)
            3: '#9b59b6', // Purple (Classifying)
            4: '#f39c12', // Gold (Interpretive)
            5: '#e8f5e9'  // Soft white (Re-creative)
        };
        return colors[stage] || '#ffffff';
    }
    
    getCompanionColor() {
        // Color shifts based on user's current stage
        const stage = this.data.current_stage;
        return this.getStageColor(stage);
    }
    
    animate() {
        this.time += 0.01;
        
        // Clear canvas with twilight gradient
        const gradient = this.ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        gradient.addColorStop(0, '#1a1a2e');
        gradient.addColorStop(1, '#16213e');
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw companion star
        this.drawCompanionStar();
        
        // Draw all stars
        this.stars.forEach(star => this.drawStar(star));
        
        // Draw connections between nearby stars
        this.drawConnections();
        
        requestAnimationFrame(() => this.animate());
    }
    
    drawCompanionStar() {
        const star = this.companionStar;
        
        // Gentle pulse
        star.pulse = this.time;
        const pulseFactor = 1 + Math.sin(star.pulse) * 0.1;
        star.size = star.baseSize * pulseFactor;
        
        // Glow effect
        const gradient = this.ctx.createRadialGradient(
            star.x, star.y, 0,
            star.x, star.y, star.glow * pulseFactor
        );
        gradient.addColorStop(0, star.color);
        gradient.addColorStop(0.5, star.color + '88');
        gradient.addColorStop(1, 'transparent');
        
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(
            star.x - star.glow * pulseFactor,
            star.y - star.glow * pulseFactor,
            star.glow * 2 * pulseFactor,
            star.glow * 2 * pulseFactor
        );
        
        // Core star
        this.ctx.fillStyle = star.color;
        this.ctx.beginPath();
        this.ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
        this.ctx.fill();
    }
    
    drawStar(star) {
        // Gentle pulse
        star.pulse += 0.02;
        const pulseFactor = 1 + Math.sin(star.pulse) * 0.15;
        star.size = star.baseSize * pulseFactor;
        
        // Shimmer for seed stars
        if (star.type === 'seed') {
            star.shimmer += 0.01;
            const shimmerAlpha = (Math.sin(star.shimmer) + 1) * 0.3 + 0.4;
            
            // Extra glow
            const gradient = this.ctx.createRadialGradient(
                star.x, star.y, 0,
                star.x, star.y, star.size * 3
            );
            gradient.addColorStop(0, star.color);
            gradient.addColorStop(0.5, star.color + Math.floor(shimmerAlpha * 255).toString(16));
            gradient.addColorStop(1, 'transparent');
            
            this.ctx.fillStyle = gradient;
            this.ctx.fillRect(
                star.x - star.size * 3,
                star.y - star.size * 3,
                star.size * 6,
                star.size * 6
            );
        }
        
        // Draw star
        this.ctx.fillStyle = star.color;
        this.ctx.beginPath();
        this.ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
        this.ctx.fill();
        
        // Smooth movement toward target position (for constellation organization)
        if (star.targetX !== undefined) {
            star.x += (star.targetX - star.x) * 0.02;
            star.y += (star.targetY - star.y) * 0.02;
        }
    }
    
    drawConnections() {
        // Draw subtle lines between stars in same stage
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        this.ctx.lineWidth = 1;
        
        for (let i = 0; i < this.stars.length; i++) {
            for (let j = i + 1; j < this.stars.length; j++) {
                const star1 = this.stars[i];
                const star2 = this.stars[j];
                
                // Only connect stars of same stage
                if (star1.stage === star2.stage && star1.type === 'journey' && star2.type === 'journey') {
                    const distance = Math.hypot(star2.x - star1.x, star2.y - star1.y);
                    
                    // Only draw if close enough
                    if (distance < 100) {
                        this.ctx.beginPath();
                        this.ctx.moveTo(star1.x, star1.y);
                        this.ctx.lineTo(star2.x, star2.y);
                        this.ctx.stroke();
                    }
                }
            }
        }
    }
    
    handleClick(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        
        // Check if clicked on a star
        for (let star of this.stars) {
            const distance = Math.hypot(x - star.x, y - star.y);
            if (distance < star.size + 10) { // Click tolerance
                this.showStarPreview(star);
                return;
            }
        }
        
        // Check companion star
        const compDistance = Math.hypot(x - this.companionStar.x, y - this.companionStar.y);
        if (compDistance < this.companionStar.size + 15) {
            this.showCompanionInfo();
        }
    }
    
    showStarPreview(star) {
        if (star.type === 'seed') {
            // Show seed artwork info and suggest starting with it
            alert(`Seed Artwork: ${star.title}\nby ${star.artist}\n\nTap to begin your journey with this artwork.`);
            // TODO: Trigger upload/journey with this seed artwork
        } else if (star.type === 'journey') {
            // Redirect to gallery view of this journey
            window.location.href = '/gallery/' + star.id;
        }
    }
    
    showCompanionInfo() {
        const stageNames = {
            1: 'Accountive - Making personal connections',
            2: 'Constructive - Building observations',
            3: 'Classifying - Analyzing technique',
            4: 'Interpretive - Exploring meaning',
            5: 'Re-creative - Synthesizing deeply'
        };
        
        const stageName = stageNames[this.data.current_stage] || 'Growing';
        alert(`Your Companion Star\n\nYou're currently at Stage ${this.data.current_stage}.${this.data.current_substage}\n${stageName}\n\nYour constellation has ${this.data.journey_count} stars.`);
    }
}

// Initialize constellation when data is loaded
function initConstellation(data) {
    new Constellation('constellationCanvas', data);
}