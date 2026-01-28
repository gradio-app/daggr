<script lang="ts">
	interface Props {
		label: string;
		value: string;
		language?: string;
		lineNumbers?: boolean;
		editable?: boolean;
		onchange?: (value: string) => void;
	}

	let { 
		label, 
		value, 
		language = 'text',
		lineNumbers = true,
		editable = false,
		onchange 
	}: Props = $props();

	let copySuccess = $state(false);
	let containerEl: HTMLDivElement | null = $state(null);
	let isFullscreen = $state(false);

	let lines = $derived(value ? value.split('\n') : ['']);

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

	function copyCode() {
		navigator.clipboard.writeText(value).then(() => {
			copySuccess = true;
			setTimeout(() => copySuccess = false, 1500);
		});
	}

	function downloadCode() {
		const blob = new Blob([value], { type: 'text/plain' });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = url;
		link.download = `${label || 'code'}.${language}`;
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		URL.revokeObjectURL(url);
	}

	function handleInput(e: Event) {
		const target = e.target as HTMLTextAreaElement;
		onchange?.(target.value);
	}
</script>

<svelte:document onfullscreenchange={handleFullscreenChange} />

<div class="gr-code-wrap" class:fullscreen={isFullscreen} bind:this={containerEl}>
	<div class="gr-header">
		<div class="header-left">
			<span class="gr-label">{label}</span>
			<span class="language-badge">{language}</span>
		</div>
		<div class="code-actions">
			<button class="action-btn" onclick={openFullscreen} title="View fullscreen">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
				</svg>
			</button>
			<button class="action-btn" class:success={copySuccess} onclick={copyCode} title="Copy code">
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
			<button class="action-btn" onclick={downloadCode} title="Download">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
					<polyline points="7 10 12 15 17 10"/>
					<line x1="12" y1="15" x2="12" y2="3"/>
				</svg>
			</button>
		</div>
	</div>

	<div class="code-container">
		{#if editable}
			<textarea
				class="code-editor"
				value={value}
				oninput={handleInput}
				spellcheck="false"
			></textarea>
		{:else}
			<div class="code-display">
				{#if lineNumbers}
					<div class="line-numbers">
						{#each lines as _, i}
							<span>{i + 1}</span>
						{/each}
					</div>
				{/if}
				<pre class="code-content"><code>{value}</code></pre>
			</div>
		{/if}
	</div>
</div>

<style>
	.gr-code-wrap {
		background: #1a1a1a;
		border: 1px solid #333;
		border-radius: 6px;
		overflow: hidden;
	}

	.gr-code-wrap.fullscreen {
		border-radius: 0;
		display: flex;
		flex-direction: column;
		height: 100vh;
	}

	.gr-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px;
		background: #222;
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.gr-label {
		font-size: 10px;
		font-weight: 400;
		color: #888;
		padding-left: 4px;
	}

	.language-badge {
		font-size: 9px;
		padding: 2px 6px;
		background: #333;
		color: #888;
		border-radius: 3px;
		text-transform: lowercase;
	}

	.code-actions {
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

	.code-container {
		max-height: 300px;
		overflow: auto;
	}

	.gr-code-wrap.fullscreen .code-container {
		max-height: none;
		flex: 1;
	}

	.gr-code-wrap.fullscreen .code-content,
	.gr-code-wrap.fullscreen .code-editor {
		font-size: 14px;
	}

	.gr-code-wrap.fullscreen .line-numbers span {
		font-size: 14px;
	}

	.code-display {
		display: flex;
	}

	.line-numbers {
		display: flex;
		flex-direction: column;
		padding: 10px 0;
		background: #1e1e1e;
		border-right: 1px solid #333;
		user-select: none;
		flex-shrink: 0;
	}

	.line-numbers span {
		padding: 0 10px;
		font-family: 'SF Mono', Monaco, Consolas, monospace;
		font-size: 11px;
		line-height: 1.5;
		color: #555;
		text-align: right;
		min-width: 30px;
	}

	.code-content {
		flex: 1;
		margin: 0;
		padding: 10px;
		font-family: 'SF Mono', Monaco, Consolas, monospace;
		font-size: 11px;
		line-height: 1.5;
		color: #e5e7eb;
		overflow-x: auto;
		white-space: pre;
	}

	.code-content code {
		font-family: inherit;
	}

	.code-editor {
		width: 100%;
		min-height: 150px;
		padding: 10px;
		font-family: 'SF Mono', Monaco, Consolas, monospace;
		font-size: 11px;
		line-height: 1.5;
		color: #e5e7eb;
		background: transparent;
		border: none;
		outline: none;
		resize: vertical;
	}
</style>

