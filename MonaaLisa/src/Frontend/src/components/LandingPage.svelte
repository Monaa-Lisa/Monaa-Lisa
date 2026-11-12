<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import { spring } from 'svelte/motion';
  import techlistImg from '../assets/techlist.png';
  import monaaLisaLogo from '../assets/monaa_lisa_logo.png';
  import mlbg from '../assets/mlbg.png';
  import webmVideo from '../assets/ML_LOOP_main.webm';
  import mp4Video from '../assets/ML_LOOP_fallback.mp4';

  const dispatch = createEventDispatcher();

  let scrollY = 0;
  let innerHeight = 1000;

  // aScroll progress: 0 to 2 (since scroll track is 900vh)
  $: rawProgress = innerHeight ? scrollY / (innerHeight * 4) : 0;

  const smoothProgress = spring(0, {
    stiffness: 0.02,
    damping: 0.9
  });

  $: smoothProgress.set(rawProgress);

  $: progress = $smoothProgress;

  // 1. Hero Section
  $: heroOpacity = Math.max(0, 1 - progress * 10);
  
  // 2. Background Image
  $: bgScale = 1.2 - (progress * 0.2);
  
  // 3. Transition Title "Monaa-Lisa"
  // We want an exponential zoom for linear visual speed.
  // Range: progress 0.1 to 0.4
  const zoomStart = 0.1;
  const zoomEnd = 0.4;
  $: zoomT = Math.min(1, Math.max(0, (progress - zoomStart) / (zoomEnd - zoomStart)));
  
  // Scale: 3000 -> 1 exponentially
  $: titleScale = 3000 * Math.pow(1 / 3000, zoomT);
  
  // OPTIMIZATION: Use SVG transform instead of CSS transform on HTML elements
  // This prevents the browser from creating a massive texture layer while avoiding Chrome viewBox bugs.
  
  // ADJUSTMENT: Center point for the zoom (0-100)
  // We keep the camera centered in the middle of our viewport (50x25)
  // And instead, moving the TEXT below to align the letter with this center.
  const focusX = 50; 
  const focusY = 25;

  // Title X Position: 
  // 50 = Center
  // 49.2 = Move Text slightly Left (so camera hits the letter to the Right of the gap)
  // Logic: 
  // If at 50 it hits the gap between "aa", the second 'a' is to the right.
  // We move the text LEFT (smaller X) to bring that 'a' into the center camera view.
  const titleX = 49.2; 
  
  // Opacity: Starts transparent (0), fades to white (1)
  // User wants it faster/earlier.
  // Start fading in slightly before the zoom finishes (at 0.35) and finish by 0.4
  $: titleOpacity = Math.min(1, Math.max(0, (progress - 0.35) * 20));

  // 4. Subtitle
  $: subtitleOpacity = Math.min(1, Math.max(0, (progress - 0.4) * 10));

  // Move title up
  $: titleY = 50 - (subtitleOpacity * 20);
  
  // Convert percentage-based Y to absolute World Unit Y (World Height is 50)
  $: titleYAbs = titleY * 0.5;

  // 5. Utilizing Caption
  $: utilizingOpacity = Math.min(1, Math.max(0, (progress - 0.6) * 10));

  // 6. Arxiv Logo
  $: arxivOpacity = Math.min(1, Math.max(0, (progress - 0.8) * 10));

  // 7. Fade out previous section
  $: previousSectionOpacity = Math.max(0, 1 - (progress - 1.0) * 5);

  // 7b. New section fades in as previous fades out
  $: newSectionOpacity = Math.min(1, Math.max(0, 1 - previousSectionOpacity));

  // 8. New Section Animations
  // Node 1 forms in the middle (scale 0 to 1)
  $: node1Scale = Math.min(1, Math.max(0, (progress - 1.2) * 10));
  
  // Node 1 moves to the left (X translation)
  // Starts at 0, moves to -15vw
  $: node1X = Math.min(1, Math.max(0, (progress - 1.3) * 10)) * -15;
  
  // Text 1 "Search a Paper" appears
  $: text1Opacity = Math.min(1, Math.max(0, (progress - 1.35) * 10));

  // Edge 1 forms (height 0 to 130px)
  $: edge1Height = Math.min(1, Math.max(0, (progress - 1.4) * 10)) * 130;

  // Node 2 forms and text "Find its References and Citations" appears
  $: node2Opacity = Math.min(1, Math.max(0, (progress - 1.5) * 10));

  // Edge 2 forms (height 0 to 130px)
  $: edge2Height = Math.min(1, Math.max(0, (progress - 1.6) * 10)) * 130;

  // Node 3 forms and text "Find thematically similar paper" appears
  $: node3Opacity = Math.min(1, Math.max(0, (progress - 1.7) * 10));

  // Edge 3 forms (height 0 to 130px)
  $: edge3Height = Math.min(1, Math.max(0, (progress - 1.8) * 10)) * 130;

  // Big text appears
  $: finalProjectOpacity = Math.min(1, Math.max(0, (progress - 1.9) * 10));

  // ── Canvas: cross-browser zoom-through-text (replaces SVG mask) ──
  let canvasEl: HTMLCanvasElement;

  function drawCanvas() {
    if (!canvasEl || typeof window === 'undefined') return;
    const ctx = canvasEl.getContext('2d');
    if (!ctx) return;
    const W = canvasEl.width;
    const H = canvasEl.height;

    ctx.clearRect(0, 0, W, H);

    // Replicate SVG viewBox "0 0 100 50" with preserveAspectRatio="xMidYMid slice"
    const svgScale = Math.max(W / 100, H / 50);
    const svgOffX = (W - 100 * svgScale) / 2;
    const svgOffY = (H - 50 * svgScale) / 2;

    // Focus point (viewport centre) and text anchor in canvas pixels
    const fpx = svgOffX + focusX * svgScale;
    const fpy = svgOffY + focusY * svgScale;
    const textPx = svgOffX + titleX * svgScale;
    const textPy = svgOffY + titleYAbs * svgScale;

    const fontSizePx = 12 * svgScale;
    const fontDef = `900 ${fontSizePx}px Arial, sans-serif`;

    // 1. Dark overlay
    ctx.fillStyle = '#1a1f2c';
    ctx.fillRect(0, 0, W, H);

    // 2. Cut text-shaped hole via destination-out
    ctx.save();
    ctx.translate(fpx, fpy);
    ctx.scale(titleScale, titleScale);
    ctx.translate(-fpx, -fpy);
    ctx.font = fontDef;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.globalCompositeOperation = 'destination-out';
    ctx.fillStyle = 'rgba(0,0,0,1)';
    ctx.fillText('MONAA-LISA', textPx, textPy);
    ctx.restore();

    // 3. White text fill that fades in as zoom completes
    if (titleOpacity > 0) {
      ctx.save();
      ctx.globalAlpha = titleOpacity;
      ctx.translate(fpx, fpy);
      ctx.scale(titleScale, titleScale);
      ctx.translate(-fpx, -fpy);
      ctx.font = fontDef;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = 'white';
      ctx.fillText('MONAA-LISA', textPx, textPy);
      ctx.restore();
    }
  }

  function resizeCanvas() {
    if (!canvasEl || typeof window === 'undefined') return;
    const dpr = window.devicePixelRatio || 1;
    canvasEl.width = window.innerWidth * dpr;
    canvasEl.height = window.innerHeight * dpr;
    canvasEl.style.width = window.innerWidth + 'px';
    canvasEl.style.height = window.innerHeight + 'px';
    drawCanvas();
  }

  onMount(() => {
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    return () => window.removeEventListener('resize', resizeCanvas);
  });

  // Redraw whenever animated values change
  $: titleScale, titleOpacity, titleYAbs, canvasEl, drawCanvas();

  export function reset() {
    window.scrollTo({ top: 0, behavior: 'instant' });
    smoothProgress.set(0, { hard: true });
  }

  function start() {
    dispatch('start');
  }
</script>

<svelte:window bind:scrollY bind:innerHeight />

<div class="landing-page">
  <div class="sticky-wrapper">
      <!-- Background Image Layer -->
      <div class="background" style="transform: scale({bgScale})">
           <video
             class="art-placeholder"
             autoplay
             loop
             muted
             playsinline
             poster={mlbg}
           >
             <source src={webmVideo} type="video/webm" />
             <source src={mp4Video} type="video/mp4" />
           </video>
      </div>

      <!-- Logo Layer -->
      <div class="logo-layer" style="transform: scale({bgScale})">
          <img src={monaaLisaLogo} alt="Monaa-Lisa Logo" class="hero-logo" />
      </div>

      <!-- Hero Section (Title) -->
      <div class="hero-layer title-layer" style="opacity: {heroOpacity}; pointer-events: none">
          <h1 class="hero-title">Monaa-Lisa</h1>
      </div>

      <!-- Hero Section (Content) -->
      <div class="hero-layer content-layer" style="opacity: {heroOpacity}; pointer-events: {heroOpacity < 0.1 ? 'none' : 'auto'}">
          <!-- Spacer to push content down similar to where it would be if title was here -->
          <div class="title-spacer"></div>
          <div class="hero-content">
            <button class="start-btn" on:click={start}>START</button>
            <p class="hero-subtitle">Visualize academia interactively</p>
          </div>
      </div>

      <!-- Second Section: Canvas-based zoom-through-text — works identically on Chromium and Firefox -->
      <canvas bind:this={canvasEl} class="overlay-canvas"></canvas>
      
      <!-- Subtitle is separate, fades in at the end -->
      <div class="subtitle-container" style="opacity: {subtitleOpacity * previousSectionOpacity}">
          <h2 class="sub-title">A tool to visualize academic papers, their relations and citations</h2>
      </div>

      <div class="utilizing-container" style="opacity: {utilizingOpacity * previousSectionOpacity}">
          <h2 class="sub-title">utilizing</h2>
      </div>

      <div class="techlist-container" style="opacity: {arxivOpacity * previousSectionOpacity}; pointer-events: {arxivOpacity > 0.1 ? 'auto' : 'none'}">
          <div class="techlist-gradient left"></div>
          <div class="techlist-scroll">
              <img src={techlistImg} alt="Tech List" class="techlist-img" />
              <img src={techlistImg} alt="Tech List" class="techlist-img" />
              <img src={techlistImg} alt="Tech List" class="techlist-img" />
              <img src={techlistImg} alt="Tech List" class="techlist-img" />
          </div>
          <div class="techlist-gradient right"></div>
      </div>

      <!-- New Section: Program Explanation -->
      <div class="program-explanation-section" style="opacity: {newSectionOpacity}; pointer-events: {progress > 1.1 ? 'auto' : 'none'}">
          <div class="node-container">
              <div class="node-row">
                  <div class="node" style="transform: translateX({node1X}vw) scale({node1Scale})"></div>
                  <div class="node-text" style="opacity: {text1Opacity}; transform: translateX(calc({node1X}vw + 20px))">Search a Paper</div>
              </div>
              
              <div class="edge" style="height: {edge1Height}px; transform: translateX({node1X}vw)"></div>
              
              <div class="node-row" style="opacity: {node2Opacity}">
                  <div class="node" style="transform: translateX({node1X}vw)"></div>
                  <div class="node-text" style="transform: translateX(calc({node1X}vw + 20px))">Find its References and Citations</div>
              </div>
              
              <div class="edge" style="height: {edge2Height}px; transform: translateX({node1X}vw)"></div>
              
              <div class="node-row" style="opacity: {node3Opacity}">
                  <div class="node" style="transform: translateX({node1X}vw)"></div>
                  <div class="node-text" style="transform: translateX(calc({node1X}vw + 20px))">Find thematically similar paper</div>
              </div>
              
              <div class="edge" style="height: {edge3Height}px; transform: translateX({node1X}vw)"></div>
              
              <div class="final-project-text" style="opacity: {finalProjectOpacity}">
                <span class="final-prefix">A software project by</span>
                <span class="final-names">Nico Bestek, Bastian Rosinski, Lenio Cabral-Rosario, Nick Wittkowski</span>
              </div>
          </div>
      </div>
  </div>
  
  <!-- Scroll Track -->
  <div class="scroll-track"></div>
</div>

<style>
  .landing-page {
    position: relative;
    width: 100%;
    background: #000;
    color: #fff;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
    z-index: 9999;
  }

  .scroll-track {
    height: 900vh;
  }

  .sticky-wrapper {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100vh;
    overflow: hidden;
    display: flex;
    justify-content: center;
    align-items: center;
  }

  .background {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 0;
    will-change: transform;
  }

  .art-placeholder {
    width: 100%;
    height: 100%;
    object-fit: cover;
    filter: brightness(0.9) contrast(0.85);
  }

  .logo-layer {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 15; /* Middle Layer */
    pointer-events: none;
    display: flex;
    justify-content: center;
    align-items: flex-end;
  }

  .hero-layer {
    position: absolute;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    align-items: center;
    text-align: center;
    padding-top: 10vh;
  }

  .title-layer {
    z-index: 10; /* Bottom Layer */
  }

  .content-layer {
    z-index: 20; /* Top Layer */
  }

  .title-spacer {
    /* Approximate height of title + margin to push button down */
    height: calc(6rem + 2rem); 
    width: 1px;
  }

  .hero-logo {
    height: 92vh;
    width: auto;
    margin-bottom: 0;
    filter: drop-shadow(0 0 20px rgba(0,0,0,0.8));
  }

  .hero-title {
    font-size: 10rem;
    margin: 0;
    margin-bottom: 2rem;
    text-transform: uppercase;
    letter-spacing: 10px;
    font-weight: 900;
    text-shadow: 0 0 20px rgba(0,0,0,0.5);
  }

  .hero-content {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .start-btn {
    margin-top: 500px;
    padding: 15px 50px;
    font-size: 1.5rem;
    background: rgba(100, 100, 255, 0.15); /* Slight blue tint base */
    border: 2px solid #fff;
    color: #fff;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 2px;
    transition: all 0.3s ease;
    backdrop-filter: blur(10px);
    box-shadow: 0 0 20px rgba(138, 43, 226, 0.3), inset 0 0 20px rgba(0, 191, 255, 0.2); /* Purple glow + Blue inner glow */
  }

  .start-btn:hover {
    background: rgba(255, 255, 255, 0.9);
    color: #000;
    transform: scale(1.05);
    box-shadow: 0 0 30px rgba(138, 43, 226, 0.6), inset 0 0 20px rgba(0, 191, 255, 0.4);
  }

  .hero-subtitle {
    margin-top: 100px;
    font-size: 1.2rem;
    letter-spacing: 9px;
    text-transform: uppercase;
    opacity: 0.9;
    text-shadow: 0 2px 2px rgba(0,0,0,0.9);
  }

  .overlay-canvas {
    position: absolute;
    z-index: 20;
    top: 0;
    left: 0;
    pointer-events: none;
    /* width/height set dynamically via resizeCanvas() */
  }

  .subtitle-container {
    position: absolute;
    z-index: 30;
    top: 45%; /* Position below the title */
    width: 100%;
    text-align: center;
    pointer-events: none;
  }

  .utilizing-container {
    position: absolute;
    z-index: 30;
    top: 55%;
    width: 100%;
    text-align: center;
    pointer-events: none;
  }

  .techlist-container {
    position: absolute;
    z-index: 40;
    top: 65%;
    width: 100%;
    height: 150px;
    display: flex;
    align-items: center;
    overflow: hidden;
  }

  .techlist-scroll {
    display: flex;
    width: max-content;
    animation: scroll-left 90s linear infinite;
  }

  .techlist-img {
    height: 100px;
    object-fit: contain;
    filter: invert(0); /* Assuming techlist.png is black on transparent, like arxiv_logo.png */
  }

  @keyframes scroll-left {
    0% { transform: translateX(0); }
    100% { transform: translateX(-50%); }
  }

  .techlist-gradient {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 400px;
    z-index: 2;
    pointer-events: none;
  }

  .techlist-gradient.left {
    left: 0;
    background: linear-gradient(to right, #1a1f2c, transparent);
  }

  .techlist-gradient.right {
    right: 0;
    background: linear-gradient(to left, #1a1f2c, transparent);
  }

  .program-explanation-section {
    position: absolute;
    z-index: 50;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    background: #1a1f2c;
  }

  .node-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
  }

  .node-row {
    display: flex;
    align-items: center;
    position: relative;
    height: 56px;
  }

  .node {
    width: 28px;
    height: 28px;
    background-color: white;
    border-radius: 50%;
    box-shadow: 0 0 20px rgba(255, 255, 255, 0.85);
    position: absolute;
    left: -14px; /* Centre the node on the vertical axis */
  }

  .node-text {
    position: absolute;
    left: 0;
    white-space: nowrap;
    font-size: 1.9rem;
    font-weight: 300;
    letter-spacing: 3px;
    text-shadow: 0 0 12px rgba(0,0,0,0.8);
  }

  .edge {
    width: 2px;
    background-color: rgba(255, 255, 255, 0.5);
    margin: 10px 0;
    /* The edge should grow downwards, so we align it to the top */
    transform-origin: top center;
  }

  .final-project-text {
    margin-top: 48px;
    text-align: center;
    text-shadow: 0 0 24px rgba(255, 255, 255, 0.35);
  }

  .final-prefix {
    display: block;
    font-size: 3.2rem;
    font-weight: 700;
    letter-spacing: 6px;
    text-transform: uppercase;
    margin-bottom: 0.6rem;
  }

  .final-names {
    display: block;
    font-size: 2.2rem;
    font-weight: 600;
    letter-spacing: 3px;
    text-transform: uppercase;
    white-space: normal;
  }

  .sub-title {
    font-size: 2rem;
    font-weight: 300;
    letter-spacing: 5px;
    text-transform: uppercase;
    text-shadow: 0 0 10px rgba(0,0,0,0.8);
  }

  @media (max-width: 768px) {
    .hero-title {
      font-size: 4rem;
    }
    .hero-subtitle {
      bottom: 20px;
      font-size: 0.9rem;
    }
    .final-prefix {
      font-size: 2.2rem;
      letter-spacing: 3px;
    }
    .final-names {
      font-size: 1.6rem;
      letter-spacing: 1.5px;
    }
  }
</style>
