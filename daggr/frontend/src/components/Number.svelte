<script lang="ts">
	interface Props {
		label: string;
		value: number | null;
		minimum?: number;
		maximum?: number;
		step?: number;
		placeholder?: string;
		disabled?: boolean;
		onchange?: (value: number | null) => void;
	}

	let { 
		label, 
		value, 
		minimum, 
		maximum, 
		step = 1, 
		placeholder = '',
		disabled = false,
		onchange 
	}: Props = $props();

	function handleInput(e: Event) {
		const target = e.target as HTMLInputElement;
		const newValue = target.value === '' ? null : parseFloat(target.value);
		if (newValue !== null && !isNaN(newValue)) {
			let clamped = newValue;
			if (minimum !== undefined) clamped = Math.max(clamped, minimum);
			if (maximum !== undefined) clamped = Math.min(clamped, maximum);
			onchange?.(clamped);
		} else if (newValue === null) {
			onchange?.(null);
		}
	}

	function increment() {
		if (disabled) return;
		const current = value ?? 0;
		let newValue = current + step;
		if (maximum !== undefined) newValue = Math.min(newValue, maximum);
		onchange?.(newValue);
	}

	function decrement() {
		if (disabled) return;
		const current = value ?? 0;
		let newValue = current - step;
		if (minimum !== undefined) newValue = Math.max(newValue, minimum);
		onchange?.(newValue);
	}
</script>

<div class="gr-number-wrap">
	<span class="gr-label">{label}</span>
	<div class="input-container">
		<button class="step-btn" onclick={decrement} {disabled}>
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<line x1="5" y1="12" x2="19" y2="12"/>
			</svg>
		</button>
		<input
			type="number"
			class="gr-input"
			value={value ?? ''}
			min={minimum}
			max={maximum}
			{step}
			{placeholder}
			{disabled}
			oninput={handleInput}
		/>
		<button class="step-btn" onclick={increment} {disabled}>
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<line x1="12" y1="5" x2="12" y2="19"/>
				<line x1="5" y1="12" x2="19" y2="12"/>
			</svg>
		</button>
	</div>
</div>

<style>
	.gr-number-wrap {
		background: var(--block-background-fill);
		border: 1px solid var(--border-color-primary);
		border-radius: 6px;
		overflow: hidden;
	}

	.gr-label {
		display: block;
		font-size: 10px;
		font-weight: 400;
		color: var(--body-text-color-subdued);
		padding: 6px 10px 0;
	}

	.input-container {
		display: flex;
		align-items: center;
		padding: 4px 10px 8px;
		gap: 4px;
	}

	.step-btn {
		width: 24px;
		height: 24px;
		padding: 4px;
		border: none;
		background: var(--input-background-fill);
		border-radius: 4px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.15s;
		flex-shrink: 0;
	}

	.step-btn svg {
		width: 12px;
		height: 12px;
		color: var(--body-text-color-subdued);
	}

	.step-btn:hover:not(:disabled) {
		background: var(--background-fill-secondary);
	}

	.step-btn:hover:not(:disabled) svg {
		color: var(--body-text-color);
	}

	.step-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.gr-input {
		flex: 1;
		min-width: 0;
		padding: 4px 8px;
		font-size: 11px;
		font-family: 'SF Mono', Monaco, monospace;
		color: var(--body-text-color);
		background: var(--input-background-fill);
		border: 1px solid var(--input-border-color);
		border-radius: 4px;
		outline: none;
		text-align: center;
	}

	.gr-input:focus {
		border-color: var(--color-accent);
	}

	.gr-input::placeholder {
		color: var(--input-placeholder-color);
	}

	.gr-input:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	.gr-input::-webkit-inner-spin-button,
	.gr-input::-webkit-outer-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	.gr-input[type="number"] {
		-moz-appearance: textfield;
	}
</style>

