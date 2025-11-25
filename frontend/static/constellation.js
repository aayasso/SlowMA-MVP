/**
 * Constellation Canvas - Interactive star visualization
 * Click stars to view artwork details and re-visit journeys
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
        this.hoveredStar = null;
        this.mouseX = 0;
        this.mouseY = 0;
        
        // Set canvas size
        this.resize();
        window.addEventListener('resize', () => this.resize());
        
        // Initialize stars
        this.initStars();
        
        // Add mouse interactions
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
        this.canvas.style.cursor = 'default';
        
        // Start animation
        this.animate();
        
        console.log('Constellation created with', this.stars.length, 'stars');
    }
    
    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }
    
    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        this.mouseX = e.clientX - rect.left;
        this.mouseY = e.clientY - rect.top;
        
        console.log('Mouse move detected:', this.mouseX, this.mouseY);
        
        // Check if hovering over a clickable star
        this.hoveredStar = null;
        for (let star of this.stars) {
            if (star.type === 'journey' || star.type === 'seed') {
                const distance = Math.hypot(this.mouseX - star.x, this.mouseY - star.y);
                if (distance < 30) {
                    this.hoveredStar = star;
                    console.log('Hovering over star:', star.title);
                    this.canvas.style.cursor = 'pointer';
                    return;
                }
            }
        }
        this.canvas.style.cursor = 'default';
    }
    
    handleClick(e) {
        if (this.hoveredStar) {
            this.showStarModal(this.hoveredStar);
        }
    }
    
    showStarModal(star) {
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'star-modal';
        
        // Build thumbnail HTML if we have an image
        let thumbnailHTML = '';
        if (star.type === 'seed' && star.thumbnail) {
            thumbnailHTML = '<img src="/static/seed_artworks/' + star.thumbnail + '" alt="' + star.title + '" class="artwork-thumbnail">';
        } else if (star.type === 'journey' && star.id) {
            thumbnailHTML = '<img src="/uploads/' + star.id + '.jpg" alt="' + star.title + '" class="artwork-thumbnail" onerror="this.style.display=\'none\'">';
        }
        
        const journeyButton = star.type === 'journey' 
            ? '<button class="btn-primary" onclick="window.location.href=\'/walkthrough/' + star.id + '\'">Re-visit This Journey</button>'
            : '<p class="seed-message">This is a seed artwork. Upload a photo to begin your journey!</p>';
        
        modal.innerHTML = '<div class="star-modal-content">' +
            '<button class="star-modal-close" onclick="this.parentElement.parentElement.remove()">×</button>' +
            thumbnailHTML +
            '<h2>' + (star.title || 'Untitled Artwork') + '</h2>' +
            (star.artist ? '<p class="artist-name">' + star.artist + '</p>' : '') +
            (star.completed_at ? '<p class="journey-date">Journey completed: ' + new Date(star.completed_at).toLocaleDateString() + '</p>' : '') +
            journeyButton +
            '</div>';
        
        document.body.appendChild(modal);
        
        // Close on background click
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }
    
    initStars() {
        const centerX = this.canvas.width / 2;
        const centerY = 200;
        
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
        
        // Seed stars (4 pre-loaded artworks)
        if (this.data.show_seeds && this.data.seed_artworks) {
            const seedRadius = 180;
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
                    thumbnail: seed.thumbnail,
                    x: x,
                    y: y,
                    size: 6,
                    color: '#FFD700',
                    pulsePhase: index * 0.5,
                    targetX: x,
                    targetY: y
                });
            });
        }
        
        // Journey stars (completed artworks)
        if (this.data.journeys && this.data.journeys.length > 0) {
            const journeys = this.data.journeys.slice().reverse();
            const baseRadius = 150;
            const radiusIncrement = 80;
            
            let currentRing = 0;
            let starsInCurrentRing = 8;
            let starsPlacedInRing = 0;
            
            journeys.forEach((journey, index) => {
                const currentRadius = baseRadius + (currentRing * radiusIncrement);
                const angleStep = (Math.PI * 2) / starsInCurrentRing;
                const angle = angleStep * starsPlacedInRing;
                
                const x = centerX + Math.cos(angle) * currentRadius;
                const y = centerY + Math.sin(angle) * currentRadius;
                
                this.stars.push({
                    type: 'journey',
                    id: journey.id,
                    title: journey.title,
                    artist: journey.artist,
                    x: x,
                    y: y,
                    size: 5,
                    color: this.getStageColor(journey.stage || 1),
                    pulsePhase: index * 0.3,
                    targetX: x,
                    targetY: y,
                    completed_at: journey.completed_at
                });
                
                starsPlacedInRing++;
                
                if (starsPlacedInRing >= starsInCurrentRing) {
                    currentRing++;
                    starsPlacedInRing = 0;
                    starsInCurrentRing = Math.min(8 + (currentRing * 2), 16);
                }
            });
        }
    }
    
    getStageColor(stage) {
        const colors = {
            1: '#FF6B6B',
            2: '#4ECDC4',
            3: '#A78BFA',
            4: '#FBBF24',
            5: '#34D399'
        };
        return colors[stage] || colors[1];
    }
    
    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        const time = Date.now() / 1000;
        
        // Draw connections
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        this.ctx.lineWidth = 1;
        
        for (let i = 0; i < this.stars.length; i++) {
            for (let j = i + 1; j < this.stars.length; j++) {
                const star1 = this.stars[i];
                const star2 = this.stars[j];
                const distance = Math.hypot(star2.x - star1.x, star2.y - star1.y);
                
                if (distance < 200) {
                    const opacity = (1 - distance / 200) * 0.2;
                    this.ctx.strokeStyle = 'rgba(255, 255, 255, ' + opacity + ')';
                    this.ctx.beginPath();
                    this.ctx.moveTo(star1.x, star1.y);
                    this.ctx.lineTo(star2.x, star2.y);
                    this.ctx.stroke();
                }
            }
        }
        
        // Draw stars
        this.stars.forEach((star) => {
            const isHovered = this.hoveredStar === star;
            const pulse = Math.sin(time + star.pulsePhase) * 0.3 + 1;
            const hoverBoost = isHovered ? 1.5 : 1;
            const size = star.size * pulse * hoverBoost;
            
            // Glow effect
            const glowMultiplier = isHovered ? 5 : 3;
            const gradient = this.ctx.createRadialGradient(
                star.x, star.y, 0,
                star.x, star.y, size * glowMultiplier
            );
            
            const opacity = isHovered ? 'FF' : '80';
            gradient.addColorStop(0, star.color);
            gradient.addColorStop(0.4, star.color + opacity);
            gradient.addColorStop(1, star.color + '00');
            
            this.ctx.fillStyle = gradient;
            this.ctx.beginPath();
            this.ctx.arc(star.x, star.y, size * glowMultiplier, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Core star
            this.ctx.fillStyle = star.color;
            this.ctx.globalAlpha = isHovered ? 1 : 0.8;
            this.ctx.beginPath();
            this.ctx.arc(star.x, star.y, size, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.globalAlpha = 1;
            
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
    
    window.constellationInstance = new Constellation('constellationCanvas', data);
}