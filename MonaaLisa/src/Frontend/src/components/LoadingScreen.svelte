<script lang="ts">
  import { fade } from 'svelte/transition';
</script>

<div class="loading-screen" out:fade={{ duration: 800 }}>
  <div class="logo-container">
    <div class="loading-logo">M-L</div>
  </div>
</div>

<style>
  .loading-screen {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background-color: var(--bg-primary, #0F1020);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 10001;
  }

  .loading-logo {
    font-size: 48px;
    font-weight: bold;
    letter-spacing: 4px;
    border: 3px solid rgba(147, 51, 234, 0.5);
    padding: 10px 20px;
    background: linear-gradient(135deg, rgba(147,51,234,0.08), rgba(232,57,160,0.06));
    color: #fff;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    animation: glow 2s ease-in-out infinite;
  }

  @keyframes glow {
    0% {
      filter: drop-shadow(0 0 5px rgba(34, 211, 238, 0.6));
      border-color: rgba(34, 211, 238, 0.5);
    }
    50% {
      filter: drop-shadow(0 0 25px rgba(147, 51, 234, 0.9));
      border-color: rgba(147, 51, 234, 0.7);
    }
    100% {
      filter: drop-shadow(0 0 5px rgba(232, 57, 160, 0.6));
      border-color: rgba(232, 57, 160, 0.5);
    }
  }
</style>
