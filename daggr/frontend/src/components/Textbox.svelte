<script lang="ts">
	interface Props {
		label: string;
		placeholder?: string;
		lines?: number;
		disabled?: boolean;
		value: any;
		oninput?: (value: string) => void;
	}

	let { label, placeholder = '', lines = 1, disabled = false, value, oninput }: Props = $props();

	function handleInput(e: Event) {
		const target = e.target as HTMLInputElement | HTMLTextAreaElement;
		oninput?.(target.value);
	}
</script>

<div class="gr-textbox-wrap">
	<span class="gr-label">{label}</span>
	{#if lines > 1}
		<textarea
			class="gr-input"
			{placeholder}
			rows={lines}
			{disabled}
			{value}
			oninput={handleInput}
		></textarea>
	{:else}
		<input
			type="text"
			class="gr-input"
			{placeholder}
			{disabled}
			{value}
			oninput={handleInput}
		/>
	{/if}
</div>

<style>
	.gr-textbox-wrap {
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

	.gr-input {
		width: 100%;
		padding: 4px 10px 8px;
		font-size: 11px;
		font-family: inherit;
		color: var(--body-text-color);
		background: transparent;
		border: none;
		outline: none;
		box-sizing: border-box;
	}

	.gr-input::placeholder {
		color: var(--input-placeholder-color);
	}

	.gr-textbox-wrap:focus-within {
		border-color: var(--color-accent);
	}

	.gr-input:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	textarea.gr-input {
		resize: none;
		min-height: 36px;
		line-height: 1.4;
	}
</style>

