<script lang="ts">
	interface LabelValue {
		label: string;
		confidences?: { label: string; confidence: number }[];
	}

	interface Props {
		label: string;
		value: LabelValue;
		showHeading?: boolean;
		color?: string;
	}

	let { 
		label, 
		value, 
		showHeading = true,
		color
	}: Props = $props();

	let sortedConfidences = $derived.by(() => {
		if (!value.confidences) return [];
		return [...value.confidences].sort((a, b) => b.confidence - a.confidence);
	});

	function formatConfidence(conf: number): string {
		return (conf * 100).toFixed(1) + '%';
	}
</script>

<div class="gr-label-wrap">
	<div class="gr-header">
		<span class="gr-label">{label}</span>
	</div>

	{#if value.label}
		{#if showHeading}
			<div class="main-label" style:color={color}>
				{value.label}
			</div>
		{/if}

		{#if sortedConfidences.length > 0}
			<div class="confidences">
				{#each sortedConfidences as item, i}
					<div class="confidence-item" class:top={i === 0}>
						<div class="confidence-header">
							<span class="confidence-label">{item.label}</span>
							<span class="confidence-value">{formatConfidence(item.confidence)}</span>
						</div>
						<div class="confidence-bar-bg">
							<div 
								class="confidence-bar" 
								style:width="{item.confidence * 100}%"
								class:top={i === 0}
							></div>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	{:else}
		<div class="gr-empty">No label</div>
	{/if}
</div>

<style>
	.gr-label-wrap {
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

	.main-label {
		padding: 8px 10px;
		font-size: 18px;
		font-weight: 600;
		color: var(--color-accent);
		text-align: center;
	}

	.confidences {
		padding: 0 10px 10px;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.confidence-item {
		display: flex;
		flex-direction: column;
		gap: 3px;
	}

	.confidence-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.confidence-label {
		font-size: 11px;
		color: var(--body-text-color);
	}

	.confidence-item.top .confidence-label {
		font-weight: 500;
	}

	.confidence-value {
		font-size: 10px;
		font-family: 'SF Mono', Monaco, monospace;
		color: var(--body-text-color-subdued);
	}

	.confidence-bar-bg {
		height: 4px;
		background: var(--input-background-fill);
		border-radius: 2px;
		overflow: hidden;
	}

	.confidence-bar {
		height: 100%;
		background: var(--neutral-500);
		border-radius: 2px;
		transition: width 0.3s ease;
	}

	.confidence-bar.top {
		background: var(--color-accent);
	}

	.gr-empty {
		font-size: 11px;
		color: var(--input-placeholder-color);
		font-style: italic;
		padding: 6px 10px;
		text-align: center;
	}
</style>

