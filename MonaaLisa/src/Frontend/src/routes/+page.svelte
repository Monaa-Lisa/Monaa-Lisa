<script lang="ts">
  import { onMount } from 'svelte';
  import GraphLayout from '../components/GraphLayout.svelte';
  import LandingPage from '../components/LandingPage.svelte';
  import LoadingScreen from '../components/LoadingScreen.svelte';
  import { fade } from 'svelte/transition';

  let loading = true;
  let showLanding = true;
  let landingPage: LandingPage;

  onMount(() => {
    //check da cookie
    if (document.cookie.split('; ').some(row => row === 'hasVisited=true')) {
      showLanding = false;
    }

    setTimeout(() => {
      loading = false;
    }, 2000);
  });

  function handleStart() {
    //session cookie that keeps the user on the main app after they click start even if they close the tab
    //deleted when browser is closed and it will show landing page again next time
    document.cookie = "hasVisited=true; path=/; SameSite=Lax";
    showLanding = false;
  }

  function handleReset() {
    if (showLanding && landingPage) {
      landingPage.reset();
    } else {
      // Delete the cookie
      document.cookie = "hasVisited=; path=/; max-age=0";
      showLanding = true;
      if (typeof window !== 'undefined') {
        window.scrollTo({ top: 0, behavior: 'instant' });
      }
    }
  }
</script>

{#if loading}
  <LoadingScreen />
{/if}

{#if !showLanding}
  <main in:fade={{ duration: 300 }}>
    <GraphLayout />
  </main>
{:else}
  <div class="landing-wrapper" out:fade={{ duration: 300 }}>
    {#if !loading}
      <button class="logo-btn" on:click={handleReset} transition:fade>M-L</button>
    {/if}
    <LandingPage bind:this={landingPage} on:start={handleStart} />
  </div>
{/if}

<style>
  :global(body) {
    margin: 0;
    padding: 0;
    background: #000;
    color: #fff;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
    overflow-x: hidden;
  }

  main {
    width: 100vw;
    height: 100vh;
    position: fixed;
    top: 0;
    left: 0;
  }

  .logo-btn {
    position: fixed;
    top: 40px;
    left: 40px;
    z-index: 10000;
    font-size: 24px;
    font-weight: bold;
    letter-spacing: 2px;
    border: 2px solid #fff;
    padding: 5px 10px;
    background: transparent;
    color: #fff;
    cursor: pointer;
    transition: all 0.3s ease;
    font-family: inherit;
  }

  .logo-btn:hover {
    background: #fff;
    color: #000;
  }

  @media (max-width: 768px) {
    .logo-btn {
      top: 20px;
      left: 20px;
    }
  }
</style>