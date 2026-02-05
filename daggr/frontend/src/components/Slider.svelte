<script lang="ts">
	interface Props {
		label: string;
		value: number;
		min?: number;
		max?: number;
		step?: number;
		disabled?: boolean;
		onchange?: (value: number) => void;
	}

	let { 
		label, 
		value, 
		min = 0, 
		max = 100, 
		step = 1, 
		disabled = false,
		onchange 
	}: Props = $props();

	let rangeEl: HTMLInputElement | null = $state(null);

	let percentage = $derived(((value - min) / (max - min)) * 100);

	$effect(() => {
		if (rangeEl) {
			rangeEl.style.setProperty('--range-progress', `${percentage}%`);
		}
	});

	function handleRangeInput(e: Event) {
		const target = e.target as HTMLInputElement;
		onchange?.(parseFloat(target.value));
	}

	function handleNumberInput(e: Event) {
		const target = e.target as HTMLInputElement;
		let newValue = parseFloat(target.value);
		if (!isNaN(newValue)) {
			newValue = Math.min(Math.max(newValue, min), max);
			onchange?.(newValue);
		}
	}
</script>

<div class="gr-slider-wrap">
	<div class="gr-header">
		<span class="gr-label">{label}</span>
		<input
			type="number"
			class="number-input"
			{value}
			min={min}
			max={max}
			{step}
			{disabled}
			oninput={handleNumberInput}
		/>
	</div>
	<div class="slider-container">
		<span class="min-value">{min}</span>
		<input
			bind:this={rangeEl}
			type="range"
			class="range-input"
			{value}
			min={min}
			max={max}
			{step}
			{disabled}
			oninput={handleRangeInput}
		/>
		<span class="max-value">{max}</span>
	</div>
</div>

<style>
	.gr-slider-wrap {
		background: var(--block-background-fill);
		border: 1px solid var(--border-color-primary);
		border-radius: 6px;
		padding: 6px 10px 10px;
	}

	.gr-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 8px;
	}

	.gr-label {
		font-size: 10px;
		font-weight: 400;
		color: var(--body-text-color-subdued);
	}

	.number-input {
		width: 60px;
		padding: 3px 6px;
		background: var(--input-background-fill);
		border: 1px solid var(--input-border-color);
		border-radius: 4px;
		font-size: 11px;
		color: var(--body-text-color);
		text-align: center;
		outline: none;
	}

	.number-input:focus {
		border-color: var(--color-accent);
	}

	.number-input:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.slider-container {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.min-value, .max-value {
		font-size: 10px;
		color: var(--neutral-500);
		min-width: 24px;
	}

	.min-value {
		text-align: right;
	}

	.max-value {
		text-align: left;
	}

	.range-input {
		flex: 1;
		-webkit-appearance: none;
		appearance: none;
		height: 4px;
		background: linear-gradient(
			to right,
			var(--color-accent) var(--range-progress, 0%),
			var(--border-color-primary) var(--range-progress, 0%)
		);
		border-radius: 2px;
		outline: none;
		cursor: pointer;
	}

	.range-input:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.range-input::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 14px;
		height: 14px;
		background: var(--body-text-color);
		border-radius: 50%;
		cursor: pointer;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
		transition: transform 0.1s;
	}

	.range-input::-webkit-slider-thumb:hover {
		transform: scale(1.1);
	}

	.range-input::-moz-range-thumb {
		width: 14px;
		height: 14px;
		background: var(--body-text-color);
		border: none;
		border-radius: 50%;
		cursor: pointer;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
	}

	.range-input::-moz-range-progress {
		background: var(--color-accent);
		height: 4px;
		border-radius: 2px;
	}

	.range-input::-moz-range-track {
		background: var(--border-color-primary);
		height: 4px;
		border-radius: 2px;
	}
</style>

