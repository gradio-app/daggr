<script lang="ts">
	import type { GradioComponentData, ItemListItem } from '../types';

	interface Props {
		nodeId: string;
		schema: GradioComponentData[];
		items: ItemListItem[];
		getValue: (nodeId: string, itemIndex: number, fieldName: string) => any;
		onchange?: (nodeId: string, itemIndex: number, fieldName: string, value: any) => void;
	}

	let { nodeId, schema, items, getValue, onchange }: Props = $props();

	function handleFieldChange(itemIndex: number, fieldName: string, value: any) {
		onchange?.(nodeId, itemIndex, fieldName, value);
	}
</script>

<div class="item-list-section">
	<div class="item-list-header">
		<span class="item-list-title">Items ({items.length})</span>
	</div>
	<div class="item-list-items">
		{#each items as item (item.index)}
			<div class="item-list-item">
				<div class="item-list-fields">
					{#each schema as comp (comp.port_name)}
						{#if comp.component === 'dropdown'}
							{@const currentValue = getValue(nodeId, item.index, comp.port_name)}
							<select
								class="gr-select"
								onchange={(e) => handleFieldChange(item.index, comp.port_name, (e.target as HTMLSelectElement).value)}
							>
								{#each comp.props?.choices || [] as choice}
									<option value={choice} selected={choice === currentValue}>{choice}</option>
								{/each}
							</select>
						{:else if comp.component === 'textbox' || comp.component === 'text'}
							<div class="gr-textbox-wrap item-list-textbox">
								{#if comp.props?.lines && comp.props.lines > 1}
									<textarea
										class="gr-input"
										rows={comp.props?.lines || 2}
										value={getValue(nodeId, item.index, comp.port_name)}
										oninput={(e) => handleFieldChange(item.index, comp.port_name, (e.target as HTMLTextAreaElement).value)}
									></textarea>
								{:else}
									<input
										type="text"
										class="gr-input"
										value={getValue(nodeId, item.index, comp.port_name)}
										oninput={(e) => handleFieldChange(item.index, comp.port_name, (e.target as HTMLInputElement).value)}
									/>
								{/if}
							</div>
						{/if}
					{/each}
				</div>
			</div>
		{/each}
	</div>
</div>

<style>
	.item-list-section {
		border-top: 1px solid color-mix(in srgb, var(--primary-500, #22c55e) 20%, transparent);
		background: color-mix(in srgb, var(--primary-500, #22c55e) 3%, transparent);
	}

	.item-list-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 10px;
		border-bottom: 1px solid color-mix(in srgb, var(--primary-500, #22c55e) 10%, transparent);
	}

	.item-list-title {
		font-size: 10px;
		font-weight: 600;
		color: var(--primary-500, #22c55e);
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.item-list-items {
		max-height: 300px;
		overflow-y: auto;
	}

	.item-list-item {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		padding: 8px 10px;
		border-bottom: 1px solid color-mix(in srgb, var(--primary-500, #22c55e) 8%, transparent);
	}

	.item-list-item:last-child {
		border-bottom: none;
	}

	.item-list-fields {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.gr-select {
		width: 100%;
		padding: 6px 8px;
		font-size: 11px;
		background: color-mix(in srgb, var(--primary-500, #22c55e) 8%, transparent);
		border: 1px solid color-mix(in srgb, var(--primary-500, #22c55e) 20%, transparent);
		border-radius: 4px;
		color: var(--body-text-color);
		cursor: pointer;
	}

	.gr-select:focus {
		outline: none;
		border-color: color-mix(in srgb, var(--primary-500, #22c55e) 50%, transparent);
	}

	.gr-textbox-wrap {
		background: var(--block-background-fill);
		border: 1px solid var(--border-color-primary);
		border-radius: 6px;
		overflow: hidden;
	}

	.item-list-textbox {
		flex: 1;
	}

	.gr-input {
		width: 100%;
		padding: 6px 10px;
		font-size: 11px;
		font-family: inherit;
		color: var(--body-text-color);
		background: transparent;
		border: none;
		outline: none;
		box-sizing: border-box;
	}

	.item-list-textbox textarea.gr-input {
		resize: vertical;
		min-height: 40px;
	}
</style>

