<script lang="ts">
	interface Props {
		value: string;
		variant?: 'primary' | 'secondary' | 'stop';
		size?: 'sm' | 'md' | 'lg';
		disabled?: boolean;
		onclick?: () => void;
	}

	let { 
		value, 
		variant = 'primary', 
		size = 'md', 
		disabled = false,
		onclick 
	}: Props = $props();
</script>

<button 
	class="gr-button {variant} {size}" 
	{disabled}
	onclick={() => onclick?.()}
>
	{value}
</button>

<style>
	.gr-button {
		font-family: inherit;
		font-weight: 500;
		border: none;
		border-radius: 6px;
		cursor: pointer;
		transition: all 0.15s;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}

	.gr-button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.sm {
		padding: 4px 10px;
		font-size: 10px;
	}

	.md {
		padding: 6px 14px;
		font-size: 11px;
	}

	.lg {
		padding: 8px 18px;
		font-size: 12px;
	}

	.primary {
		background: var(--color-accent);
		color: var(--button-primary-text-color);
	}

	.primary:hover:not(:disabled) {
		background: var(--button-primary-background-fill-hover);
	}

	.primary:active:not(:disabled) {
		background: var(--button-primary-background-fill-hover);
		filter: brightness(0.9);
	}

	.secondary {
		background: var(--button-secondary-background-fill);
		color: var(--button-secondary-text-color);
		border: 1px solid var(--button-secondary-border-color);
	}

	.secondary:hover:not(:disabled) {
		background: var(--button-secondary-background-fill-hover);
		border-color: var(--button-secondary-border-color-hover);
	}

	.secondary:active:not(:disabled) {
		background: var(--button-secondary-background-fill-hover);
		filter: brightness(0.9);
	}

	.stop {
		background: var(--error-border-color);
		color: var(--button-primary-text-color);
	}

	.stop:hover:not(:disabled) {
		background: var(--error-text-color);
	}

	.stop:active:not(:disabled) {
		background: var(--error-text-color);
		filter: brightness(0.9);
	}
</style>

