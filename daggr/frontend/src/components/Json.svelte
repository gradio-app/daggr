<script lang="ts">
	interface Props {
		label: string;
		value: any;
		open?: boolean | number;
		showIndices?: boolean;
	}

	let { 
		label, 
		value, 
		open = 2,
		showIndices = true
	}: Props = $props();

	let copySuccess = $state(false);
	let containerEl: HTMLDivElement | null = $state(null);
	let isFullscreen = $state(false);

	function copyJson() {
		const text = JSON.stringify(value, null, 2);
		navigator.clipboard.writeText(text).then(() => {
			copySuccess = true;
			setTimeout(() => copySuccess = false, 1500);
		});
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

<div class="gr-json-wrap" class:fullscreen={isFullscreen} bind:this={containerEl}>
	<div class="gr-header">
		<span class="gr-label">{label}</span>
		<div class="json-actions">
			<button class="action-btn" onclick={openFullscreen} title="View fullscreen">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
				</svg>
			</button>
			{#if value !== null && value !== undefined}
				<button class="action-btn" class:success={copySuccess} onclick={copyJson} title="Copy JSON">
					{#if copySuccess}
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<polyline points="20 6 9 17 4 12"/>
						</svg>
					{:else}
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
							<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
						</svg>
					{/if}
				</button>
			{/if}
		</div>
	</div>

	{#if value !== null && value !== undefined}
		<div class="json-content">
			<JsonNode value={value} depth={0} maxOpen={typeof open === 'number' ? open : (open ? Infinity : 0)} {showIndices} />
		</div>
	{:else}
		<div class="gr-empty">null</div>
	{/if}
</div>

{#snippet JsonNode(props: { value: any; depth: number; maxOpen: number; showIndices: boolean; key?: string | number })}
	{@const { value: nodeValue, depth, maxOpen, showIndices, key } = props}
	{@const isOpen = depth < maxOpen}
	
	{#if Array.isArray(nodeValue)}
		<div class="json-node">
			{#if key !== undefined}
				<span class="json-key">{showIndices && typeof key === 'number' ? `[${key}]` : `"${key}"`}</span>
				<span class="json-colon">: </span>
			{/if}
			<details open={isOpen}>
				<summary class="json-bracket">[<span class="json-preview">{nodeValue.length} items</span>]</summary>
				<div class="json-children">
					{#each nodeValue as item, i}
						{@render JsonNode({ value: item, depth: depth + 1, maxOpen, showIndices, key: i })}
					{/each}
				</div>
			</details>
		</div>
	{:else if typeof nodeValue === 'object' && nodeValue !== null}
		<div class="json-node">
			{#if key !== undefined}
				<span class="json-key">{showIndices && typeof key === 'number' ? `[${key}]` : `"${key}"`}</span>
				<span class="json-colon">: </span>
			{/if}
			<details open={isOpen}>
				<summary class="json-bracket">&#123;<span class="json-preview">{Object.keys(nodeValue).length} keys</span>&#125;</summary>
				<div class="json-children">
					{#each Object.entries(nodeValue) as [k, v]}
						{@render JsonNode({ value: v, depth: depth + 1, maxOpen, showIndices, key: k })}
					{/each}
				</div>
			</details>
		</div>
	{:else}
		<div class="json-node json-leaf">
			{#if key !== undefined}
				<span class="json-key">{showIndices && typeof key === 'number' ? `[${key}]` : `"${key}"`}</span>
				<span class="json-colon">: </span>
			{/if}
			{#if typeof nodeValue === 'string'}
				<span class="json-string">"{nodeValue}"</span>
			{:else if typeof nodeValue === 'number'}
				<span class="json-number">{nodeValue}</span>
			{:else if typeof nodeValue === 'boolean'}
				<span class="json-boolean">{nodeValue ? 'true' : 'false'}</span>
			{:else if nodeValue === null}
				<span class="json-null">null</span>
			{:else}
				<span class="json-undefined">undefined</span>
			{/if}
		</div>
	{/if}
{/snippet}

<style>
	.gr-json-wrap {
		background: #1a1a1a;
		border: 1px solid #333;
		border-radius: 6px;
		overflow: hidden;
	}

	.gr-json-wrap.fullscreen {
		border-radius: 0;
		display: flex;
		flex-direction: column;
		height: 100vh;
	}

	.gr-json-wrap.fullscreen .json-content {
		flex: 1;
		overflow: auto;
		font-size: 14px;
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

	.json-actions {
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

	.action-btn.success svg {
		color: #22c55e;
	}

	.json-content {
		padding: 0 10px 10px;
		font-family: 'SF Mono', Monaco, Consolas, monospace;
		font-size: 11px;
		line-height: 1.5;
		overflow-x: auto;
	}

	.json-node {
		display: block;
	}

	.json-leaf {
		padding-left: 0;
	}

	.json-children {
		padding-left: 16px;
		border-left: 1px solid #333;
		margin-left: 4px;
	}

	.json-key {
		color: #93c5fd;
	}

	.json-colon {
		color: #666;
	}

	.json-string {
		color: #a5d6a7;
	}

	.json-number {
		color: #ffcc80;
	}

	.json-boolean {
		color: #ce93d8;
	}

	.json-null {
		color: #ef9a9a;
	}

	.json-undefined {
		color: #666;
	}

	.json-bracket {
		color: #888;
		cursor: pointer;
		list-style: none;
		display: inline;
	}

	.json-bracket::-webkit-details-marker {
		display: none;
	}

	.json-bracket::before {
		content: '▶';
		display: inline-block;
		width: 12px;
		font-size: 8px;
		color: #666;
		transition: transform 0.15s;
	}

	details[open] > .json-bracket::before {
		transform: rotate(90deg);
	}

	.json-preview {
		color: #555;
		font-size: 10px;
		margin-left: 4px;
	}

	details[open] > .json-bracket .json-preview {
		display: none;
	}

	.gr-empty {
		font-size: 11px;
		color: #555;
		font-style: italic;
		padding: 6px 10px;
	}
</style>

