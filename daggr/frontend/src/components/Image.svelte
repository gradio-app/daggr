<script lang="ts">
	interface Props {
		label: string;
		value: any;
		editable?: boolean;
		onchange?: (value: any) => void;
	}

	let { label, value, editable = true, onchange }: Props = $props();

	let imgEl: HTMLImageElement | null = $state(null);
	let fileInputEl: HTMLInputElement | null = $state(null);
	let showWebcam = $state(false);
	let videoEl: HTMLVideoElement | null = $state(null);
	let stream: MediaStream | null = $state(null);

	let src = $derived.by(() => {
		if (!value) return null;
		if (typeof value === 'string') return value;
		if (value.url) return value.url;
		if (value instanceof Blob) return URL.createObjectURL(value);
		return null;
	});

	async function downloadImage() {
		if (!src) return;
		try {
			const response = await fetch(src);
			const blob = await response.blob();
			const blobUrl = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = blobUrl;
			const ext = blob.type.split('/')[1] || 'png';
			link.download = `${label || 'image'}.${ext}`;
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			URL.revokeObjectURL(blobUrl);
		} catch (e) {
			console.error('Failed to download image:', e);
		}
	}

	function openFullscreen() {
		if (!imgEl) return;
		if (imgEl.requestFullscreen) {
			imgEl.requestFullscreen();
		} else if ((imgEl as any).webkitRequestFullscreen) {
			(imgEl as any).webkitRequestFullscreen();
		} else if ((imgEl as any).msRequestFullscreen) {
			(imgEl as any).msRequestFullscreen();
		}
	}

	function triggerUpload() {
		fileInputEl?.click();
	}

	function handleFileSelect(e: Event) {
		const target = e.target as HTMLInputElement;
		const file = target.files?.[0];
		if (file) {
			onchange?.(file);
		}
		target.value = '';
	}

	async function startWebcam() {
		try {
			stream = await navigator.mediaDevices.getUserMedia({ video: true });
			showWebcam = true;
			await new Promise(resolve => setTimeout(resolve, 50));
			if (videoEl && stream) {
				videoEl.srcObject = stream;
				videoEl.play();
			}
		} catch (e) {
			console.error('Failed to access webcam:', e);
		}
	}

	function captureFromWebcam() {
		if (!videoEl) return;
		const canvas = document.createElement('canvas');
		canvas.width = videoEl.videoWidth;
		canvas.height = videoEl.videoHeight;
		const ctx = canvas.getContext('2d');
		if (ctx) {
			ctx.drawImage(videoEl, 0, 0);
			canvas.toBlob((blob) => {
				if (blob) {
					onchange?.(blob);
				}
				stopWebcam();
			}, 'image/png');
		}
	}

	function stopWebcam() {
		if (stream) {
			stream.getTracks().forEach(track => track.stop());
			stream = null;
		}
		showWebcam = false;
	}

	function clearImage() {
		onchange?.(null);
	}

	async function pasteFromClipboard() {
		try {
			const items = await navigator.clipboard.read();
			for (const item of items) {
				const imageType = item.types.find(type => type.startsWith('image/'));
				if (imageType) {
					const blob = await item.getType(imageType);
					onchange?.(blob);
					return;
				}
			}
		} catch (e) {
			console.error('Failed to paste from clipboard:', e);
		}
	}
</script>

<div class="gr-image-wrap">
	<input
		bind:this={fileInputEl}
		type="file"
		accept="image/*"
		style="display: none"
		onchange={handleFileSelect}
	/>
	
	<div class="gr-header">
		<span class="gr-label">{label}</span>
		<div class="image-actions">
			{#if showWebcam}
				<button class="action-btn capture" onclick={captureFromWebcam} title="Capture photo">
					<svg viewBox="0 0 24 24" fill="currentColor">
						<circle cx="12" cy="12" r="10"/>
					</svg>
				</button>
				<button class="action-btn" onclick={stopWebcam} title="Cancel">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<line x1="18" y1="6" x2="6" y2="18"/>
						<line x1="6" y1="6" x2="18" y2="18"/>
					</svg>
				</button>
			{:else if src}
				<button class="action-btn" onclick={openFullscreen} title="View fullscreen">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
					</svg>
				</button>
				<button class="action-btn" onclick={downloadImage} title="Download">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
						<polyline points="7 10 12 15 17 10"/>
						<line x1="12" y1="15" x2="12" y2="3"/>
					</svg>
				</button>
				<button class="action-btn" onclick={clearImage} title="Clear image">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<line x1="18" y1="6" x2="6" y2="18"/>
						<line x1="6" y1="6" x2="18" y2="18"/>
					</svg>
				</button>
			{:else if editable}
				<button class="action-btn" onclick={triggerUpload} title="Upload image">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
						<polyline points="17 8 12 3 7 8"/>
						<line x1="12" y1="3" x2="12" y2="15"/>
					</svg>
				</button>
				<button class="action-btn" onclick={pasteFromClipboard} title="Paste from clipboard">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
						<rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
					</svg>
				</button>
				<button class="action-btn" onclick={startWebcam} title="Capture from webcam">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
						<circle cx="12" cy="13" r="4"/>
					</svg>
				</button>
			{/if}
		</div>
	</div>
	
	{#if showWebcam}
		<div class="webcam-container">
			<video bind:this={videoEl} autoplay playsinline muted></video>
		</div>
	{:else if src}
		<div class="image-container">
			<img bind:this={imgEl} class="gr-image" {src} alt={label} />
		</div>
	{:else}
		<div class="gr-empty">No image</div>
	{/if}
</div>

<style>
	.gr-image-wrap {
		background: var(--block-background-fill);
		border: 1px solid var(--border-color-primary);
		border-radius: 6px;
		overflow: hidden;
	}

	.gr-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px;
	}

	.gr-label {
		font-size: 10px;
		font-weight: 400;
		color: var(--body-text-color-subdued);
		padding-left: 4px;
	}

	.image-actions {
		display: flex;
		gap: 4px;
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

	.action-btn svg {
		width: 12px;
		height: 12px;
		color: var(--body-text-color-subdued);
	}

	.action-btn:hover {
		background: color-mix(in srgb, var(--body-text-color) 15%, transparent);
	}

	.action-btn:hover svg {
		color: var(--body-text-color);
	}

	.action-btn.capture {
		background: var(--error-border-color);
	}

	.action-btn.capture svg {
		color: var(--button-primary-text-color);
	}

	.action-btn.capture:hover {
		background: var(--error-text-color);
	}

	.image-container {
		padding: 0 6px 6px;
	}

	.gr-image {
		width: 100%;
		max-height: 80px;
		object-fit: contain;
		display: block;
		border-radius: 4px;
	}

	.webcam-container {
		padding: 0 6px 6px;
	}

	.webcam-container video {
		width: 100%;
		max-height: 120px;
		object-fit: contain;
		border-radius: 4px;
		background: var(--body-background-fill);
	}

	.gr-empty {
		font-size: 11px;
		color: var(--input-placeholder-color);
		font-style: italic;
		padding: 6px;
		text-align: center;
	}
</style>
