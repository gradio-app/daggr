<script lang="ts">
	import Audio from './Audio.svelte';
	import Textbox from './Textbox.svelte';
	import Image from './Image.svelte';
	import Dialogue from './Dialogue.svelte';
	import Video from './Video.svelte';
	import File from './File.svelte';
	import Dataframe from './Dataframe.svelte';
	import Gallery from './Gallery.svelte';
	import Code from './Code.svelte';
	import Json from './Json.svelte';
	import Slider from './Slider.svelte';
	import Radio from './Radio.svelte';
	import Dropdown from './Dropdown.svelte';
	import CheckboxGroup from './CheckboxGroup.svelte';
	import ColorPicker from './ColorPicker.svelte';
	import Label from './Label.svelte';
	import HighlightedText from './HighlightedText.svelte';
	import Markdown from './Markdown.svelte';
	import type { GradioComponentData } from '../types';

	interface Props {
		comp: GradioComponentData;
		nodeId: string;
		isInputNode: boolean;
		value: any;
		onchange?: (portName: string, value: any) => void;
	}

	let { comp, nodeId, isInputNode, value, onchange }: Props = $props();

	function handleNumberInput(e: Event) {
		const target = e.target as HTMLInputElement;
		onchange?.(comp.port_name, parseFloat(target.value));
	}

	function handleCheckboxChange(e: Event) {
		const target = e.target as HTMLInputElement;
		onchange?.(comp.port_name, target.checked);
	}
</script>

<div class="embedded-component">
	{#if comp.component === 'textbox' || comp.component === 'text'}
		<Textbox
			label={comp.props?.label || comp.port_name}
			placeholder={comp.props?.placeholder || ''}
			lines={comp.props?.lines || 1}
			disabled={!isInputNode}
			{value}
			oninput={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'number'}
		<div class="gr-textbox-wrap">
			<span class="gr-label">{comp.props?.label || comp.port_name}</span>
			<input
				type="number"
				class="gr-input"
				disabled={!isInputNode}
				{value}
				oninput={handleNumberInput}
			/>
		</div>
	{:else if comp.component === 'checkbox'}
		<label class="gr-checkbox-wrap">
			<input
				type="checkbox"
				disabled={!isInputNode}
				checked={value}
				onchange={handleCheckboxChange}
			/>
			<span class="gr-check-label">{comp.props?.label || comp.port_name}</span>
		</label>
	{:else if comp.component === 'markdown'}
		<Markdown
			label={comp.props?.label || comp.port_name}
			value={value || ''}
			showLabel={true}
		/>
	{:else if comp.component === 'html'}
		<div class="gr-textbox-wrap">
			<span class="gr-label">{comp.props?.label || comp.port_name}</span>
			<div class="gr-html">{@html comp.value || ''}</div>
		</div>
	{:else if comp.component === 'json'}
		<Json
			label={comp.props?.label || comp.port_name}
			value={value}
			open={comp.props?.open ?? 2}
		/>
	{:else if comp.component === 'audio'}
		<Audio
			label={comp.props?.label || comp.port_name}
			value={value}
			id="{nodeId}_{comp.port_name}"
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'image'}
		<Image
			label={comp.props?.label || comp.port_name}
			value={value}
			editable={isInputNode}
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'video'}
		<Video
			label={comp.props?.label || comp.port_name}
			value={value}
			editable={isInputNode}
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'file'}
		<File
			label={comp.props?.label || comp.port_name}
			value={value}
			editable={isInputNode}
			fileTypes={comp.props?.file_types}
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'dataframe'}
		<Dataframe
			label={comp.props?.label || comp.port_name}
			value={value}
			editable={isInputNode}
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'gallery'}
		<Gallery
			label={comp.props?.label || comp.port_name}
			value={value}
		/>
	{:else if comp.component === 'dialogue'}
		<Dialogue
			label={comp.props?.label || comp.port_name}
			value={Array.isArray(value) ? value : (value ? [value] : [])}
			speakers={comp.props?.speakers || []}
			editable={true}
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'code'}
		<Code
			label={comp.props?.label || comp.port_name}
			value={value || ''}
			language={comp.props?.language || 'text'}
			editable={isInputNode}
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'slider'}
		<Slider
			label={comp.props?.label || comp.port_name}
			value={value ?? comp.props?.value ?? 0}
			min={comp.props?.minimum ?? 0}
			max={comp.props?.maximum ?? 100}
			step={comp.props?.step ?? 1}
			disabled={!isInputNode}
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'radio'}
		<Radio
			label={comp.props?.label || comp.port_name}
			choices={comp.props?.choices || []}
			value={value}
			disabled={!isInputNode}
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'dropdown'}
		<Dropdown
			label={comp.props?.label || comp.port_name}
			choices={comp.props?.choices || []}
			value={value}
			disabled={!isInputNode}
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'checkboxgroup'}
		<CheckboxGroup
			label={comp.props?.label || comp.port_name}
			choices={comp.props?.choices || []}
			value={value || []}
			disabled={!isInputNode}
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'colorpicker'}
		<ColorPicker
			label={comp.props?.label || comp.port_name}
			value={value || '#000000'}
			disabled={!isInputNode}
			onchange={(v) => onchange?.(comp.port_name, v)}
		/>
	{:else if comp.component === 'label'}
		<Label
			label={comp.props?.label || comp.port_name}
			value={value}
		/>
	{:else if comp.component === 'highlightedtext'}
		<HighlightedText
			label={comp.props?.label || comp.port_name}
			value={value}
		/>
	{:else}
		<div class="gr-fallback">
			<span class="fallback-type">{comp.component}</span>
			{#if comp.value}
				<pre>{typeof comp.value === 'string' ? comp.value : JSON.stringify(comp.value, null, 2)}</pre>
			{/if}
		</div>
	{/if}
</div>

<style>
	.embedded-component {
		margin-bottom: 8px;
	}

	.embedded-component:last-child {
		margin-bottom: 0;
	}

	.gr-textbox-wrap {
		background: #1a1a1a;
		border: 1px solid #333;
		border-radius: 6px;
		overflow: hidden;
	}

	.gr-label {
		display: block;
		font-size: 10px;
		font-weight: 400;
		color: #888;
		padding: 6px 10px 0;
	}

	.gr-input {
		width: 100%;
		padding: 4px 10px 8px;
		font-size: 11px;
		font-family: inherit;
		color: #e5e7eb;
		background: transparent;
		border: none;
		outline: none;
		box-sizing: border-box;
	}

	.gr-input::placeholder {
		color: #555;
	}

	.gr-textbox-wrap:focus-within {
		border-color: #f97316;
	}

	.gr-input:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	.gr-checkbox-wrap {
		display: flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
		padding: 6px 0;
	}

	.gr-checkbox-wrap input[type="checkbox"] {
		width: 14px;
		height: 14px;
		accent-color: #f97316;
		cursor: pointer;
	}

	.gr-check-label {
		font-size: 11px;
		color: #e5e7eb;
	}

	.gr-markdown,
	.gr-html {
		font-size: 11px;
		color: #d1d5db;
		line-height: 1.4;
		padding: 6px 10px 8px;
		max-height: 100px;
		overflow: auto;
	}

	.gr-html :global(strong), .gr-html :global(b) {
		font-weight: 600;
		color: #f3f4f6;
	}

	.gr-html :global(em), .gr-html :global(i) {
		font-style: italic;
	}

	.gr-html :global(a) {
		color: #f97316;
		text-decoration: underline;
	}

	.gr-html :global(code) {
		font-family: 'SF Mono', Monaco, Consolas, monospace;
		background: rgba(249, 115, 22, 0.1);
		padding: 1px 4px;
		border-radius: 3px;
		font-size: 10px;
	}

	.gr-json {
		font-size: 10px;
		font-family: 'SF Mono', Monaco, Consolas, monospace;
		color: #9ca3af;
		padding: 6px 10px 8px;
		max-height: 100px;
		overflow: auto;
		margin: 0;
		white-space: pre-wrap;
		word-break: break-all;
	}

	.gr-fallback {
		font-size: 10px;
		color: #9ca3af;
		background: #1a1a1a;
		border: 1px solid #333;
		padding: 8px 10px;
		border-radius: 6px;
	}

	.gr-fallback .fallback-type {
		display: inline-block;
		color: #666;
		font-style: italic;
		font-size: 9px;
		background: #2a2a2a;
		padding: 2px 6px;
		border-radius: 4px;
		margin-bottom: 4px;
	}

	.gr-fallback pre {
		margin: 0;
		font-size: 9px;
		white-space: pre-wrap;
		word-break: break-all;
		max-height: 60px;
		overflow: auto;
	}
</style>

