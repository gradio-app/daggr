<script lang="ts">
	interface Props {
		label: string;
		value: any;
		editable?: boolean;
		autoplay?: boolean;
		loop?: boolean;
		onchange?: (value: any) => void;
	}

	let { label, value, editable = true, autoplay = false, loop = false, onchange }: Props = $props();

	let videoEl: HTMLVideoElement | null = $state(null);
	let previewVideoEl: HTMLVideoElement | null = $state(null);
	let fileInputEl: HTMLInputElement | null = $state(null);
	let isRecording = $state(false);
	let mediaRecorder: MediaRecorder | null = $state(null);
	let recordedChunks: Blob[] = $state([]);
	let stream: MediaStream | null = $state(null);

	$effect(() => {
		if (previewVideoEl && stream) {
			previewVideoEl.srcObject = stream;
		}
	});

	let src = $derived.by(() => {
		if (!value) return null;
		if (typeof value === 'string') return value;
		if (value.url) return value.url;
		if (value instanceof Blob) return URL.createObjectURL(value);
		return null;
	});

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

	async function startRecording() {
		try {
			stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
			mediaRecorder = new MediaRecorder(stream);
			recordedChunks = [];

			mediaRecorder.ondataavailable = (e) => {
				if (e.data.size > 0) {
					recordedChunks.push(e.data);
				}
			};

			mediaRecorder.onstop = () => {
				const blob = new Blob(recordedChunks, { type: 'video/webm' });
				onchange?.(blob);
				stopStream();
			};

			mediaRecorder.start();
			isRecording = true;
		} catch (e) {
			console.error('Failed to access camera:', e);
		}
	}

	function stopRecording() {
		if (mediaRecorder && mediaRecorder.state !== 'inactive') {
			mediaRecorder.stop();
		}
		isRecording = false;
	}

	function stopStream() {
		if (stream) {
			stream.getTracks().forEach(track => track.stop());
			stream = null;
		}
	}

	function clearVideo() {
		onchange?.(null);
	}

	async function downloadVideo() {
		if (!src) return;
		try {
			const response = await fetch(src);
			const blob = await response.blob();
			const blobUrl = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = blobUrl;
			const ext = blob.type.split('/')[1]?.split(';')[0] || 'webm';
			link.download = `${label || 'video'}.${ext}`;
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			URL.revokeObjectURL(blobUrl);
		} catch (e) {
			console.error('Failed to download video:', e);
		}
	}

	function openFullscreen() {
		if (videoEl) {
			if (videoEl.requestFullscreen) {
				videoEl.requestFullscreen();
			}
		}
	}
</script>

<div class="gr-video-wrap">
	<input
		bind:this={fileInputEl}
		type="file"
		accept="video/*"
		style="display: none"
		onchange={handleFileSelect}
	/>

	<div class="gr-header">
		<span class="gr-label">{label}</span>
		<div class="video-actions">
			{#if isRecording}
				<button class="action-btn recording" onclick={stopRecording} title="Stop recording">
					<svg viewBox="0 0 24 24" fill="currentColor">
						<rect x="6" y="6" width="12" height="12" rx="2"/>
					</svg>
				</button>
			{:else if src}
				<button class="action-btn" onclick={openFullscreen} title="Fullscreen">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
					</svg>
				</button>
				<button class="action-btn" onclick={downloadVideo} title="Download">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
						<polyline points="7 10 12 15 17 10"/>
						<line x1="12" y1="15" x2="12" y2="3"/>
					</svg>
				</button>
				<button class="action-btn" onclick={clearVideo} title="Clear">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<line x1="18" y1="6" x2="6" y2="18"/>
						<line x1="6" y1="6" x2="18" y2="18"/>
					</svg>
				</button>
			{:else if editable}
				<button class="action-btn" onclick={triggerUpload} title="Upload video">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
						<polyline points="17 8 12 3 7 8"/>
						<line x1="12" y1="3" x2="12" y2="15"/>
					</svg>
				</button>
				<button class="action-btn" onclick={startRecording} title="Record video">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<polygon points="23 7 16 12 23 17 23 7"/>
						<rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
					</svg>
				</button>
			{/if}
		</div>
	</div>

	{#if isRecording && stream}
		<div class="video-container recording-preview">
			<!-- svelte-ignore a11y_media_has_caption -->
			<video autoplay muted playsinline bind:this={previewVideoEl}></video>
			<div class="recording-indicator">
				<span class="rec-dot"></span>
				<span>REC</span>
			</div>
		</div>
	{:else if src}
		<div class="video-container">
			<!-- svelte-ignore a11y_media_has_caption -->
			<video
				bind:this={videoEl}
				{src}
				{autoplay}
				{loop}
				controls
				playsinline
			></video>
		</div>
	{:else}
		<div class="gr-empty">No video</div>
	{/if}
</div>

<style>
	.gr-video-wrap {
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

	.video-actions {
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

	.action-btn.recording {
		background: var(--error-border-color);
		animation: pulse-recording 1.5s ease-in-out infinite;
	}

	.action-btn.recording svg {
		color: var(--button-primary-text-color);
	}

	@keyframes pulse-recording {
		0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--error-border-color) 40%, transparent); }
		50% { box-shadow: 0 0 0 4px transparent; }
	}

	.video-container {
		padding: 0 6px 6px;
		position: relative;
	}

	.video-container video {
		width: 100%;
		max-height: 150px;
		border-radius: 4px;
		background: var(--body-background-fill);
	}

	.recording-preview .recording-indicator {
		position: absolute;
		top: 10px;
		left: 16px;
		display: flex;
		align-items: center;
		gap: 4px;
		background: rgba(0, 0, 0, 0.6);
		padding: 2px 6px;
		border-radius: 3px;
		font-size: 10px;
		color: var(--error-border-color);
		font-weight: 600;
	}

	.rec-dot {
		width: 6px;
		height: 6px;
		background: var(--error-border-color);
		border-radius: 50%;
		animation: blink 1s ease-in-out infinite;
	}

	@keyframes blink {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.3; }
	}

	.gr-empty {
		font-size: 11px;
		color: var(--input-placeholder-color);
		font-style: italic;
		padding: 6px;
		text-align: center;
	}
</style>


