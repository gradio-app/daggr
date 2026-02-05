<script lang="ts">
	interface GalleryItem {
		image?: { url: string };
		video?: { url: string };
		caption?: string | null;
	}

	interface Props {
		label: string;
		value: GalleryItem[] | null;
		columns?: number;
		height?: number;
		objectFit?: 'contain' | 'cover' | 'fill';
		allowPreview?: boolean;
		onselect?: (index: number, item: GalleryItem) => void;
	}

	let { 
		label, 
		value, 
		columns = 3, 
		height = 200,
		objectFit = 'cover',
		allowPreview = true,
		onselect 
	}: Props = $props();

	let selectedIndex: number | null = $state(null);
	let showPreview = $state(false);

	let items = $derived(value || []);

	function handleItemClick(index: number) {
		selectedIndex = index;
		onselect?.(index, items[index]);
		if (allowPreview) {
			showPreview = true;
		}
	}

	function closePreview() {
		showPreview = false;
	}

	function navigatePreview(delta: number) {
		if (selectedIndex === null) return;
		const newIndex = (selectedIndex + delta + items.length) % items.length;
		selectedIndex = newIndex;
		onselect?.(newIndex, items[newIndex]);
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (!showPreview) return;
		if (e.key === 'Escape') closePreview();
		if (e.key === 'ArrowLeft') navigatePreview(-1);
		if (e.key === 'ArrowRight') navigatePreview(1);
	}
</script>

<svelte:window onkeydown={handleKeyDown} />

<div class="gr-gallery-wrap">
	<div class="gr-header">
		<span class="gr-label">{label}</span>
		{#if items.length > 0}
			<span class="item-count">{items.length} items</span>
		{/if}
	</div>

	{#if items.length > 0}
		<div 
			class="gallery-grid" 
			style:grid-template-columns="repeat({columns}, 1fr)"
			style:max-height="{height}px"
		>
			{#each items as item, index}
				<button
					class="gallery-item"
					class:selected={selectedIndex === index}
					onclick={() => handleItemClick(index)}
				>
					{#if item.image?.url}
						<img src={item.image.url} alt={item.caption || `Image ${index + 1}`} style:object-fit={objectFit} />
					{:else if item.video?.url}
						<!-- svelte-ignore a11y_media_has_caption -->
						<video src={item.video.url} style:object-fit={objectFit}></video>
						<div class="video-badge">
							<svg viewBox="0 0 24 24" fill="currentColor">
								<polygon points="5 3 19 12 5 21 5 3"/>
							</svg>
						</div>
					{/if}
					{#if item.caption}
						<div class="caption">{item.caption}</div>
					{/if}
				</button>
			{/each}
		</div>
	{:else}
		<div class="gr-empty">No images</div>
	{/if}
</div>

{#if showPreview && selectedIndex !== null && items[selectedIndex]}
	<div class="preview-overlay" onclick={closePreview}>
		<div class="preview-content" onclick={(e) => e.stopPropagation()}>
			<button class="preview-close" onclick={closePreview}>
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<line x1="18" y1="6" x2="6" y2="18"/>
					<line x1="6" y1="6" x2="18" y2="18"/>
				</svg>
			</button>
			
			{#if items.length > 1}
				<button class="preview-nav prev" onclick={() => navigatePreview(-1)}>
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<polyline points="15 18 9 12 15 6"/>
					</svg>
				</button>
				<button class="preview-nav next" onclick={() => navigatePreview(1)}>
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<polyline points="9 18 15 12 9 6"/>
					</svg>
				</button>
			{/if}

			{#if items[selectedIndex].image?.url}
				<img src={items[selectedIndex].image?.url} alt={items[selectedIndex].caption || ''} />
			{:else if items[selectedIndex].video?.url}
				<!-- svelte-ignore a11y_media_has_caption -->
				<video src={items[selectedIndex].video?.url} controls autoplay></video>
			{/if}

			{#if items[selectedIndex].caption}
				<div class="preview-caption">{items[selectedIndex].caption}</div>
			{/if}

			<div class="preview-counter">{selectedIndex + 1} / {items.length}</div>
		</div>
	</div>
{/if}

<style>
	.gr-gallery-wrap {
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

	.item-count {
		font-size: 10px;
		color: var(--input-placeholder-color);
	}

	.gallery-grid {
		display: grid;
		gap: 4px;
		padding: 0 6px 6px;
		overflow-y: auto;
	}

	.gallery-item {
		position: relative;
		aspect-ratio: 1;
		background: var(--background-fill-secondary);
		border: 2px solid transparent;
		border-radius: 4px;
		overflow: hidden;
		cursor: pointer;
		padding: 0;
		transition: border-color 0.15s;
	}

	.gallery-item:hover {
		border-color: var(--border-color-primary);
	}

	.gallery-item.selected {
		border-color: var(--color-accent);
	}

	.gallery-item img,
	.gallery-item video {
		width: 100%;
		height: 100%;
	}

	.video-badge {
		position: absolute;
		top: 4px;
		right: 4px;
		width: 20px;
		height: 20px;
		background: rgba(0, 0, 0, 0.6);
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.video-badge svg {
		width: 10px;
		height: 10px;
		color: white;
		margin-left: 2px;
	}

	.caption {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		padding: 4px 6px;
		background: linear-gradient(transparent, rgba(0, 0, 0, 0.8));
		font-size: 10px;
		color: white;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.gr-empty {
		font-size: 11px;
		color: var(--input-placeholder-color);
		font-style: italic;
		padding: 6px;
		text-align: center;
	}

	.preview-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.9);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}

	.preview-content {
		position: relative;
		max-width: 90vw;
		max-height: 90vh;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.preview-content img,
	.preview-content video {
		max-width: 100%;
		max-height: 80vh;
		border-radius: 4px;
	}

	.preview-close {
		position: absolute;
		top: -40px;
		right: 0;
		width: 32px;
		height: 32px;
		background: rgba(255, 255, 255, 0.1);
		border: none;
		border-radius: 50%;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.15s;
	}

	.preview-close svg {
		width: 18px;
		height: 18px;
		color: white;
	}

	.preview-close:hover {
		background: rgba(255, 255, 255, 0.2);
	}

	.preview-nav {
		position: absolute;
		top: 50%;
		transform: translateY(-50%);
		width: 40px;
		height: 40px;
		background: rgba(255, 255, 255, 0.1);
		border: none;
		border-radius: 50%;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.15s;
	}

	.preview-nav.prev {
		left: -60px;
	}

	.preview-nav.next {
		right: -60px;
	}

	.preview-nav svg {
		width: 24px;
		height: 24px;
		color: white;
	}

	.preview-nav:hover {
		background: rgba(255, 255, 255, 0.2);
	}

	.preview-caption {
		margin-top: 12px;
		font-size: 13px;
		color: var(--body-text-color-subdued);
		text-align: center;
	}

	.preview-counter {
		position: absolute;
		bottom: -30px;
		font-size: 12px;
		color: var(--neutral-500);
	}
</style>

