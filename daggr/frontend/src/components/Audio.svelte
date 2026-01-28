<script lang="ts">
	import AudioPlayer from './AudioPlayer.svelte';

	interface Props {
		label: string;
		value: any;
		id: string;
		editable?: boolean;
		onchange?: (value: any) => void;
	}

	let { label, value, id, editable = true, onchange }: Props = $props();

	let fileInputEl: HTMLInputElement | null = $state(null);
	let isRecording = $state(false);
	let mediaRecorder: MediaRecorder | null = $state(null);
	let recordedChunks: Blob[] = $state([]);
	let recordingTime = $state(0);
	let recordingTimer: number | null = $state(null);

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
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			mediaRecorder = new MediaRecorder(stream);
			recordedChunks = [];
			recordingTime = 0;

			mediaRecorder.ondataavailable = (e) => {
				if (e.data.size > 0) {
					recordedChunks.push(e.data);
				}
			};

			mediaRecorder.onstop = () => {
				const blob = new Blob(recordedChunks, { type: 'audio/webm' });
				onchange?.(blob);
				stream.getTracks().forEach(track => track.stop());
				if (recordingTimer) {
					clearInterval(recordingTimer);
					recordingTimer = null;
				}
			};

			mediaRecorder.start();
			isRecording = true;
			
			recordingTimer = window.setInterval(() => {
				recordingTime += 1;
			}, 1000);
		} catch (e) {
			console.error('Failed to access microphone:', e);
		}
	}

	function stopRecording() {
		if (mediaRecorder && mediaRecorder.state !== 'inactive') {
			mediaRecorder.stop();
		}
		isRecording = false;
	}

	function clearAudio() {
		onchange?.(null);
	}

	function formatTime(seconds: number): string {
		const mins = Math.floor(seconds / 60);
		const secs = seconds % 60;
		return `${mins}:${secs.toString().padStart(2, '0')}`;
	}

	async function downloadAudio() {
		if (!src) return;
		try {
			const response = await fetch(src);
			const blob = await response.blob();
			const blobUrl = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = blobUrl;
			
			let ext = 'wav';
			try {
				const urlPath = new URL(src, window.location.origin).pathname;
				const urlExt = urlPath.split('.').pop()?.toLowerCase();
				if (urlExt && ['wav', 'mp3', 'webm', 'ogg', 'flac', 'm4a', 'aac'].includes(urlExt)) {
					ext = urlExt;
				}
			} catch {
				const blobExt = blob.type.split('/')[1]?.split(';')[0];
				if (blobExt && blobExt !== 'octet-stream') {
					ext = blobExt;
				}
			}
			
			link.download = `${label || 'audio'}.${ext}`;
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			URL.revokeObjectURL(blobUrl);
		} catch (e) {
			console.error('Failed to download audio:', e);
		}
	}
</script>

<div class="gr-audio-wrap">
	<input
		bind:this={fileInputEl}
		type="file"
		accept="audio/*"
		style="display: none"
		onchange={handleFileSelect}
	/>
	
	<div class="gr-header">
		<span class="gr-label">{label}</span>
		<div class="audio-actions">
			{#if editable && !isRecording && !src}
				<button class="action-btn" onclick={triggerUpload} title="Upload audio">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
						<polyline points="17 8 12 3 7 8"/>
						<line x1="12" y1="3" x2="12" y2="15"/>
					</svg>
				</button>
				<button class="action-btn" onclick={startRecording} title="Record from microphone">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
						<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
						<line x1="12" y1="19" x2="12" y2="23"/>
						<line x1="8" y1="23" x2="16" y2="23"/>
					</svg>
				</button>
			{/if}
			{#if isRecording}
				<button class="action-btn recording" onclick={stopRecording} title="Stop recording">
					<svg viewBox="0 0 24 24" fill="currentColor">
						<rect x="6" y="6" width="12" height="12" rx="2"/>
					</svg>
				</button>
			{/if}
			{#if src && !isRecording}
				{#if editable}
					<button class="action-btn" onclick={clearAudio} title="Clear audio">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<line x1="18" y1="6" x2="6" y2="18"/>
							<line x1="6" y1="6" x2="18" y2="18"/>
						</svg>
					</button>
				{/if}
				<button class="action-btn" onclick={downloadAudio} title="Download">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
						<polyline points="7 10 12 15 17 10"/>
						<line x1="12" y1="15" x2="12" y2="3"/>
					</svg>
				</button>
			{/if}
		</div>
	</div>
	
	{#if isRecording}
		<div class="recording-indicator">
			<span class="recording-dot"></span>
			<span class="recording-time">{formatTime(recordingTime)}</span>
			<span class="recording-text">Recording...</span>
		</div>
	{:else if src}
		<AudioPlayer {src} {id} />
	{:else}
		<div class="gr-empty">No audio</div>
	{/if}
</div>

<style>
	.gr-audio-wrap {
		background: #1a1a1a;
		border: 1px solid #333;
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
		color: #888;
		padding-left: 4px;
	}

	.audio-actions {
		display: flex;
		gap: 4px;
	}

	.action-btn {
		width: 20px;
		height: 20px;
		padding: 3px;
		border: none;
		background: rgba(255, 255, 255, 0.08);
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
		color: #888;
	}

	.action-btn:hover {
		background: rgba(255, 255, 255, 0.15);
	}

	.action-btn:hover svg {
		color: #fff;
	}

	.action-btn.recording {
		background: #dc2626;
		animation: pulse-recording 1.5s ease-in-out infinite;
	}

	.action-btn.recording svg {
		color: #fff;
	}

	.action-btn.recording:hover {
		background: #ef4444;
	}

	@keyframes pulse-recording {
		0%, 100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.4); }
		50% { box-shadow: 0 0 0 4px rgba(220, 38, 38, 0); }
	}

	.recording-indicator {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 12px 10px;
		background: linear-gradient(135deg, #1e1e1e 0%, #171717 100%);
	}

	.recording-dot {
		width: 10px;
		height: 10px;
		background: #dc2626;
		border-radius: 50%;
		animation: blink 1s ease-in-out infinite;
	}

	@keyframes blink {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.3; }
	}

	.recording-time {
		font-size: 12px;
		font-family: 'SF Mono', Monaco, monospace;
		color: #dc2626;
		font-weight: 600;
	}

	.recording-text {
		font-size: 11px;
		color: #888;
	}

	.gr-empty {
		font-size: 11px;
		color: #555;
		font-style: italic;
		padding: 6px;
		text-align: center;
	}
</style>

