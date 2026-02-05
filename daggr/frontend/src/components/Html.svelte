<script lang="ts">
	interface Props {
		label?: string;
		value: string;
		showLabel?: boolean;
	}

	let { 
		label = '', 
		value, 
		showLabel = false
	}: Props = $props();

	let contentEl: HTMLDivElement | null = $state(null);

	function openFullscreen() {
		if (!contentEl) return;
		if (contentEl.requestFullscreen) {
			contentEl.requestFullscreen();
		} else if ((contentEl as any).webkitRequestFullscreen) {
			(contentEl as any).webkitRequestFullscreen();
		}
	}
</script>

<div class="gr-html-wrap">
	<div class="gr-header">
		{#if showLabel && label}
			<span class="gr-label">{label}</span>
		{:else}
			<span class="gr-label-spacer"></span>
		{/if}
		{#if value}
			<button class="action-btn" onclick={openFullscreen} title="View fullscreen">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
				</svg>
			</button>
		{/if}
	</div>
	
	<div class="html-content" bind:this={contentEl}>
		{@html value}
	</div>
</div>

<style>
	.gr-html-wrap {
		background: var(--block-background-fill);
		border: 1px solid var(--border-color-primary);
		border-radius: 6px;
		overflow: hidden;
	}

	.gr-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 6px 0 6px;
	}

	.gr-label {
		font-size: 10px;
		font-weight: 400;
		color: var(--body-text-color-subdued);
		padding-left: 4px;
	}

	.gr-label-spacer {
		flex: 1;
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

	.html-content {
		padding: 8px 10px 10px;
		font-size: 12px;
		line-height: 1.5;
		color: var(--body-text-color);
		max-height: 200px;
		overflow: auto;
	}

	.html-content:fullscreen {
		background: var(--block-background-fill);
		padding: 40px;
		max-height: none;
		overflow: auto;
	}
</style>
