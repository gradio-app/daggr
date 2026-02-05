<script lang="ts">
	import { onMount } from "svelte";

	interface Props {
		label: string;
		value: string | null;
	}

	let { label, value }: Props = $props();

	let filename = $derived(value ? value.split('/').pop() || 'model.glb' : '');

	let containerEl: HTMLDivElement;
	let canvas: HTMLCanvasElement;
	let viewer: any = $state(null);
	let loading = $state(false);
	let modelLoading = $state(false);
	let error = $state<string | null>(null);
	let currentModelUrl = $state<string | null>(null);
	let mounted = $state(false);
	let isFullscreen = $state(false);

	onMount(() => {
		mounted = true;

		return () => {
			mounted = false;
			if (viewer) {
				viewer.dispose();
				viewer = null;
			}
		};
	});

	$effect(() => {
		if (canvas) {
			const originalFocus = canvas.focus.bind(canvas);
			canvas.focus = (options?: FocusOptions) => {
				originalFocus({ ...options, preventScroll: true });
			};
		}
	});

	$effect(() => {
		if (!mounted || !canvas) return;
		
		if (value && !viewer && !loading) {
			initViewer();
		} else if (value && viewer && value !== currentModelUrl && !modelLoading) {
			loadModel(value);
		} else if (!value && viewer && currentModelUrl) {
			viewer.resetModel();
			currentModelUrl = null;
		}
	});

	async function initViewer() {
		if (loading || !canvas) return;
		loading = true;
		error = null;

		try {
			const BABYLON_VIEWER = await import("@babylonjs/viewer");
			
			if (!mounted) return;
			
			const createdViewer = await BABYLON_VIEWER.CreateViewerForCanvas(canvas, {
				clearColor: [0.1, 0.1, 0.1, 1],
				useRightHandedSystem: true,
				animationAutoPlay: true,
				cameraAutoOrbit: { enabled: false }
			});
			
			if (!mounted) {
				createdViewer.dispose();
				return;
			}
			
			viewer = createdViewer;
			loading = false;
			
			if (value) {
				await loadModel(value);
			}
		} catch (e) {
			if (!mounted) return;
			error = e instanceof Error ? e.message : 'Failed to initialize 3D viewer';
			console.error('Failed to initialize Babylon.js viewer:', e);
			loading = false;
		}
	}

	async function loadModel(url: string) {
		if (!viewer || modelLoading) return;
		
		modelLoading = true;
		error = null;
		
		try {
			if (currentModelUrl) {
				viewer.resetModel();
			}
			
			await viewer.loadModel(url, {
				pluginOptions: {
					obj: {
						importVertexColors: true
					}
				}
			});
			
			if (mounted) {
				currentModelUrl = url;
				viewer.resetCamera();
			}
		} catch (e) {
			if (!mounted) return;
			error = e instanceof Error ? e.message : 'Failed to load model';
			console.error('Failed to load 3D model:', e);
		} finally {
			if (mounted) {
				modelLoading = false;
			}
		}
	}

	function downloadModel() {
		if (!value) return;
		const link = document.createElement('a');
		link.href = value;
		link.download = filename;
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	}

	function resetCamera() {
		if (viewer) {
			viewer.resetCamera();
		}
	}
	
	function retry() {
		error = null;
		currentModelUrl = null;
		if (viewer) {
			loadModel(value!);
		} else {
			initViewer();
		}
	}

	function openFullscreen() {
		if (!containerEl) return;
		if (containerEl.requestFullscreen) {
			containerEl.requestFullscreen();
		} else if ((containerEl as any).webkitRequestFullscreen) {
			(containerEl as any).webkitRequestFullscreen();
		}
	}

	function handleFullscreenChange() {
		isFullscreen = !!document.fullscreenElement;
	}
</script>

<svelte:document onfullscreenchange={handleFullscreenChange} />

<div class="gr-model3d-wrap" class:fullscreen={isFullscreen} bind:this={containerEl}>
	<div class="gr-header">
		<span class="gr-label">{label}</span>
		{#if value}
			<div class="header-actions">
				<button class="action-btn" onclick={resetCamera} title="Reset camera">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
						<path d="M3 3v5h5"/>
					</svg>
				</button>
				<button class="action-btn" onclick={openFullscreen} title="View fullscreen">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
					</svg>
				</button>
				<button class="action-btn" onclick={downloadModel} title="Download">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
						<polyline points="7 10 12 15 17 10"/>
						<line x1="12" y1="15" x2="12" y2="3"/>
					</svg>
				</button>
			</div>
		{/if}
	</div>

	{#if value}
		<div class="canvas-container">
			{#if loading || modelLoading}
				<div class="loading-overlay">
					<div class="spinner"></div>
					<span>{loading ? 'Loading 3D viewer...' : 'Loading model...'}</span>
				</div>
			{/if}
			{#if error && !loading && !modelLoading}
				<div class="error-overlay">
					<span class="error-icon">⚠️</span>
					<span class="error-text">{error}</span>
					<button class="retry-btn" onclick={retry}>Retry</button>
				</div>
			{/if}
			<canvas bind:this={canvas} tabindex="-1"></canvas>
		</div>
		<div class="model-footer">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="model-icon">
				<path d="M12 2L2 7l10 5 10-5-10-5z"/>
				<path d="M2 17l10 5 10-5"/>
				<path d="M2 12l10 5 10-5"/>
			</svg>
			<span class="model-name">{filename}</span>
		</div>
	{:else}
		<div class="gr-empty">No model</div>
	{/if}
</div>

<style>
	.gr-model3d-wrap {
		background: var(--block-background-fill);
		border: 1px solid var(--border-color-primary);
		border-radius: 6px;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.gr-model3d-wrap.fullscreen {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		width: 100vw;
		height: 100vh;
		z-index: 9999;
		border-radius: 0;
	}

	.gr-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 10px;
		border-bottom: 1px solid var(--border-color-primary);
	}

	.gr-model3d-wrap.fullscreen .gr-header {
		padding: 12px 20px;
	}

	.gr-label {
		font-size: 10px;
		font-weight: 400;
		color: var(--body-text-color-subdued);
	}

	.gr-model3d-wrap.fullscreen .gr-label {
		font-size: 14px;
	}

	.header-actions {
		display: flex;
		gap: 4px;
	}

	.gr-model3d-wrap.fullscreen .header-actions {
		gap: 8px;
	}

	.action-btn {
		width: 20px;
		height: 20px;
		padding: 3px;
		border: none;
		background: color-mix(in srgb, var(--body-text-color) 8%, transparent);
		border-radius: 4px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.15s;
	}

	.gr-model3d-wrap.fullscreen .action-btn {
		width: 32px;
		height: 32px;
		padding: 6px;
	}

	.action-btn svg {
		width: 12px;
		height: 12px;
		color: var(--body-text-color-subdued);
	}

	.gr-model3d-wrap.fullscreen .action-btn svg {
		width: 18px;
		height: 18px;
	}

	.action-btn:hover {
		background: color-mix(in srgb, var(--color-accent) 30%, transparent);
	}

	.action-btn:hover svg {
		color: var(--color-accent);
	}

	.canvas-container {
		position: relative;
		width: 100%;
		height: 200px;
		background: var(--body-background-fill);
	}

	.gr-model3d-wrap.fullscreen .canvas-container {
		flex: 1;
		height: auto;
	}

	.canvas-container canvas {
		width: 100%;
		height: 100%;
		display: block;
		outline: none;
	}

	.canvas-container canvas:focus {
		outline: none;
	}

	.loading-overlay,
	.error-overlay {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 10px;
		background: color-mix(in srgb, var(--body-background-fill) 90%, transparent);
		color: var(--body-text-color-subdued);
		font-size: 11px;
		z-index: 10;
	}

	.gr-model3d-wrap.fullscreen .loading-overlay,
	.gr-model3d-wrap.fullscreen .error-overlay {
		font-size: 16px;
		gap: 16px;
	}

	.spinner {
		width: 24px;
		height: 24px;
		border: 2px solid var(--border-color-primary);
		border-top-color: var(--color-accent);
		border-radius: 50%;
		animation: spin 1s linear infinite;
	}

	.gr-model3d-wrap.fullscreen .spinner {
		width: 40px;
		height: 40px;
		border-width: 3px;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.error-icon {
		font-size: 20px;
	}

	.gr-model3d-wrap.fullscreen .error-icon {
		font-size: 32px;
	}

	.error-text {
		color: var(--error-text-color);
		text-align: center;
		padding: 0 10px;
	}

	.retry-btn {
		margin-top: 5px;
		padding: 4px 12px;
		border: 1px solid var(--color-accent);
		background: transparent;
		color: var(--color-accent);
		border-radius: 4px;
		font-size: 10px;
		cursor: pointer;
		transition: background 0.15s;
	}

	.gr-model3d-wrap.fullscreen .retry-btn {
		padding: 8px 20px;
		font-size: 14px;
	}

	.retry-btn:hover {
		background: color-mix(in srgb, var(--color-accent) 20%, transparent);
	}

	.model-footer {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 10px;
		background: var(--input-background-fill);
	}

	.gr-model3d-wrap.fullscreen .model-footer {
		padding: 12px 20px;
	}

	.model-icon {
		width: 18px;
		height: 18px;
		color: var(--color-accent);
		flex-shrink: 0;
	}

	.gr-model3d-wrap.fullscreen .model-icon {
		width: 24px;
		height: 24px;
	}

	.model-name {
		font-size: 10px;
		color: var(--body-text-color-subdued);
		word-break: break-all;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.gr-model3d-wrap.fullscreen .model-name {
		font-size: 14px;
	}

	.gr-empty {
		font-size: 11px;
		color: var(--input-placeholder-color);
		font-style: italic;
		padding: 20px;
		text-align: center;
	}
</style>
