<script lang="ts">
	interface Props {
		label: string;
		choices: [string, string | number][];
		value: (string | number)[];
		disabled?: boolean;
		onchange?: (value: (string | number)[]) => void;
	}

	let { label, choices, value, disabled = false, onchange }: Props = $props();

	function toggleChoice(internalValue: string | number) {
		if (disabled) return;
		let newValue: (string | number)[];
		if (value.includes(internalValue)) {
			newValue = value.filter(v => v !== internalValue);
		} else {
			newValue = [...value, internalValue];
		}
		onchange?.(newValue);
	}
</script>

<div class="gr-checkboxgroup-wrap">
	<span class="gr-label">{label}</span>
	<div class="choices">
		{#each choices as [displayValue, internalValue]}
			<label class="choice" class:disabled class:selected={value.includes(internalValue)}>
				<input
					type="checkbox"
					checked={value.includes(internalValue)}
					{disabled}
					onchange={() => toggleChoice(internalValue)}
				/>
				<span class="checkmark"></span>
				<span class="choice-label">{displayValue}</span>
			</label>
		{/each}
	</div>
</div>

<style>
	.gr-checkboxgroup-wrap {
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
		padding: 6px 10px 4px;
	}

	.choices {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		padding: 0 10px 8px;
	}

	.choice {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 4px 8px;
		background: var(--input-background-fill);
		border: 1px solid var(--input-border-color);
		border-radius: 4px;
		cursor: pointer;
		transition: all 0.15s;
	}

	.choice:hover:not(.disabled) {
		border-color: var(--border-color-primary);
		background: var(--background-fill-secondary);
	}

	.choice.selected {
		background: color-mix(in srgb, var(--color-accent) 15%, transparent);
		border-color: color-mix(in srgb, var(--color-accent) 40%, transparent);
	}

	.choice.disabled {
		cursor: not-allowed;
		opacity: 0.6;
	}

	.choice input {
		position: absolute;
		opacity: 0;
		cursor: pointer;
		height: 0;
		width: 0;
	}

	.checkmark {
		width: 12px;
		height: 12px;
		background: var(--checkbox-background-color);
		border: 1px solid var(--checkbox-border-color);
		border-radius: 2px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
		flex-shrink: 0;
	}

	.choice input:checked ~ .checkmark {
		background: var(--color-accent);
		border-color: var(--color-accent);
	}

	.checkmark::after {
		content: '';
		display: none;
		width: 3px;
		height: 6px;
		border: solid var(--button-primary-text-color);
		border-width: 0 1.5px 1.5px 0;
		transform: rotate(45deg);
		margin-bottom: 1px;
	}

	.choice input:checked ~ .checkmark::after {
		display: block;
	}

	.choice-label {
		font-size: 11px;
		color: var(--body-text-color);
	}
</style>

