/**
 * SENTINEL-CORE: Analytics Engine & Bio-Feedback UI
 */

// --- 1. Background Starfield ---
const starCanvas = document.getElementById('starfield');
const sCtx = starCanvas.getContext('2d');
let stars = [];

function initStars() {
    starCanvas.width = window.innerWidth;
    starCanvas.height = window.innerHeight;
    stars = Array.from({ length: 200 }, () => ({
        x: Math.random() * starCanvas.width,
        y: Math.random() * starCanvas.height,
        z: Math.random() * 2 // depth/speed
    }));
}

function animateStars() {
    sCtx.clearRect(0, 0, starCanvas.width, starCanvas.height);
    sCtx.fillStyle = 'rgba(255, 255, 255, 0.8)';
    stars.forEach(star => {
        star.y += star.z * 0.5; // Drift downwards
        if (star.y > starCanvas.height) star.y = 0;
        sCtx.beginPath();
        sCtx.arc(star.x, star.y, star.z * 0.8, 0, Math.PI * 2);
        sCtx.fill();
    });
    requestAnimationFrame(animateStars);
}
initStars(); animateStars();
window.addEventListener('resize', initStars);

// --- 2. Central Particle Core (The Purple Dust) ---
const coreCanvas = document.getElementById('particle-core');
const cCtx = coreCanvas.getContext('2d');
const coreSize = 296;
coreCanvas.width = coreSize; coreCanvas.height = coreSize;
const center = coreSize / 2;
let particleSpeedMult = 1;

const particles = Array.from({ length: 300 }, () => ({
    x: Math.random() * coreSize, y: Math.random() * coreSize,
    vx: (Math.random() - 0.5) * 0.5, vy: (Math.random() - 0.5) * 0.5,
    size: Math.random() * 1.5, alpha: Math.random() * 0.6 + 0.2
}));

function animateCore() {
    cCtx.clearRect(0, 0, coreSize, coreSize);
    particles.forEach(p => {
        const dx = p.x - center, dy = p.y - center;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        // Circular boundary collision
        if (dist > (center - 5)) {
            p.vx *= -1; p.vy *= -1;
            p.x += p.vx * 2; p.y += p.vy * 2;
        }

        p.x += p.vx * particleSpeedMult;
        p.y += p.vy * particleSpeedMult;

        cCtx.beginPath();
        cCtx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        cCtx.fillStyle = `rgba(188, 19, 254, ${p.alpha})`; // Neon Purple
        cCtx.fill();
    });
    requestAnimationFrame(animateCore);
}
animateCore();

// --- 3. Telemetry & Charts (Jitter Graph) ---
const ctxChart = document.getElementById('jitterChart').getContext('2d');
const jitterData = Array(20).fill(0);
const jitterChart = new Chart(ctxChart, {
    type: 'line',
    data: {
        labels: Array(20).fill(''),
        datasets: [{
            label: 'Mouse Velocity',
            data: jitterData,
            borderColor: '#00ffff',
            borderWidth: 2,
            tension: 0.4,
            pointRadius: 0
        }]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { display: false }, y: { display: false, min: 0, max: 100 } }
    }
});

// Mouse Tracking for Jitter Graph
let lastMouse = { x: 0, y: 0 };
let currentVelocity = 0;
window.addEventListener('mousemove', (e) => {
    const dx = e.clientX - lastMouse.x;
    const dy = e.clientY - lastMouse.y;
    currentVelocity = Math.min(Math.sqrt(dx*dx + dy*dy), 100);
    lastMouse = { x: e.clientX, y: e.clientY };
});

setInterval(() => {
    jitterData.push(currentVelocity);
    jitterData.shift();
    jitterChart.update();
    currentVelocity *= 0.8; // Decay
}, 100);

// --- 4. Context Switch Histogram ---
const histContainer = document.getElementById('histogram');
let switchData = Array(10).fill(0).map(() => Math.random() * 80);

function renderHistogram() {
    histContainer.innerHTML = '';
    switchData.forEach(val => {
        const bar = document.createElement('div');
        bar.className = 'hist-bar';
        bar.style.height = `${val}%`;
        histContainer.appendChild(bar);
    });
}
setInterval(() => {
    switchData.push(Math.random() * 80 + 10);
    switchData.shift();
    renderHistogram();
}, 2000);
renderHistogram();

// --- 5. Burnout Engine (The Brain) ---
// Simulates B_p (Burnout Probability) shifting over time, affecting the UI state.
let bp = 0.24;
const ring = document.getElementById('aegis-ring');
const bpText = document.getElementById('bp-value');
const eyes = document.querySelectorAll('.eye');
const sysStatus = document.getElementById('system-status');

setInterval(() => {
    // Simulate gradual stress increase based on mouse jitter
    bp += (jitterData[19] > 50) ? 0.05 : -0.02;
    bp = Math.max(0.1, Math.min(bp, 0.99)); // Clamp between 0.1 and 0.99
    
    // UI State Machine based on Burnout Probability
    if (bp < 0.4) {
        // ZEN
        ring.style.borderColor = '#00ffff';
        ring.style.boxShadow = '0 0 40px #00ffff, inset 0 0 40px #00ffff';
        bpText.innerText = `${bp.toFixed(2)} (ZEN)`;
        bpText.className = 'text-cyan';
        sysStatus.innerText = 'STABLE'; sysStatus.className = 'text-cyan';
        eyes.forEach(eye => { eye.style.backgroundColor = '#00ffff'; eye.style.height = '8px'; });
        particleSpeedMult = 1;
    } else if (bp < 0.7) {
        // ELEVATED
        ring.style.borderColor = '#f3ec19';
        ring.style.boxShadow = '0 0 40px #f3ec19, inset 0 0 40px #f3ec19';
        bpText.innerText = `${bp.toFixed(2)} (ELEVATED)`;
        bpText.className = 'text-yellow';
        sysStatus.innerText = 'WARNING'; sysStatus.className = 'text-yellow';
        eyes.forEach(eye => { eye.style.backgroundColor = '#f3ec19'; eye.style.height = '20px'; }); // Wide eyes
        particleSpeedMult = 3;
    } else {
        // CRITICAL
        ring.style.borderColor = '#ff003c';
        ring.style.boxShadow = '0 0 40px #ff003c, inset 0 0 40px #ff003c';
        bpText.innerText = `${bp.toFixed(2)} (CRITICAL)`;
        bpText.className = 'text-red';
        sysStatus.innerText = 'CRITICAL'; sysStatus.className = 'text-red';
        eyes.forEach(eye => { eye.style.backgroundColor = '#ff003c'; eye.style.height = '4px'; }); // Squinting
        particleSpeedMult = 8; // Frenetic particles
    }
}, 1000);

// --- 6. Flow Lock Protocol ---
document.getElementById('flow-toggle').addEventListener('change', (e) => {
    const label = document.getElementById('lock-label');
    if (e.target.checked) {
        label.innerText = 'LOCKDOWN ACTIVE';
        label.className = 'lock-status text-purple';
        label.style.color = 'var(--neon-purple)';
        // Hackathon trick: dim the panels when focused
        document.querySelectorAll('.panel').forEach(p => p.style.opacity = '0.4');
    } else {
        label.innerText = 'STANDBY';
        label.style.color = 'var(--neon-cyan)';
        document.querySelectorAll('.panel').forEach(p => p.style.opacity = '1');
    }
});