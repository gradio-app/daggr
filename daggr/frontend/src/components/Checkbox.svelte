<script lang="ts">
	interface Props {
		label: string;
		value: boolean;
		disabled?: boolean;
		onchange?: (value: boolean) => void;
	}

	let { label, value, disabled = false, onchange }: Props = $props();

	function handleChange(e: Event) {
		const target = e.target as HTMLInputElement;
		onchange?.(target.checked);
	}
</script>

<div class="gr-checkbox-wrap">
	<label class="checkbox-container" class:disabled>
		<input
			type="checkbox"
			checked={value}
			{disabled}
			onchange={handleChange}
		/>
		<span class="checkmark"></span>
		<span class="gr-label">{label}</span>
	</label>
</div>

<style>
	.gr-checkbox-wrap {
		background: var(--block-background-fill);
		border: 1px solid var(--border-color-primary);
		border-radius: 6px;
		padding: 8px 10px;
	}

	.checkbox-container {
		display: flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
		position: relative;
	}

	.checkbox-container.disabled {
		cursor: not-allowed;
		opacity: 0.6;
	}

	.checkbox-container input {
		position: absolute;
		opacity: 0;
		cursor: pointer;
		height: 0;
		width: 0;
	}

	.checkmark {
		width: 14px;
		height: 14px;
		background: var(--checkbox-background-color);
		border: 1px solid var(--checkbox-border-color);
		border-radius: 3px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
		flex-shrink: 0;
	}

	.checkbox-container:hover .checkmark {
		border-color: var(--checkbox-border-color-hover);
	}

	.checkbox-container input:checked ~ .checkmark {
		background: var(--color-accent);
		border-color: var(--color-accent);
	}

	.checkmark::after {
		content: '';
		display: none;
		width: 4px;
		height: 7px;
		border: solid var(--button-primary-text-color);
		border-width: 0 2px 2px 0;
		transform: rotate(45deg);
		margin-bottom: 2px;
	}

	.checkbox-container input:checked ~ .checkmark::after {
		display: block;
	}

	.checkbox-container:focus-within .checkmark {
		border-color: var(--color-accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-accent) 20%, transparent);
	}

	.gr-label {
		font-size: 11px;
		color: var(--body-text-color);
	}

	.checkbox-container.disabled .gr-label {
		color: var(--neutral-500);
	}
</style>

