<script lang="ts">
  import MapCanvas from '$lib/components/MapCanvas.svelte';
  import Sidebar from '$lib/components/Sidebar.svelte';

  // --- 1. IMPORTE ALLER TEST-DATEN ---

  // Level 0
  import level0 from '$lib/data/test/level0.json';

  // Level 1 (Kategorien)
  import l1_cat0 from '$lib/data/test/level1_cat0.json';
  import l1_cat1 from '$lib/data/test/level1_cat1.json';
  import l1_cat2 from '$lib/data/test/level1_cat2.json';
  import l1_cat3 from '$lib/data/test/level1_cat3.json';
  import l1_cat4 from '$lib/data/test/level1_cat4.json';

  // Level 2 (Subkategorien -> Paper Punkte)
  // Category 0
  import l2_cat0_sub0 from '$lib/data/test/level2_cat0.sub0.json';
  import l2_cat0_sub1 from '$lib/data/test/level2_cat0.sub1.json';
  import l2_cat0_sub2 from '$lib/data/test/level2_cat0.sub2.json';
  // Category 1
  import l2_cat1_sub0 from '$lib/data/test/level2_cat1.sub0.json';
  import l2_cat1_sub1 from '$lib/data/test/level2_cat1.sub1.json';
  import l2_cat1_sub2 from '$lib/data/test/level2_cat1.sub2.json';
  // Category 2
  import l2_cat2_sub0 from '$lib/data/test/level2_cat2.sub0.json';
  import l2_cat2_sub1 from '$lib/data/test/level2_cat2.sub1.json';
  import l2_cat2_sub2 from '$lib/data/test/level2_cat2.sub2.json';
  // Category 3
  import l2_cat3_sub0 from '$lib/data/test/level2_cat3.sub0.json';
  import l2_cat3_sub1 from '$lib/data/test/level2_cat3.sub1.json';
  import l2_cat3_sub2 from '$lib/data/test/level2_cat3.sub2.json';
  // Category 4
  import l2_cat4_sub0 from '$lib/data/test/level2_cat4.sub0.json';
  import l2_cat4_sub1 from '$lib/data/test/level2_cat4.sub1.json';
  import l2_cat4_sub2 from '$lib/data/test/level2_cat4.sub2.json';

  // --- 2. DATA MAPPING (Lookup Tables) ---

  // Map: Welche ID in Level 0 führt zu welcher Level 1 Datei?
  const level1Map: Record<string, any> = {
    "cat0": l1_cat0,
    "cat1": l1_cat1,
    "cat2": l1_cat2,
    "cat3": l1_cat3,
    "cat4": l1_cat4
  };

  // Map: Welche ID in Level 1 führt zu welcher Level 2 Datei?
  const level2Map: Record<string, any> = {
    // Cat 0
    "cat0.sub0": l2_cat0_sub0,
    "cat0.sub1": l2_cat0_sub1,
    "cat0.sub2": l2_cat0_sub2,
    // Cat 1
    "cat1.sub0": l2_cat1_sub0,
    "cat1.sub1": l2_cat1_sub1,
    "cat1.sub2": l2_cat1_sub2,
    // Cat 2
    "cat2.sub0": l2_cat2_sub0,
    "cat2.sub1": l2_cat2_sub1,
    "cat2.sub2": l2_cat2_sub2,
    // Cat 3
    "cat3.sub0": l2_cat3_sub0,
    "cat3.sub1": l2_cat3_sub1,
    "cat3.sub2": l2_cat3_sub2,
    // Cat 4
    "cat4.sub0": l2_cat4_sub0,
    "cat4.sub1": l2_cat4_sub1,
    "cat4.sub2": l2_cat4_sub2
  };

  // --- 3. STATE MANAGEMENT ---

  let currentLevel = 0;
  let selectedPaper: any = null;


  // Start mit Level 0
  let activeData: any = level0;

  // Speichert die Historie, um korrekt zurück zu navigieren
  let history: any[] = [];

  function handleDrillDown(event: CustomEvent) {
    const id = event.detail.id; // Die ID des angeklickten Elements (z.B. "cat0" oder "cat0.sub2")
    console.log("Drilldown angefordert für ID:", id);

    if (currentLevel === 0) {
      // Suche die passende Level 1 Datei in der Map
      const nextData = level1Map[id];
      if (nextData) {
        history.push({ level: 0, data: activeData }); // Aktuellen Stand speichern
        activeData = nextData;
        currentLevel = 1;
        selectedPaper = null;
      } else {
        console.warn("Keine Daten gefunden für Level 1 ID:", id);
      }
    }
    else if (currentLevel === 1) {
      // Suche die passende Level 2 Datei in der Map
      const nextData = level2Map[id];
      if (nextData) {
        history.push({ level: 1, data: activeData }); // Aktuellen Stand speichern
        activeData = nextData; // Das ist direkt das Array der Papers
        currentLevel = 2;
        selectedPaper = null;
      } else {
        console.warn("Keine Daten gefunden für Level 2 ID:", id);
      }
    }
  }

  function handleBack() {
    if (history.length > 0) {
      const lastState = history.pop();
      activeData = lastState.data;
      currentLevel = lastState.level;
      selectedPaper = null;
      // Array-Reassign triggert Svelte Reactivity
      history = history;
    }
  }
</script>

<div class="layout">
    <div class="map-container">
        <MapCanvas
            data={activeData}
            level={currentLevel}
            bind:selectedPaper
            on:drilldown={handleDrillDown}
        />
    </div>

    <Sidebar
        selectedPaper={selectedPaper}
        currentLevel={currentLevel}
        onBack={handleBack}
    />
</div>

<style>
  /* Stellt sicher, dass die App den ganzen Bildschirm nutzt */
  :global(body), :global(html) {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
  }

  .layout {
    display: flex;
    height: 100vh; /* WICHTIG: Volle Viewport Height */
    width: 100vw;
    overflow: hidden;
  }

  .map-container {
    flex-grow: 1;
    position: relative;
    background: #ccc; /* Falls Canvas fehlt, sehen wir grau */
    overflow: hidden; /* Verhindert Scrollbars */
  }
</style>