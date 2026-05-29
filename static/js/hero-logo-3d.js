const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const lerp = (start, end, progress) => start + (end - start) * progress;
const smoothStep = (value) => value * value * (3 - 2 * value);

function getStaticBase(modelUrl) {
  const marker = "/models/";
  return modelUrl?.includes(marker) ? modelUrl.slice(0, modelUrl.indexOf(marker)) : "/static";
}

async function loadThreeRuntime(modelUrl) {
  const staticBase = getStaticBase(modelUrl);
  const [threeModule, loaderModule, dracoModule] = await Promise.all([
    import(`${staticBase}/vendor/three/three.module.min.js`),
    import(`${staticBase}/vendor/three/GLTFLoader.js`),
    import(`${staticBase}/vendor/three/DRACOLoader.js`),
  ]);

  return {
    THREE: threeModule,
    GLTFLoader: loaderModule.GLTFLoader,
    DRACOLoader: dracoModule.DRACOLoader,
    staticBase,
  };
}

function initHeroLogo3D() {
  const container = document.querySelector("#hero-3d-container");
  const hero = container?.closest(".hero-section");
  const scrollSection = container?.closest(".hero-scroll-3d") || hero;
  const heroPanel = hero?.querySelector(".hero-main");

  if (!container?.dataset.modelUrl || !hero || !scrollSection || !heroPanel) {
    return;
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const mobileViewport = window.matchMedia("(max-width: 680px)");

  if (mobileViewport.matches) {
    container.removeAttribute("data-model-url");
    container.classList.add("is-mobile-fallback");
    container.dataset.hero3dStatus = "mobile-fallback";
    return;
  }

  let THREE;
  let GLTFLoader;
  let DRACOLoader;
  let staticBase = "/static";
  let renderer;
  let scene;
  let camera;
  let logoRoot;
  let logoWheel;
  let keyLight;
  let greenLight;
  let cyanLight;
  let resizeObserver;
  let frameId = 0;
  let isStarted = false;
  let isLoaded = false;
  let targetProgress = reducedMotion.matches ? 1 : 0;
  let progress = targetProgress;
  let lastTime = 0;
  const logoMaterials = [];

  function createRenderer() {
    const canvas = document.createElement("canvas");
    canvas.className = "hero-logo-3d-canvas";
    canvas.setAttribute("aria-hidden", "true");
    container.appendChild(canvas);

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(34, 1, 0.01, 1000);
    camera.position.set(0, 0, 8.6);

    renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });

    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;

    const ambient = new THREE.HemisphereLight(0xf2ffd7, 0x020704, 1.18);
    keyLight = new THREE.DirectionalLight(0xffffff, 2.2);
    keyLight.position.set(3.4, 4.2, 5.6);
    greenLight = new THREE.DirectionalLight(0xb7ff4f, 2.65);
    greenLight.position.set(-4.4, 2.4, 4.8);
    cyanLight = new THREE.PointLight(0x78ffe3, 0.9, 10);
    cyanLight.position.set(-3.2, -0.1, 3.6);

    scene.add(ambient, keyLight, greenLight, cyanLight);
  }

  function handleResize() {
    if (!renderer || !camera) {
      return;
    }

    const rect = container.getBoundingClientRect();
    const width = Math.max(1, Math.floor(rect.width));
    const height = Math.max(1, Math.floor(rect.height));

    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  function normalizeModel(model) {
    const bounds = new THREE.Box3().setFromObject(model);
    const center = bounds.getCenter(new THREE.Vector3());
    const size = bounds.getSize(new THREE.Vector3());
    const maxAxis = Math.max(size.x, size.y, size.z) || 1;
    const normalizationScale = 1 / maxAxis;

    // Center after scaling: Object3D applies scale before position, so the pivot remains the logo center.
    model.scale.multiplyScalar(normalizationScale);
    model.position.set(
      -center.x * normalizationScale,
      -center.y * normalizationScale,
      -center.z * normalizationScale,
    );

    model.traverse((child) => {
      if (!child.isMesh || !child.material) {
        return;
      }

      child.castShadow = false;
      child.receiveShadow = false;
      child.material.transparent = true;
      child.material.opacity = 0.28;
      child.material.envMapIntensity = 1.35;

      if ("emissive" in child.material) {
        child.material.emissive = new THREE.Color(0x315f00);
        child.material.emissiveIntensity = 0.14;
      }

      child.material.needsUpdate = true;
      logoMaterials.push(child.material);
    });
  }

  function loadLogo() {
    if (isLoaded) {
      return;
    }

    isLoaded = true;
    container.classList.add("is-loading");
    container.dataset.hero3dStatus = "loading-model";

    const dracoLoader = new DRACOLoader();
    dracoLoader.setDecoderPath(`${staticBase}/vendor/draco/`);
    dracoLoader.setDecoderConfig({ type: "wasm" });

    const loader = new GLTFLoader();
    loader.setDRACOLoader(dracoLoader);
    loader.load(
      container.dataset.modelUrl,
      (gltf) => {
        logoRoot = new THREE.Group();
        logoWheel = new THREE.Group();
        normalizeModel(gltf.scene);
        logoWheel.add(gltf.scene);
        logoRoot.add(logoWheel);
        scene.add(logoRoot);

        container.classList.remove("is-loading");
        container.classList.add("is-loaded");
        container.dataset.hero3dStatus = "loaded";
        dracoLoader.dispose();
      },
      undefined,
      (error) => {
        container.classList.remove("is-loading");
        container.classList.add("is-load-error");
        container.dataset.hero3dStatus = "load-error";
        container.dataset.hero3dError = error?.message || "model-load-error";
        dracoLoader.dispose();
      },
    );
  }

  function screenPointToWorld(point, z) {
    const rect = container.getBoundingClientRect();
    const xRatio = (point.x - rect.left) / Math.max(1, rect.width);
    const yRatio = (point.y - rect.top) / Math.max(1, rect.height);
    const distance = Math.max(0.1, camera.position.z - z);
    const worldHeight = 2 * Math.tan((camera.fov * Math.PI) / 360) * distance;
    const worldWidth = worldHeight * camera.aspect;

    return {
      x: (xRatio - 0.5) * worldWidth,
      y: camera.position.y + (0.5 - yRatio) * worldHeight,
    };
  }

  function getMotionPoints() {
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 1;
    const panelRect = heroPanel.getBoundingClientRect();
    const logoDiameter = clamp(viewportHeight * 0.28, 180, 330);
    const safeLeftCenter = logoDiameter * 0.55 + 22;
    const desiredFinalX = panelRect.left - logoDiameter * 0.42;
    const maxLeftCenter = Math.max(safeLeftCenter, panelRect.left - 18);
    const finalCenterX = clamp(desiredFinalX, safeLeftCenter, maxLeftCenter);

    return {
      start: {
        x: panelRect.left + panelRect.width * 0.58,
        y: panelRect.top + panelRect.height * 0.52,
      },
      end: {
        x: finalCenterX,
        y: panelRect.top + panelRect.height * 0.86,
      },
    };
  }

  function getStickyTopOffset() {
    const rawTop = window.getComputedStyle(hero).top;
    const parsedTop = Number.parseFloat(rawTop);
    return Number.isFinite(parsedTop) ? parsedTop : 0;
  }

  function updateTargetProgress() {
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 1;
    const stickyTop = getStickyTopOffset();
    const scrollDistance = Math.max(1, scrollSection.offsetHeight - viewportHeight + stickyTop);
    const rect = scrollSection.getBoundingClientRect();
    targetProgress = reducedMotion.matches ? 1 : clamp((stickyTop - rect.top) / scrollDistance);
  }

  function applyMotion(time) {
    const eased = smoothStep(progress);
    const reveal = smoothStep(clamp((eased - 0.02) / 0.7));
    const settled = smoothStep(clamp((eased - 0.88) / 0.12));

    container.style.setProperty("--hero-3d-glow", String(lerp(0.08, 0.88, reveal)));
    container.style.setProperty("--hero-3d-shadow", String(lerp(0.06, 0.68, reveal)));

    if (!logoRoot || !logoWheel) {
      return;
    }

    const points = getMotionPoints();
    const z = lerp(-3.25, 0.64, eased);
    const scrollFollow = Math.sin(eased * Math.PI * 0.5) * Math.min(92, window.innerHeight * 0.09);
    const screenPoint = {
      x: lerp(points.start.x, points.end.x, eased),
      y: lerp(points.start.y, points.end.y, eased) + Math.sin(eased * Math.PI) * 18 + scrollFollow,
    };
    const worldPoint = screenPointToWorld(screenPoint, z);
    const containerRect = container.getBoundingClientRect();
    const glowX = ((screenPoint.x - containerRect.left) / Math.max(1, containerRect.width)) * 100;
    const glowY = ((screenPoint.y - containerRect.top) / Math.max(1, containerRect.height)) * 100;
    const floatY = Math.sin(time * 0.0016) * 0.028 * settled;
    const floatX = Math.sin(time * 0.0011) * 0.018 * settled;
    const rollTurns = 2;

    container.style.setProperty("--hero-3d-x", `${glowX}%`);
    container.style.setProperty("--hero-3d-y", `${glowY}%`);

    logoRoot.position.set(worldPoint.x + floatX, worldPoint.y + floatY, z);
    logoRoot.scale.setScalar(lerp(1.68, 2.58, eased));
    logoRoot.rotation.set(
      Math.sin(time * 0.0013) * 0.01 * settled,
      lerp(0, 0.72, eased),
      0,
    );

    logoWheel.rotation.set(0, 0, Math.PI * 2 * rollTurns * eased);

    const opacity = lerp(0.24, 1, reveal);
    logoMaterials.forEach((material) => {
      material.opacity = opacity;
      material.transparent = opacity < 0.995;
    });

    if (keyLight && greenLight && cyanLight) {
      keyLight.intensity = 1.9 + reveal * 0.36;
      greenLight.intensity = 2.2 + reveal * 0.82;
      cyanLight.intensity = 0.58 + reveal * 0.34;
    }
  }

  function animate(time = 0) {
    updateTargetProgress();
    const delta = lastTime ? Math.min(0.12, (time - lastTime) / 1000) : 0.016;
    lastTime = time;
    progress += (targetProgress - progress) * Math.min(1, delta * 4.5);

    applyMotion(time);
    renderer?.render(scene, camera);
    frameId = window.requestAnimationFrame(animate);
  }

  async function start() {
    if (isStarted) {
      return;
    }

    isStarted = true;
    container.dataset.hero3dStatus = "loading-runtime";
    container.classList.add("is-runtime-loading");

    try {
      ({ THREE, GLTFLoader, DRACOLoader, staticBase } = await loadThreeRuntime(container.dataset.modelUrl));
      createRenderer();
      handleResize();
      updateTargetProgress();
      container.dataset.hero3dStatus = "runtime-ready";
      loadLogo();
      frameId = window.requestAnimationFrame(animate);

      if ("ResizeObserver" in window) {
        resizeObserver = new ResizeObserver(() => {
          handleResize();
          updateTargetProgress();
        });
        resizeObserver.observe(container);
      }
    } catch (error) {
      container.classList.add("is-load-error");
      container.dataset.hero3dStatus = "runtime-error";
      container.dataset.hero3dError = error?.message || "runtime-error";
    } finally {
      container.classList.remove("is-runtime-loading");
    }
  }

  function isNearViewport() {
    const rect = scrollSection.getBoundingClientRect();
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 1;
    return rect.bottom >= -260 && rect.top <= viewportHeight + 260;
  }

  window.addEventListener("scroll", updateTargetProgress, { passive: true });
  window.addEventListener("resize", () => {
    handleResize();
    updateTargetProgress();
  }, { passive: true });

  if (isNearViewport()) {
    start();
  } else if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        start();
        observer.disconnect();
      }
    }, { rootMargin: "260px 0px" });

    observer.observe(scrollSection);
  } else {
    start();
  }

  window.addEventListener("pagehide", () => {
    window.cancelAnimationFrame(frameId);
    resizeObserver?.disconnect();
    renderer?.dispose();
  }, { once: true });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initHeroLogo3D, { once: true });
} else {
  initHeroLogo3D();
}
