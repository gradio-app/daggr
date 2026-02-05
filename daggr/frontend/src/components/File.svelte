<script lang="ts">
	interface FileValue {
		name: string;
		size: number;
		url?: string;
		data?: File | Blob;
	}

	interface Props {
		label: string;
		value: FileValue | FileValue[] | null;
		fileTypes?: string[];
		multiple?: boolean;
		editable?: boolean;
		onchange?: (value: FileValue | FileValue[] | null) => void;
	}

	let { 
		label, 
		value, 
		fileTypes, 
		multiple = false, 
		editable = true, 
		onchange 
	}: Props = $props();

	let fileInputEl: HTMLInputElement | null = $state(null);
	let isDragging = $state(false);

	function normalizeFileValue(v: any): FileValue {
		if (typeof v === 'string') {
			const name = v.split('/').pop() || 'file';
			return { name, size: 0, url: v };
		}
		return v;
	}

	let files = $derived.by(() => {
		if (!value) return [];
		const arr = Array.isArray(value) ? value : [value];
		return arr.map(normalizeFileValue);
	});

	let acceptStr = $derived(fileTypes?.join(',') || '*');

	function triggerUpload() {
		fileInputEl?.click();
	}

	function handleFileSelect(e: Event) {
		const target = e.target as HTMLInputElement;
		const selectedFiles = target.files;
		if (selectedFiles && selectedFiles.length > 0) {
			processFiles(Array.from(selectedFiles));
		}
		target.value = '';
	}

	function processFiles(fileList: File[]) {
		const newFiles: FileValue[] = fileList.map(f => ({
			name: f.name,
			size: f.size,
			url: URL.createObjectURL(f),
			data: f
		}));

		if (multiple) {
			onchange?.([...files, ...newFiles]);
		} else {
			onchange?.(newFiles[0]);
		}
	}

	function removeFile(index: number) {
		if (multiple) {
			const newFiles = files.filter((_, i) => i !== index);
			onchange?.(newFiles.length > 0 ? newFiles : null);
		} else {
			onchange?.(null);
		}
	}

	function clearAll() {
		onchange?.(null);
	}

	function formatSize(bytes: number): string {
		if (!bytes) return '';
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		if (editable) isDragging = true;
	}

	function handleDragLeave() {
		isDragging = false;
	}

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		isDragging = false;
		if (!editable) return;

		const droppedFiles = e.dataTransfer?.files;
		if (droppedFiles && droppedFiles.length > 0) {
			processFiles(Array.from(droppedFiles));
		}
	}

	async function downloadFile(file: FileValue) {
		const url = file.url || (file.data ? URL.createObjectURL(file.data) : null);
		if (!url) return;

		const link = document.createElement('a');
		link.href = url;
		link.download = file.name;
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	}
</script>

<div 
	class="gr-file-wrap"
	class:dragging={isDragging}
	ondragover={handleDragOver}
	ondragleave={handleDragLeave}
	ondrop={handleDrop}
>
	<input
		bind:this={fileInputEl}
		type="file"
		accept={acceptStr}
		{multiple}
		style="display: none"
		onchange={handleFileSelect}
	/>

	<div class="gr-header">
		<span class="gr-label">{label}</span>
		<div class="file-actions">
			{#if editable}
				<button class="action-btn" onclick={triggerUpload} title="Upload file">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
						<polyline points="17 8 12 3 7 8"/>
						<line x1="12" y1="3" x2="12" y2="15"/>
					</svg>
				</button>
				{#if files.length > 0}
					<button class="action-btn" onclick={clearAll} title="Clear all">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<line x1="18" y1="6" x2="6" y2="18"/>
							<line x1="6" y1="6" x2="18" y2="18"/>
						</svg>
					</button>
				{/if}
			{/if}
		</div>
	</div>

	{#if files.length > 0}
		<div class="file-list">
			{#each files as file, index}
				<div class="file-item">
					<div class="file-icon">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
							<polyline points="14 2 14 8 20 8"/>
						</svg>
					</div>
					<div class="file-info">
						<span class="file-name">{file.name}</span>
						<span class="file-size">{formatSize(file.size)}</span>
					</div>
					<div class="file-item-actions">
						<button class="item-btn" onclick={() => downloadFile(file)} title="Download">
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
								<polyline points="7 10 12 15 17 10"/>
								<line x1="12" y1="15" x2="12" y2="3"/>
							</svg>
						</button>
						{#if editable}
							<button class="item-btn" onclick={() => removeFile(index)} title="Remove">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<line x1="18" y1="6" x2="6" y2="18"/>
									<line x1="6" y1="6" x2="18" y2="18"/>
								</svg>
							</button>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{:else if editable}
		<div class="drop-zone">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
				<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
				<polyline points="17 8 12 3 7 8"/>
				<line x1="12" y1="3" x2="12" y2="15"/>
			</svg>
			<span>Drop files here or click to upload</span>
		</div>
	{:else}
		<div class="gr-empty">No file</div>
	{/if}
</div>

<style>
	.gr-file-wrap {
		background: var(--block-background-fill);
		border: 1px solid var(--border-color-primary);
		border-radius: 6px;
		overflow: hidden;
		transition: border-color 0.15s;
	}

	.gr-file-wrap.dragging {
		border-color: var(--color-accent);
		border-style: dashed;
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
		color: var(--body-text-color-subdued);
		padding-left: 4px;
	}

	.file-actions {
		display: flex;
		gap: 4px;
	}

	.action-btn {
		width: 20px;
		height: 20px;
		padding: 3px;
		border: none;
		background: color-mix(in srgb, var(--body-text-color) 8%, transparent);
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
		color: var(--body-text-color-subdued);
	}

	.action-btn:hover {
		background: color-mix(in srgb, var(--body-text-color) 15%, transparent);
	}

	.action-btn:hover svg {
		color: var(--body-text-color);
	}

	.file-list {
		padding: 0 6px 6px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.file-item {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 8px;
		background: var(--input-background-fill);
		border-radius: 4px;
	}

	.file-icon {
		width: 24px;
		height: 24px;
		color: var(--neutral-500);
		flex-shrink: 0;
	}

	.file-icon svg {
		width: 100%;
		height: 100%;
	}

	.file-info {
		flex: 1;
		min-width: 0;
	}

	.file-name {
		display: block;
		font-size: 11px;
		color: var(--body-text-color);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.file-size {
		font-size: 10px;
		color: var(--neutral-500);
	}

	.file-item-actions {
		display: flex;
		gap: 2px;
	}

	.item-btn {
		width: 18px;
		height: 18px;
		padding: 2px;
		border: none;
		background: transparent;
		border-radius: 3px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.15s;
	}

	.item-btn svg {
		width: 12px;
		height: 12px;
		color: var(--neutral-500);
	}

	.item-btn:hover {
		background: color-mix(in srgb, var(--body-text-color) 10%, transparent);
	}

	.item-btn:hover svg {
		color: var(--body-text-color);
	}

	.drop-zone {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 8px;
		padding: 20px;
		color: var(--input-placeholder-color);
		cursor: pointer;
	}

	.drop-zone svg {
		width: 32px;
		height: 32px;
	}

	.drop-zone span {
		font-size: 11px;
	}

	.drop-zone:hover {
		color: var(--body-text-color-subdued);
	}

	.gr-empty {
		font-size: 11px;
		color: var(--input-placeholder-color);
		font-style: italic;
		padding: 6px;
		text-align: center;
	}
</style>

