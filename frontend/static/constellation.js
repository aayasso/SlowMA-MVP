/**
 * Constellation Canvas - Dynamic star visualization
 * Represents user's journey through slow looking
 */

class Constellation {
    constructor(canvasId, constellationData) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error('Canvas element not found:', canvasId);
            return;
        }
        
        this.ctx = this.canvas.getContext('2d');
        this.data = constellationData;
        this.stars = [];
        this.animationId = null;
        
        // Set canvas size
        this.resize();
        window.addEventListener('resize', () => this.resize());
        
        // Initialize stars
        this.initStars();
        
        // Start animation
        this.animate();
        
        console.log('Constellation created with', this.stars.length, 'stars');
    }
    
    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }
    
    initStars() {
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        
        // Companion star (center) - represents the user
        this.stars.push({
            type: 'companion',
            x: centerX,
            y: centerY,
            size: 8,
            color: this.getStageColor(this.data.companion_star.stage),
            pulsePhase: 0,
            targetX: centerX,
            targetY: centerY
        });
        
        // Seed stars (4 pre-loaded artworks) - only show if user has < 10 journeys
        if (this.data.show_seeds && this.data.seed_artworks) {
            const seedRadius = 150;
            const seedAngleStep = (Math.PI * 2) / this.data.seed_artworks.length;
            
            this.data.seed_artworks.forEach((seed, index) => {
                const angle = seedAngleStep * index;
                const x = centerX + Math.cos(angle) * seedRadius;
                const y = centerY + Math.sin(angle) * seedRadius;
                
                this.stars.push({
                    type: 'seed',
                    id: seed.id,
                    title: seed.title,
                    artist: seed.artist,
                    x: x,
                    y: y,
                    size: 5,
                    color: '#FFD700', // Gold color for seeds
                    pulsePhase: index * 0.5,
                    targetX: x,
                    targetY: y
                });
            });
        }
        
        // Journey stars (completed artworks)
        if (this.data.journeys && this.data.journeys.length > 0) {
            // Place journey stars in concentric circles, newest closest to center
            const journeys = [...this.data.journeys].reverse(); // Newest first
            const baseRadius = 100;
            const radiusIncrement = 50;
            let currentRadius = baseRadius;
            let starsInCurrentRing = 6;
            let starsPlaced = 0;
            
            journeys.forEach((journey, index) => {
                // Calculate position in current ring
                const angleStep = (Math.PI * 2) / starsInCurrentRing;
                const ringIndex = starsPlaced % starsInCurrentRing;
                const angle = angleStep * ringIndex + (Math.random() - 0.5) * 0.3; // Add slight randomness
                
                const x = centerX + Math.cos(angle) * currentRadius;
                const y = centerY + Math.sin(angle) * currentRadius;
                
                this.stars.push({
                    type: 'journey',
                    id: journey.id,
                    title: journey.title,
                    artist: journey.artist,
                    x: x,
                    y: y,
                    size: 4,
                    color: this.getStageColor(journey.stage || 1),
                    pulsePhase: index * 0.3,
                    targetX: x,
                    targetY: y
                });
                
                starsPlaced++;
                
                // Move to next ring when current ring is full
                if (starsPlaced % starsInCurrentRing === 0) {
                    currentRadius += radiusIncrement;
                    starsInCurrentRing += 2; // Each ring has more stars
                }
            });
        }
    }
    
    getStageColor(stage) {
        const colors = {
            1: '#FF6B6B', // Warm red-pink
            2: '#4ECDC4', // Teal
            3: '#A78BFA', // Purple
            4: '#FBBF24', // Amber
            5: '#34D399'  // Green
        };
        return colors[stage] || colors[1];
    }
    
    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        const time = Date.now() / 1000;
        
        // Draw connections between nearby stars
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        this.ctx.lineWidth = 1;
        
        for (let i = 0; i < this.stars.length; i++) {
            for (let j = i + 1; j < this.stars.length; j++) {
                const star1 = this.stars[i];
                const star2 = this.stars[j];
                const distance = Math.hypot(star2.x - star1.x, star2.y - star1.y);
                
                if (distance < 150) {
                    const opacity = (1 - distance / 150) * 0.2;
                    this.ctx.strokeStyle = `rgba(255, 255, 255, ${opacity})`;
                    this.ctx.beginPath();
                    this.ctx.moveTo(star1.x, star1.y);
                    this.ctx.lineTo(star2.x, star2.y);
                    this.ctx.stroke();
                }
            }
        }
        
        // Draw stars
        this.stars.forEach(star => {
            // Pulsing effect
            const pulse = Math.sin(time + star.pulsePhase) * 0.3 + 1;
            const size = star.size * pulse;
            
            // Glow effect
            const gradient = this.ctx.createRadialGradient(
                star.x, star.y, 0,
                star.x, star.y, size * 3
            );
            gradient.addColorStop(0, star.color);
            gradient.addColorStop(0.4, star.color + '80');
            gradient.addColorStop(1, star.color + '00');
            
            this.ctx.fillStyle = gradient;
            this.ctx.beginPath();
            this.ctx.arc(star.x, star.y, size * 3, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Core star
            this.ctx.fillStyle = star.color;
            this.ctx.beginPath();
            this.ctx.arc(star.x, star.y, size, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Extra glow for companion star
            if (star.type === 'companion') {
                this.ctx.fillStyle = star.color + '40';
                this.ctx.beginPath();
                this.ctx.arc(star.x, star.y, size * 5, 0, Math.PI * 2);
                this.ctx.fill();
            }
        });
        
        this.animationId = requestAnimationFrame(() => this.animate());
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
}

// Global initialization function
function initConstellation(data) {
    console.log('Initializing constellation with data:', data);
    
    if (!data) {
        console.error('No constellation data provided');
        return;
    }
    
    // Create constellation instance
    window.constellationInstance = new Constellation('constellationCanvas', data);
}