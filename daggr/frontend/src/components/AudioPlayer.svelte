<script lang="ts">
	interface Props {
		src: string;
		id: string;
		compact?: boolean;
	}

	let { src, id, compact = false }: Props = $props();

	let audioEl = $state<HTMLAudioElement | null>(null);
	let playing = $state(false);
	let currentTime = $state(0);
	let duration = $state(0);

	function formatTime(seconds: number): string {
		if (!seconds || !isFinite(seconds)) return '0:00';
		const mins = Math.floor(seconds / 60);
		const secs = Math.floor(seconds % 60);
		return `${mins}:${secs.toString().padStart(2, '0')}`;
	}

	function togglePlay(e: MouseEvent) {
		e.stopPropagation();
		if (!audioEl) return;
		if (audioEl.paused) {
			audioEl.play();
		} else {
			audioEl.pause();
		}
	}

	function seek(e: MouseEvent) {
		e.stopPropagation();
		if (!audioEl || !duration) return;
		const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
		const x = e.clientX - rect.left;
		const percent = x / rect.width;
		audioEl.currentTime = percent * duration;
	}

	function handleLoadedMetadata() {
		if (audioEl) duration = audioEl.duration;
	}

	function handleTimeUpdate() {
		if (audioEl) currentTime = audioEl.currentTime;
	}

	function handlePlay() {
		playing = true;
	}

	function handlePause() {
		playing = false;
	}

	function handleEnded() {
		playing = false;
		currentTime = 0;
	}
</script>

<audio 
	bind:this={audioEl}
	{src}
	preload="metadata"
	style="display:none"
	onloadedmetadata={handleLoadedMetadata}
	ontimeupdate={handleTimeUpdate}
	onplay={handlePlay}
	onpause={handlePause}
	onended={handleEnded}
></audio>

<div class="audio-player" class:compact>
	<button class="play-btn" onclick={togglePlay}>
		{#if playing}
			<svg viewBox="0 0 24 24" fill="currentColor">
				<rect x="6" y="4" width="4" height="16"/>
				<rect x="14" y="4" width="4" height="16"/>
			</svg>
		{:else}
			<svg viewBox="0 0 24 24" fill="currentColor">
				<path d="M8 5v14l11-7z"/>
			</svg>
		{/if}
	</button>
	<div class="progress" onclick={seek} role="slider" tabindex="0" aria-valuenow={currentTime} aria-valuemin="0" aria-valuemax={duration}>
		<div class="progress-fill" style="width: {duration ? (currentTime / duration) * 100 : 0}%"></div>
	</div>
	<span class="time">{formatTime(currentTime)} / {formatTime(duration)}</span>
</div>

<style>
	.audio-player {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 10px;
		background: linear-gradient(135deg, var(--block-background-fill) 0%, color-mix(in srgb, var(--block-background-fill) 90%, black) 100%);
	}

	.audio-player.compact {
		padding: 6px 8px;
		gap: 6px;
		flex: 1;
	}

	.play-btn {
		width: 28px;
		height: 28px;
		border: none;
		background: var(--color-accent);
		color: var(--button-primary-text-color);
		border-radius: 50%;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		transition: all 0.15s;
	}

	.play-btn:hover {
		background: var(--color-accent-soft);
		transform: scale(1.05);
	}

	.play-btn svg {
		width: 14px;
		height: 14px;
	}

	.compact .play-btn {
		width: 24px;
		height: 24px;
	}

	.compact .play-btn svg {
		width: 12px;
		height: 12px;
	}

	.progress {
		flex: 1;
		height: 6px;
		background: var(--border-color-primary);
		border-radius: 3px;
		cursor: pointer;
		position: relative;
		overflow: hidden;
	}

	.progress:hover {
		height: 8px;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--color-accent) 0%, var(--color-accent-soft) 100%);
		border-radius: 3px;
		transition: width 0.1s linear;
	}

	.time {
		font-size: 10px;
		font-family: 'SF Mono', Monaco, monospace;
		color: var(--body-text-color-subdued);
		min-width: 70px;
		text-align: right;
		flex-shrink: 0;
	}

	.compact .time {
		font-size: 9px;
		min-width: 60px;
	}
</style>

