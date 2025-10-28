/**
 * Constellation Canvas - Dynamic star visualization
 * Represents user's journey through slow looking
 */

class Constellation {
    constructor(canvasId, constellationData) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error('Canvas not found:', canvasId);
            return;
        }
        
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
        if (this.data.journey_count < 10 && this.data.seed_artworks) {
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
                    color: '#ffd700',
                    shimmer: Math.random()
                });
            });
        }
        
        // Create stars for completed journeys
        if (this.data.journeys && this.data.journeys.length > 0) {
            this.data.journeys.forEach((journey, index) => {
                const star = this.createJourneyStar(journey, index);
                this.stars.push(star);
            });
            
            // Organize stars into constellations
            this.organizeConstellations();
        }
    }
    
    createJourneyStar(journey, index) {
        const totalJourneys = this.data.journeys.length;
        const recency = (totalJourneys - index) / totalJourneys;
        
        const minDistance = 60;
        const maxDistance = Math.min(this.canvas.width, this.canvas.height) * 0.4;
        const distance = minDistance + (1 - recency) * (maxDistance - minDistance);
        
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
        const stageGroups = {1: [], 2: [], 3: [], 4: [], 5: []};
        
        this.stars.forEach(star => {
            if (star.type === 'journey' && star.stage) {
                stageGroups[star.stage].push(star);
            }
        });
        
        Object.keys(stageGroups).forEach(stage => {
            const stars = stageGroups[stage];
            const stageAngle = ((stage - 1) * Math.PI * 2) / 5;
            const spread = Math.PI / 3;
            
            stars.forEach((star, index) => {
                const offset = (index / stars.length - 0.5) * spread;
                const angle = stageAngle + offset;
                
                const minDistance = 60;
                const maxDistance = Math.min(this.canvas.width, this.canvas.height) * 0.4;
                const distance = minDistance + (1 - star.recency) * (maxDistance - minDistance);
                
                star.targetX = this.centerX + Math.cos(angle) * distance;
                star.targetY = this.centerY + Math.sin(angle) * distance;
            });
        });
    }
    
    getAngleForStage(stage, index) {
        const baseAngle = ((stage - 1) * Math.PI * 2) / 5;
        const jitter = (Math.random() - 0.5) * 0.3;
        return baseAngle + jitter;
    }
    
    getStageColor(stage) {
        const colors = {
            1: '#ff6b6b',
            2: '#4ecdc4',
            3: '#9b59b6',
            4: '#f39c12',
            5: '#e8f5e9'
        };
        return colors[stage] || '#ffffff';
    }
    
    getCompanionColor() {
        const stage = this.data.current_stage;
        return this.getStageColor(stage);
    }
    
    animate() {
        this.time += 0.01;
        
        const gradient = this.ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        gradient.addColorStop(0, '#1a1a2e');
        gradient.addColorStop(1, '#16213e');
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        this.drawCompanionStar();
        this.stars.forEach(star => this.drawStar(star));
        this.drawConnections();
        
        requestAnimationFrame(() => this.animate());
    }
    
    drawCompanionStar() {
        const star = this.companionStar;
        star.pulse = this.time;
        const pulseFactor = 1 + Math.sin(star.pulse) * 0.1;
        star.size = star.baseSize * pulseFactor;
        
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
        
        this.ctx.fillStyle = star.color;
        this.ctx.beginPath();
        this.ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
        this.ctx.fill();
    }
    
    drawStar(star) {
        star.pulse += 0.02;
        const pulseFactor = 1 + Math.sin(star.pulse) * 0.15;
        star.size = star.baseSize * pulseFactor;
        
        if (star.type === 'seed') {
            star.shimmer += 0.01;
            const shimmerAlpha = (Math.sin(star.shimmer) + 1) * 0.3 + 0.4;
            
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
        
        this.ctx.fillStyle = star.color;
        this.ctx.beginPath();
        this.ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
        this.ctx.fill();
        
        if (star.targetX !== undefined) {
            star.x += (star.targetX - star.x) * 0.02;
            star.y += (star.targetY - star.y) * 0.02;
        }
    }
    
    drawConnections() {
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        this.ctx.lineWidth = 1;
        
        for (let i = 0; i < this.stars.length; i++) {
            for (let j = i + 1; j < this.stars.length; j++) {
                const star1 = this.stars[i];
                const star2 = this.stars[j];
                
                if (star1.stage === star2.stage && star1.type === 'journey' && star2.type === 'journey') {
                    const distance = Math.hypot(star2.x - star1.x, star2.y - star1.y);
                    
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
        
        for (let star of this.stars) {
            const distance = Math.hypot(x - star.x, y - star.y);
            if (distance < star.size + 10) {
                this.showStarPreview(star);
                return;
            }
        }
        
        const compDistance = Math.hypot(x - this.companionStar.x, y - this.companionStar.y);
        if (compDistance < this.companionStar.size + 15) {
            this.showCompanionInfo();
        }
    }
    
    showStarPreview(star) {
        if (star.type === 'seed') {
            alert(`Seed Artwork: ${star.title}\nby ${star.artist}\n\nTap to begin your journey with this artwork.`);
        } else if (star.type === 'journey') {
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

// Initialize constellation - called from index.html
function initConstellation(data) {
    // Wait a moment for DOM to fully settle
    setTimeout(function() {
        const canvas = document.getElementById('constellationCanvas');
        if (!canvas) {
            console.error('Canvas element not found!');
            return;
        }
        
        if (!data || typeof data.journey_count === 'undefined') {
            console.error('Invalid constellation data:', data);
            return;
        }
        
        console.log('Creating constellation with', data.journey_count, 'journeys');
        new Constellation('constellationCanvas', data);
    }, 100);
}