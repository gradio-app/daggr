<script lang="ts">
	interface Props {
		label: string;
		choices: [string, string | number][];
		value: string | number | null;
		disabled?: boolean;
		filterable?: boolean;
		allowCustomValue?: boolean;
		placeholder?: string;
		onchange?: (value: string | number | null) => void;
	}

	let { 
		label, 
		choices, 
		value, 
		disabled = false, 
		filterable = true,
		allowCustomValue = false,
		placeholder = 'Select...',
		onchange 
	}: Props = $props();

	let isOpen = $state(false);
	let inputEl: HTMLInputElement | null = $state(null);
	let inputWrapEl: HTMLDivElement | null = $state(null);
	let filterText = $state('');
	let dropdownPosition = $state({ top: 0, left: 0, width: 0 });

	let choicesNames = $derived(choices.map(c => c[0]));
	let choicesValues = $derived(choices.map(c => c[1]));

	let displayText = $derived.by(() => {
		if (value === null || value === undefined) return '';
		const idx = choicesValues.indexOf(value);
		if (idx !== -1) return choicesNames[idx];
		if (allowCustomValue) return String(value);
		return '';
	});

	let filteredChoices = $derived.by(() => {
		if (!filterText) return choices;
		const lower = filterText.toLowerCase();
		return choices.filter(([name]) => name.toLowerCase().includes(lower));
	});

	function updatePosition() {
		if (inputWrapEl) {
			const rect = inputWrapEl.getBoundingClientRect();
			dropdownPosition = {
				top: rect.bottom + 2,
				left: rect.left,
				width: rect.width
			};
		}
	}

	function handleSelect(internalValue: string | number) {
		onchange?.(internalValue);
		isOpen = false;
		filterText = '';
	}

	function handleInputFocus() {
		if (!disabled) {
			updatePosition();
			isOpen = true;
			filterText = '';
		}
	}

	function handleInputBlur() {
		setTimeout(() => {
			isOpen = false;
			if (allowCustomValue && filterText) {
				onchange?.(filterText);
			}
			filterText = '';
		}, 150);
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			isOpen = false;
			filterText = '';
			inputEl?.blur();
		} else if (e.key === 'Enter' && filteredChoices.length > 0) {
			handleSelect(filteredChoices[0][1]);
		}
	}
</script>

<svelte:window onscroll={updatePosition} onresize={updatePosition} />

<div class="gr-dropdown-wrap">
	<span class="gr-label">{label}</span>
	<div class="dropdown-container">
		<div class="input-wrap" bind:this={inputWrapEl}>
			<input
				bind:this={inputEl}
				type="text"
				class="dropdown-input"
				placeholder={displayText || placeholder}
				value={isOpen ? filterText : displayText}
				{disabled}
				readonly={!filterable}
				onfocus={handleInputFocus}
				onblur={handleInputBlur}
				oninput={(e) => filterText = (e.target as HTMLInputElement).value}
				onkeydown={handleKeyDown}
			/>
			<button class="dropdown-arrow" class:open={isOpen} {disabled} tabindex="-1">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<polyline points="6 9 12 15 18 9"/>
				</svg>
			</button>
		</div>
	</div>
</div>

{#if isOpen && filteredChoices.length > 0}
	<div 
		class="options-portal"
		style="top: {dropdownPosition.top}px; left: {dropdownPosition.left}px; width: {dropdownPosition.width}px;"
	>
		{#each filteredChoices as [displayValue, internalValue]}
			<button
				class="option"
				class:selected={value === internalValue}
				onmousedown={(e) => { e.preventDefault(); handleSelect(internalValue); }}
			>
				{displayValue}
			</button>
		{/each}
	</div>
{/if}

<style>
	.gr-dropdown-wrap {
		background: var(--block-background-fill);
		border: 1px solid var(--border-color-primary);
		border-radius: 6px;
		overflow: visible;
	}

	.gr-label {
		display: block;
		font-size: 10px;
		font-weight: 400;
		color: var(--body-text-color-subdued);
		padding: 6px 10px 0;
	}

	.dropdown-container {
		position: relative;
		padding: 4px 10px 8px;
	}

	.input-wrap {
		display: flex;
		align-items: center;
		background: var(--input-background-fill);
		border: 1px solid var(--input-border-color);
		border-radius: 4px;
		transition: border-color 0.15s;
	}

	.input-wrap:focus-within {
		border-color: var(--color-accent);
	}

	.dropdown-input {
		flex: 1;
		background: transparent;
		border: none;
		padding: 6px 8px;
		font-size: 11px;
		color: var(--body-text-color);
		outline: none;
		min-width: 0;
	}

	.dropdown-input::placeholder {
		color: var(--input-placeholder-color);
	}

	.dropdown-input:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.dropdown-arrow {
		width: 24px;
		height: 24px;
		padding: 4px;
		background: transparent;
		border: none;
		cursor: pointer;
		color: var(--neutral-500);
		transition: transform 0.15s;
		flex-shrink: 0;
	}

	.dropdown-arrow:disabled {
		cursor: not-allowed;
	}

	.dropdown-arrow.open {
		transform: rotate(180deg);
	}

	.dropdown-arrow svg {
		width: 100%;
		height: 100%;
	}

	.options-portal {
		position: fixed;
		background: var(--background-fill-secondary);
		border: 1px solid var(--border-color-primary);
		border-radius: 4px;
		max-height: 150px;
		overflow-y: auto;
		z-index: 10000;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
	}

	.option {
		display: block;
		width: 100%;
		padding: 6px 10px;
		text-align: left;
		background: transparent;
		border: none;
		font-size: 11px;
		color: var(--body-text-color);
		cursor: pointer;
		transition: background 0.1s;
	}

	.option:hover {
		background: var(--background-fill-primary);
	}

	.option.selected {
		background: color-mix(in srgb, var(--color-accent) 20%, transparent);
		color: var(--color-accent);
	}
</style>
