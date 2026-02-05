<script lang="ts">
	interface TextSpan {
		text: string;
		label?: string | null;
	}

	interface Props {
		label: string;
		value: TextSpan[];
		colorMap?: Record<string, string>;
		showLegend?: boolean;
		showInlineCategory?: boolean;
	}

	let { 
		label, 
		value, 
		colorMap = {},
		showLegend = true,
		showInlineCategory = true
	}: Props = $props();

	const defaultColors = [
		'#f97316', '#22c55e', '#3b82f6', '#a855f7', '#ec4899',
		'#eab308', '#14b8a6', '#ef4444', '#8b5cf6', '#06b6d4'
	];

	let allLabels = $derived.by(() => {
		const labels = new Set<string>();
		value.forEach(span => {
			if (span.label) labels.add(span.label);
		});
		return Array.from(labels);
	});

	function getColor(labelName: string): string {
		if (colorMap[labelName]) return colorMap[labelName];
		const idx = allLabels.indexOf(labelName);
		return defaultColors[idx % defaultColors.length];
	}

	function getBackgroundColor(labelName: string): string {
		const color = getColor(labelName);
		return color + '33';
	}
</script>

<div class="gr-highlightedtext-wrap">
	<div class="gr-header">
		<span class="gr-label">{label}</span>
	</div>

	{#if value && value.length > 0}
		{#if showLegend && allLabels.length > 0}
			<div class="legend">
				{#each allLabels as labelName}
					<div class="legend-item">
						<span class="legend-color" style:background-color={getColor(labelName)}></span>
						<span class="legend-text">{labelName}</span>
					</div>
				{/each}
			</div>
		{/if}

		<div class="text-content">
			{#each value as span}
				{#if span.label}
					<span 
						class="highlighted-span"
						style:background-color={getBackgroundColor(span.label)}
						style:border-color={getColor(span.label)}
					>
						{span.text}
						{#if showInlineCategory}
							<span class="inline-label" style:background-color={getColor(span.label)}>{span.label}</span>
						{/if}
					</span>
				{:else}
					<span class="plain-text">{span.text}</span>
				{/if}
			{/each}
		</div>
	{:else}
		<div class="gr-empty">No text</div>
	{/if}
</div>

<style>
	.gr-highlightedtext-wrap {
		background: var(--block-background-fill);
		border: 1px solid var(--border-color-primary);
		border-radius: 6px;
		overflow: hidden;
	}

	.gr-header {
		padding: 6px;
	}

	.gr-label {
		font-size: 10px;
		font-weight: 400;
		color: var(--body-text-color-subdued);
		padding-left: 4px;
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		padding: 0 10px 8px;
	}

	.legend-item {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.legend-color {
		width: 10px;
		height: 10px;
		border-radius: 2px;
	}

	.legend-text {
		font-size: 10px;
		color: var(--body-text-color-subdued);
	}

	.text-content {
		padding: 0 10px 10px;
		font-size: 12px;
		line-height: 1.8;
		color: var(--body-text-color);
	}

	.plain-text {
		white-space: pre-wrap;
	}

	.highlighted-span {
		display: inline;
		padding: 2px 4px;
		border-radius: 3px;
		border-bottom: 2px solid;
		position: relative;
	}

	.inline-label {
		font-size: 9px;
		padding: 1px 4px;
		border-radius: 2px;
		color: white;
		margin-left: 4px;
		vertical-align: middle;
		font-weight: 500;
	}

	.gr-empty {
		font-size: 11px;
		color: var(--input-placeholder-color);
		font-style: italic;
		padding: 6px 10px;
		text-align: center;
	}
</style>

