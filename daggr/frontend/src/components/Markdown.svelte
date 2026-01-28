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

	let containerEl: HTMLDivElement | null = $state(null);
	let isFullscreen = $state(false);

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

	function parseMarkdown(text: string): string {
		if (!text) return '';
		
		let html = text
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;');

		html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
		html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
		html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

		html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
		html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
		html = html.replace(/`(.+?)`/g, '<code>$1</code>');
		html = html.replace(/~~(.+?)~~/g, '<del>$1</del>');

		html = html.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

		html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
		html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

		html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

		html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');

		html = html.replace(/^---$/gm, '<hr>');

		html = html.replace(/\n\n/g, '</p><p>');
		html = '<p>' + html + '</p>';
		html = html.replace(/<p><\/p>/g, '');
		html = html.replace(/<p>(<h[1-6]>)/g, '$1');
		html = html.replace(/(<\/h[1-6]>)<\/p>/g, '$1');
		html = html.replace(/<p>(<ul>)/g, '$1');
		html = html.replace(/(<\/ul>)<\/p>/g, '$1');
		html = html.replace(/<p>(<blockquote>)/g, '$1');
		html = html.replace(/(<\/blockquote>)<\/p>/g, '$1');
		html = html.replace(/<p>(<hr>)<\/p>/g, '$1');

		return html;
	}

	let renderedHtml = $derived(parseMarkdown(value));
</script>

<svelte:document onfullscreenchange={handleFullscreenChange} />

<div class="gr-markdown-wrap" class:fullscreen={isFullscreen} bind:this={containerEl}>
	<div class="gr-header">
		{#if showLabel && label}
			<span class="gr-label">{label}</span>
		{:else}
			<span></span>
		{/if}
		<div class="markdown-actions">
			<button class="action-btn" onclick={openFullscreen} title="View fullscreen">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
				</svg>
			</button>
		</div>
	</div>
	
	<div class="markdown-content">
		{@html renderedHtml}
	</div>
</div>

<style>
	.gr-markdown-wrap {
		background: #1a1a1a;
		border: 1px solid #333;
		border-radius: 6px;
		overflow: hidden;
	}

	.gr-markdown-wrap.fullscreen {
		border-radius: 0;
		display: flex;
		flex-direction: column;
		height: 100vh;
	}

	.gr-markdown-wrap.fullscreen .markdown-content {
		flex: 1;
		overflow: auto;
		font-size: 16px;
		padding: 24px;
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

	.markdown-actions {
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

	.markdown-content {
		padding: 10px;
		font-size: 12px;
		line-height: 1.6;
		color: #e5e7eb;
	}

	.markdown-content :global(h1) {
		font-size: 18px;
		font-weight: 600;
		margin: 0 0 12px 0;
		color: #fff;
	}

	.markdown-content :global(h2) {
		font-size: 15px;
		font-weight: 600;
		margin: 12px 0 8px 0;
		color: #fff;
	}

	.markdown-content :global(h3) {
		font-size: 13px;
		font-weight: 600;
		margin: 10px 0 6px 0;
		color: #fff;
	}

	.markdown-content :global(p) {
		margin: 0 0 8px 0;
	}

	.markdown-content :global(p:last-child) {
		margin-bottom: 0;
	}

	.markdown-content :global(strong) {
		font-weight: 600;
		color: #fff;
	}

	.markdown-content :global(em) {
		font-style: italic;
	}

	.markdown-content :global(code) {
		font-family: 'SF Mono', Monaco, Consolas, monospace;
		font-size: 11px;
		background: #2a2a2a;
		padding: 2px 4px;
		border-radius: 3px;
		color: #f97316;
	}

	.markdown-content :global(del) {
		text-decoration: line-through;
		color: #888;
	}

	.markdown-content :global(a) {
		color: #60a5fa;
		text-decoration: none;
	}

	.markdown-content :global(a:hover) {
		text-decoration: underline;
	}

	.markdown-content :global(ul) {
		margin: 0 0 8px 0;
		padding-left: 20px;
	}

	.markdown-content :global(li) {
		margin: 2px 0;
	}

	.markdown-content :global(blockquote) {
		margin: 8px 0;
		padding: 8px 12px;
		border-left: 3px solid #f97316;
		background: rgba(249, 115, 22, 0.1);
		color: #ccc;
	}

	.markdown-content :global(hr) {
		border: none;
		border-top: 1px solid #333;
		margin: 12px 0;
	}
</style>

