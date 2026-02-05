<script lang="ts">
	interface ImageValue {
		url: string;
	}

	interface Props {
		label: string;
		value: [ImageValue | null, ImageValue | null] | null;
		position?: number;
		sliderColor?: string;
		editable?: boolean;
		onchange?: (value: [ImageValue | null, ImageValue | null]) => void;
	}

	let { 
		label, 
		value, 
		position = 50,
		sliderColor = '#f97316',
		editable = false,
		onchange 
	}: Props = $props();

	let containerEl: HTMLDivElement | null = $state(null);
	let isDragging = $state(false);
	let sliderPosition = $state(position);

	let image1 = $derived(value?.[0]?.url || null);
	let image2 = $derived(value?.[1]?.url || null);

	function handleMouseDown(e: MouseEvent) {
		isDragging = true;
		updatePosition(e);
	}

	function handleMouseMove(e: MouseEvent) {
		if (!isDragging) return;
		updatePosition(e);
	}

	function handleMouseUp() {
		isDragging = false;
	}

	function handleTouchStart(e: TouchEvent) {
		isDragging = true;
		updatePositionTouch(e);
	}

	function handleTouchMove(e: TouchEvent) {
		if (!isDragging) return;
		updatePositionTouch(e);
	}

	function updatePosition(e: MouseEvent) {
		if (!containerEl) return;
		const rect = containerEl.getBoundingClientRect();
		const x = e.clientX - rect.left;
		const percent = Math.max(0, Math.min(100, (x / rect.width) * 100));
		sliderPosition = percent;
	}

	function updatePositionTouch(e: TouchEvent) {
		if (!containerEl || !e.touches[0]) return;
		const rect = containerEl.getBoundingClientRect();
		const x = e.touches[0].clientX - rect.left;
		const percent = Math.max(0, Math.min(100, (x / rect.width) * 100));
		sliderPosition = percent;
	}

	let fileInputEl: HTMLInputElement | null = $state(null);
	let uploadingIndex = $state<0 | 1>(0);

	function triggerUpload(index: 0 | 1) {
		uploadingIndex = index;
		fileInputEl?.click();
	}

	function handleFileSelect(e: Event) {
		const target = e.target as HTMLInputElement;
		const file = target.files?.[0];
		if (file) {
			const url = URL.createObjectURL(file);
			const newValue: [ImageValue | null, ImageValue | null] = value ? [...value] : [null, null];
			newValue[uploadingIndex] = { url };
			onchange?.(newValue);
		}
		target.value = '';
	}
</script>

<svelte:window 
	onmousemove={handleMouseMove} 
	onmouseup={handleMouseUp}
	ontouchmove={handleTouchMove}
	ontouchend={handleMouseUp}
/>

<div class="gr-imageslider-wrap">
	<input
		bind:this={fileInputEl}
		type="file"
		accept="image/*"
		style="display: none"
		onchange={handleFileSelect}
	/>

	<div class="gr-header">
		<span class="gr-label">{label}</span>
		{#if editable}
			<div class="slider-actions">
				<button class="action-btn" onclick={() => triggerUpload(0)} title="Upload left image">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
						<polyline points="17 8 12 3 7 8"/>
						<line x1="12" y1="3" x2="12" y2="15"/>
					</svg>
				</button>
				<button class="action-btn" onclick={() => triggerUpload(1)} title="Upload right image">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
						<polyline points="17 8 12 3 7 8"/>
						<line x1="12" y1="3" x2="12" y2="15"/>
					</svg>
				</button>
			</div>
		{/if}
	</div>

	{#if image1 || image2}
		<div 
			class="slider-container"
			bind:this={containerEl}
			onmousedown={handleMouseDown}
			ontouchstart={handleTouchStart}
		>
			<div class="image-layer image-before" style:clip-path="inset(0 {100 - sliderPosition}% 0 0)">
				{#if image1}
					<img src={image1} alt="Before" />
				{:else}
					<div class="empty-image">No image</div>
				{/if}
			</div>
			
			<div class="image-layer image-after">
				{#if image2}
					<img src={image2} alt="After" />
				{:else}
					<div class="empty-image">No image</div>
				{/if}
			</div>

			<div class="slider-line" style:left="{sliderPosition}%" style:background-color={sliderColor}>
				<div class="slider-handle" style:border-color={sliderColor}>
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<polyline points="15 18 9 12 15 6"/>
					</svg>
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<polyline points="9 18 15 12 9 6"/>
					</svg>
				</div>
			</div>

			<div class="labels">
				<span class="label-badge left">Before</span>
				<span class="label-badge right">After</span>
			</div>
		</div>
	{:else}
		<div class="gr-empty">No images to compare</div>
	{/if}
</div>

<style>
	.gr-imageslider-wrap {
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

	.slider-actions {
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

	.slider-container {
		position: relative;
		margin: 0 6px 6px;
		border-radius: 4px;
		overflow: hidden;
		cursor: ew-resize;
		aspect-ratio: 16/9;
		background: var(--body-background-fill);
	}

	.image-layer {
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
	}

	.image-layer img {
		width: 100%;
		height: 100%;
		object-fit: contain;
	}

	.image-before {
		z-index: 2;
	}

	.image-after {
		z-index: 1;
	}

	.empty-image {
		width: 100%;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--input-placeholder-color);
		font-size: 11px;
		font-style: italic;
		background: var(--block-background-fill);
	}

	.slider-line {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 2px;
		transform: translateX(-50%);
		z-index: 10;
		pointer-events: none;
	}

	.slider-handle {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		width: 32px;
		height: 32px;
		background: var(--block-background-fill);
		border: 2px solid;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		pointer-events: none;
	}

	.slider-handle svg {
		width: 12px;
		height: 12px;
		color: var(--body-text-color-subdued);
	}

	.labels {
		position: absolute;
		top: 8px;
		left: 8px;
		right: 8px;
		display: flex;
		justify-content: space-between;
		z-index: 5;
		pointer-events: none;
	}

	.label-badge {
		font-size: 9px;
		padding: 2px 6px;
		background: rgba(0, 0, 0, 0.6);
		color: #fff;
		border-radius: 3px;
	}

	.gr-empty {
		font-size: 11px;
		color: var(--input-placeholder-color);
		font-style: italic;
		padding: 6px;
		text-align: center;
	}
</style>

