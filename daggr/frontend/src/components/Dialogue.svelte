<script lang="ts">
	interface DialogueLine {
		speaker: string;
		text: string;
	}

	interface Props {
		label: string;
		value: DialogueLine[];
		speakers?: string[];
		editable?: boolean;
		onchange?: (value: DialogueLine[]) => void;
	}

	let { 
		label, 
		value = [], 
		speakers = [],
		editable = true, 
		onchange 
	}: Props = $props();

	let containerEl: HTMLDivElement | null = $state(null);
	let copySuccess = $state(false);
	let isFullscreen = $state(false);

	const baseColors = [
		'rgba(239, 68, 68, 0.15)',
		'rgba(59, 130, 246, 0.15)',
		'rgba(34, 197, 94, 0.15)',
		'rgba(168, 85, 247, 0.15)',
		'rgba(251, 191, 36, 0.15)',
		'rgba(236, 72, 153, 0.15)',
		'rgba(20, 184, 166, 0.15)',
		'rgba(99, 102, 241, 0.15)',
	];

	let uniqueSpeakers = $derived.by(() => {
		const fromValue = value.map(line => line.speaker);
		const all = [...new Set([...speakers, ...fromValue])];
		return all.filter(s => s && s.trim());
	});

	let speakerColorMap = $derived.by(() => {
		const map: Record<string, string> = {};
		uniqueSpeakers.forEach((speaker, idx) => {
			map[speaker] = baseColors[idx % baseColors.length];
		});
		return map;
	});

	function getSpeakerColor(speaker: string): string {
		return speakerColorMap[speaker] || baseColors[0];
	}

	function copyDialogue() {
		const text = value.map(line => `${line.speaker}: ${line.text}`).join('\n');
		navigator.clipboard.writeText(text).then(() => {
			copySuccess = true;
			setTimeout(() => copySuccess = false, 1500);
		});
	}

	function openFullscreen() {
		if (!containerEl) return;
		if (containerEl.requestFullscreen) {
			containerEl.requestFullscreen();
		} else if ((containerEl as any).webkitRequestFullscreen) {
			(containerEl as any).webkitRequestFullscreen();
		}
	}

	function handleFullscreenChange() {
		isFullscreen = !!document.fullscreenElement;
	}

	function addLine(index: number) {
		const newSpeaker = uniqueSpeakers.length > 0 ? uniqueSpeakers[0] : 'Speaker 1';
		const newValue = [
			...value.slice(0, index + 1),
			{ speaker: newSpeaker, text: '' },
			...value.slice(index + 1)
		];
		onchange?.(newValue);
	}

	function removeLine(index: number) {
		if (value.length <= 1) return;
		const newValue = [...value.slice(0, index), ...value.slice(index + 1)];
		onchange?.(newValue);
	}

	function updateSpeaker(index: number, speaker: string) {
		const newValue = [...value];
		newValue[index] = { ...newValue[index], speaker };
		onchange?.(newValue);
	}

	function updateText(index: number, text: string) {
		const newValue = [...value];
		newValue[index] = { ...newValue[index], text };
		onchange?.(newValue);
	}

	function handleSpeakerChange(e: Event, index: number) {
		const select = e.target as HTMLSelectElement;
		updateSpeaker(index, select.value);
	}

	function handleTextChange(e: Event, index: number) {
		const textarea = e.target as HTMLTextAreaElement;
		updateText(index, textarea.value);
	}

	let availableSpeakers = $derived.by(() => {
		if (uniqueSpeakers.length > 0) return uniqueSpeakers;
		return ['Speaker 1', 'Speaker 2', 'Speaker 3'];
	});
</script>

<svelte:document onfullscreenchange={handleFullscreenChange} />

<div class="gr-dialogue-wrap" class:fullscreen={isFullscreen} bind:this={containerEl}>
	<div class="gr-header">
		<span class="gr-label">{label}</span>
		<div class="dialogue-actions">
			<button class="action-btn" onclick={openFullscreen} title="View fullscreen">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
				</svg>
			</button>
			<button class="action-btn" class:success={copySuccess} onclick={copyDialogue} title="Copy dialogue">
				{#if copySuccess}
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<polyline points="20 6 9 17 4 12"/>
					</svg>
				{:else}
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
						<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
					</svg>
				{/if}
			</button>
			{#if editable}
				<button class="action-btn" onclick={() => addLine(value.length - 1)} title="Add line">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<line x1="12" y1="5" x2="12" y2="19"/>
						<line x1="5" y1="12" x2="19" y2="12"/>
					</svg>
				</button>
			{/if}
		</div>
	</div>

	<div class="dialogue-container">
		{#if value.length === 0}
			<div class="gr-empty">No dialogue</div>
		{:else}
			{#each value as line, i}
				<div class="dialogue-line" style="--speaker-color: {getSpeakerColor(line.speaker)}">
					<div class="speaker-wrapper">
						{#if editable}
							<select 
								class="speaker-select"
								value={line.speaker}
								onchange={(e) => handleSpeakerChange(e, i)}
							>
								{#each availableSpeakers as speaker}
									<option value={speaker}>{speaker}</option>
								{/each}
								{#if !availableSpeakers.includes(line.speaker)}
									<option value={line.speaker}>{line.speaker}</option>
								{/if}
							</select>
						{:else}
							<span class="speaker-name">{line.speaker}</span>
						{/if}
					</div>
					<div class="text-wrapper">
						{#if editable}
							<textarea
								class="text-input"
								value={line.text}
								placeholder="Enter text..."
								oninput={(e) => handleTextChange(e, i)}
								rows="1"
							></textarea>
						{:else}
							<span class="text-content">{line.text}</span>
						{/if}
					</div>
					{#if editable && value.length > 1}
						<button class="remove-btn" onclick={() => removeLine(i)} title="Remove line">
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<line x1="18" y1="6" x2="6" y2="18"/>
								<line x1="6" y1="6" x2="18" y2="18"/>
							</svg>
						</button>
					{/if}
				</div>
			{/each}
		{/if}
	</div>
</div>

<style>
	.gr-dialogue-wrap {
		background: #1a1a1a;
		border: 1px solid #333;
		border-radius: 6px;
		overflow: hidden;
	}

	.gr-dialogue-wrap.fullscreen {
		border-radius: 0;
		display: flex;
		flex-direction: column;
		height: 100vh;
	}

	.gr-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px;
	}

	.gr-label {
		font-size: 10px;
		font-weight: 400;
		color: #888;
		padding-left: 4px;
	}

	.dialogue-actions {
		display: flex;
		gap: 4px;
	}

	.action-btn {
		width: 20px;
		height: 20px;
		padding: 3px;
		border: none;
		background: rgba(255, 255, 255, 0.08);
		border-radius: 4px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.15s;
	}

	.action-btn svg {
		width: 12px;
		height: 12px;
		color: #888;
	}

	.action-btn:hover {
		background: rgba(255, 255, 255, 0.15);
	}

	.action-btn:hover svg {
		color: #fff;
	}

	.action-btn.success svg {
		color: #22c55e;
	}

	.dialogue-container {
		padding: 6px;
		max-height: 200px;
		overflow-y: auto;
	}

	.gr-dialogue-wrap.fullscreen .dialogue-container {
		max-height: none;
		flex: 1;
		padding: 16px;
	}

	.dialogue-line {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 8px;
		margin-bottom: 3px;
		background: var(--speaker-color);
		border-radius: 4px;
		min-height: 28px;
	}

	.dialogue-line:last-child {
		margin-bottom: 0;
	}

	.speaker-wrapper {
		flex-shrink: 0;
		min-width: 50px;
		display: flex;
		align-items: center;
	}

	.speaker-select {
		width: 100%;
		padding: 2px 4px;
		font-size: 10px;
		font-weight: 600;
		color: #fff;
		background: transparent;
		border: none;
		border-radius: 3px;
		outline: none;
		cursor: pointer;
		transition: background 0.15s;
		appearance: none;
		-webkit-appearance: none;
		-moz-appearance: none;
	}

	.speaker-select:focus,
	.speaker-select:hover {
		background: rgba(0, 0, 0, 0.2);
	}

	.speaker-select option {
		background: #2a2a2a;
		color: #e5e7eb;
	}

	.speaker-name {
		font-size: 10px;
		font-weight: 600;
		color: #fff;
	}

	.text-wrapper {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
	}

	.text-input {
		width: 100%;
		padding: 2px 6px;
		font-size: 11px;
		color: #e5e7eb;
		background: transparent;
		border: none;
		border-radius: 3px;
		outline: none;
		resize: none;
		font-family: inherit;
		line-height: 1.4;
		min-height: 20px;
		box-sizing: border-box;
		transition: background 0.15s;
	}

	.text-input:focus,
	.text-input:hover {
		background: rgba(0, 0, 0, 0.15);
	}

	.text-input::placeholder {
		color: rgba(255, 255, 255, 0.3);
	}

	.text-content {
		font-size: 11px;
		color: #e5e7eb;
		line-height: 1.4;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.remove-btn {
		width: 16px;
		height: 16px;
		padding: 2px;
		border: none;
		background: transparent;
		border-radius: 3px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		opacity: 0.3;
		transition: opacity 0.15s;
		flex-shrink: 0;
	}

	.remove-btn svg {
		width: 10px;
		height: 10px;
		color: #fff;
	}

	.remove-btn:hover {
		opacity: 1;
	}

	.remove-btn:hover svg {
		color: #ef4444;
	}

	.gr-empty {
		font-size: 11px;
		color: #555;
		font-style: italic;
		padding: 6px;
		text-align: center;
	}

	.gr-dialogue-wrap.fullscreen .dialogue-line {
		padding: 12px 16px;
		margin-bottom: 8px;
	}

	.gr-dialogue-wrap.fullscreen .speaker-wrapper {
		min-width: 120px;
	}

	.gr-dialogue-wrap.fullscreen .speaker-select,
	.gr-dialogue-wrap.fullscreen .speaker-name {
		font-size: 13px;
		padding: 8px 12px;
	}

	.gr-dialogue-wrap.fullscreen .text-input,
	.gr-dialogue-wrap.fullscreen .text-content {
		font-size: 14px;
		padding: 8px 12px;
		min-height: 38px;
	}
</style>
