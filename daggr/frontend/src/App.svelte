<script lang="ts">
	import { onMount } from 'svelte';
	import { EmbeddedComponent, MapItemsSection, ItemListSection } from './components';
	import type { GraphNode, GraphEdge, CanvasData, GradioComponentData } from './types';

	interface Sheet {
		sheet_id: string;
		name: string;
		created_at: string;
		updated_at: string;
	}

	let canvasEl: HTMLDivElement;
	let transform = $state({ x: 0, y: 0, scale: 1 });
	let isPanning = $state(false);
	let startPan = $state({ x: 0, y: 0 });

	let graphData = $state<CanvasData | null>(null);
	let sessionId = $state<string | null>(null);
	let ws: WebSocket | null = null;
	let wsConnected = $state(false);
	let reconnectAttempts = 0;
	let maxReconnectAttempts = 10;
	let isConnecting = false;
	let reconnectTimer: number | null = null;

	let inputValues = $state<Record<string, Record<string, any>>>({});
	let runningNodes = $state<Set<string>>(new Set());
	let nodeResults = $state<Record<string, any[]>>({});
	let nodeInputsSnapshots = $state<Record<string, (Record<string, any> | null)[]>>({});
	let selectedResultIndex = $state<Record<string, number>>({});
	let itemListValues = $state<Record<string, Record<number, Record<string, any>>>>({});
	let selectedVariants = $state<Record<string, number>>({});
	let nodeExecutionTimes = $state<Record<string, number>>({});
	let nodeStartTimes = $state<Record<string, number>>({});
	let nodeAvgTimes = $state<Record<string, { total: number; count: number }>>({});
	let nodeErrors = $state<Record<string, string>>({});
	let timerTick = $state(0);
	let hfUser = $state<{ username: string; fullname: string; avatar_url: string } | null>(null);
	let nodeRunModes = $state<Record<string, 'step' | 'toHere'>>({});
	let runModeMenuOpen = $state<string | null>(null);
	let runModeVersion = $state(0);
	let highlightedNodes = $state<Set<string>>(new Set());

	let sheets = $state<Sheet[]>([]);
	let currentSheetId = $state<string | null>(null);
	let userId = $state<string | null>(null);
	let canPersist = $state(false);
	let isOnSpaces = $state(false);
	let sheetDropdownOpen = $state(false);
	let editingSheetName = $state(false);
	let editSheetNameValue = $state('');
	let saveDebounceTimer: number | null = null;
	let transformDebounceTimer: number | null = null;

	let showLoginTooltip = $state(false);
	let tokenInputValue = $state('');
	let loginLoading = $state(false);
	let loginError = $state('');
	let hasShownPersistencePrompt = $state(false);

	const HF_TOKEN_KEY = 'daggr_hf_token';

	function getStoredToken(): string | null {
		try {
			return localStorage.getItem(HF_TOKEN_KEY);
		} catch {
			return null;
		}
	}

	function storeToken(token: string) {
		try {
			localStorage.setItem(HF_TOKEN_KEY, token);
		} catch {
			console.warn('[daggr] Could not store token in localStorage');
		}
	}

	function clearStoredToken() {
		try {
			localStorage.removeItem(HF_TOKEN_KEY);
		} catch {
			console.warn('[daggr] Could not clear token from localStorage');
		}
	}

	let timerInterval: number | null = null;

	let nodes = $derived(graphData?.nodes || []);
	let edges = $derived(graphData?.edges || []);
	let currentSheet = $derived(sheets.find(s => s.sheet_id === currentSheetId));

	function startTimer() {
		if (timerInterval) return;
		timerInterval = window.setInterval(() => {
			timerTick++;
		}, 100);
	}

	function stopTimerIfNoRunning() {
		if (runningNodes.size === 0 && timerInterval) {
			clearInterval(timerInterval);
			timerInterval = null;
		}
	}

	const NODE_WIDTH = 280;
	const HEADER_HEIGHT = 36;
	const HEADER_BORDER = 1;
	const BODY_PADDING_TOP = 8;
	const PORT_ROW_HEIGHT = 22;
	const EMBEDDED_COMPONENT_HEIGHT = 60;

	function generateSessionId(): string {
		return 'session_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
	}

	async function fetchUserInfo() {
		try {
			const token = getStoredToken();
			const headers: Record<string, string> = {};
			if (token) {
				headers['Authorization'] = `Bearer ${token}`;
			}
			const response = await fetch('/api/user_info', { headers });
			if (response.ok) {
				const data = await response.json();
				hfUser = data.hf_user;
				userId = data.user_id;
				canPersist = data.can_persist;
				isOnSpaces = data.is_on_spaces;
				return data;
			}
		} catch (e) {
			console.log('[daggr] Could not fetch user info');
		}
		return null;
	}

	async function handleLogin() {
		if (!tokenInputValue.trim()) {
			loginError = 'Please enter a token';
			return;
		}
		loginLoading = true;
		loginError = '';
		try {
			const response = await fetch('/api/auth/login', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ token: tokenInputValue.trim() })
			});
			const data = await response.json();
			if (response.ok && data.success) {
				storeToken(tokenInputValue.trim());
				hfUser = data.hf_user;
				showLoginTooltip = false;
				tokenInputValue = '';
				await fetchUserInfo();
				await fetchSheets();
				
				if (sheets.length > 0) {
					currentSheetId = sheets[0].sheet_id;
				} else if (canPersist) {
					await createSheet('Sheet 1');
				}
				
				if (ws && wsConnected) {
					const token = getStoredToken();
					ws.send(JSON.stringify({ action: 'set_sheet', sheet_id: currentSheetId, hf_token: token }));
					ws.send(JSON.stringify({ action: 'get_graph', sheet_id: currentSheetId, hf_token: token }));
				}
			} else {
				loginError = data.error || 'Invalid token';
			}
		} catch (e) {
			loginError = 'Failed to verify token';
		} finally {
			loginLoading = false;
		}
	}

	async function handleLogout() {
		clearStoredToken();
		hfUser = null;
		await fetchUserInfo();
		await fetchSheets();
		
		if (sheets.length > 0) {
			currentSheetId = sheets[0].sheet_id;
		} else {
			currentSheetId = null;
		}
		
		if (ws && wsConnected) {
			ws.send(JSON.stringify({ action: 'set_sheet', sheet_id: currentSheetId, hf_token: null }));
			ws.send(JSON.stringify({ action: 'get_graph', sheet_id: currentSheetId, hf_token: null }));
		}
	}

	async function fetchSheets() {
		if (!canPersist) return;
		try {
			const token = getStoredToken();
			const headers: Record<string, string> = {};
			if (token) {
				headers['Authorization'] = `Bearer ${token}`;
			}
			const response = await fetch('/api/sheets', { headers });
			if (response.ok) {
				const data = await response.json();
				sheets = data.sheets || [];
			}
		} catch (e) {
			console.log('[daggr] Could not fetch sheets');
		}
	}

	async function createSheet(name?: string) {
		if (!canPersist) return;
		try {
			const token = getStoredToken();
			const headers: Record<string, string> = { 'Content-Type': 'application/json' };
			if (token) {
				headers['Authorization'] = `Bearer ${token}`;
			}
			const response = await fetch('/api/sheets', {
				method: 'POST',
				headers,
				body: JSON.stringify({ name })
			});
			if (response.ok) {
				const data = await response.json();
				const newSheet = data.sheet;
				sheets = [newSheet, ...sheets];
				await selectSheet(newSheet.sheet_id);
			}
		} catch (e) {
			console.error('[daggr] Failed to create sheet:', e);
		}
	}

	async function renameSheet(sheetId: string, newName: string) {
		try {
			const token = getStoredToken();
			const headers: Record<string, string> = { 'Content-Type': 'application/json' };
			if (token) {
				headers['Authorization'] = `Bearer ${token}`;
			}
			const response = await fetch(`/api/sheets/${sheetId}`, {
				method: 'PATCH',
				headers,
				body: JSON.stringify({ name: newName })
			});
			if (response.ok) {
				sheets = sheets.map(s => s.sheet_id === sheetId ? { ...s, name: newName } : s);
			}
		} catch (e) {
			console.error('[daggr] Failed to rename sheet:', e);
		}
	}

	async function deleteSheet(sheetId: string) {
		if (!confirm('Delete this sheet and all its data?')) return;
		try {
			const token = getStoredToken();
			const headers: Record<string, string> = {};
			if (token) {
				headers['Authorization'] = `Bearer ${token}`;
			}
			const response = await fetch(`/api/sheets/${sheetId}`, { method: 'DELETE', headers });
			if (response.ok) {
				sheets = sheets.filter(s => s.sheet_id !== sheetId);
				if (currentSheetId === sheetId) {
					if (sheets.length > 0) {
						await selectSheet(sheets[0].sheet_id);
					} else {
						await createSheet();
					}
				}
			}
		} catch (e) {
			console.error('[daggr] Failed to delete sheet:', e);
		}
	}

	async function selectSheet(sheetId: string) {
		currentSheetId = sheetId;
		nodeResults = {};
		selectedResultIndex = {};
		inputValues = {};
		itemListValues = {};
		selectedVariants = {};
		runningNodes = new Set();
		nodeStartTimes = {};
		nodeExecutionTimes = {};
		nodeErrors = {};
		if (timerInterval) {
			clearInterval(timerInterval);
			timerInterval = null;
		}
		if (transformDebounceTimer) {
			clearTimeout(transformDebounceTimer);
			transformDebounceTimer = null;
		}
		timerTick = 0;
		transform = { x: 0, y: 0, scale: 1 };
		
		if (ws && wsConnected) {
			const token = getStoredToken();
			ws.send(JSON.stringify({ action: 'set_sheet', sheet_id: sheetId, hf_token: token }));
			ws.send(JSON.stringify({ action: 'get_graph', sheet_id: sheetId, hf_token: token }));
		}
		
		sheetDropdownOpen = false;
	}

	function connectWebSocket() {
		if (isConnecting) return;
		if (reconnectAttempts >= maxReconnectAttempts) {
			console.error('[daggr] Max reconnection attempts reached');
			return;
		}
		
		isConnecting = true;
		
		if (!sessionId) {
			sessionId = generateSessionId();
		}
		
		const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
		const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;
		
		console.log('[daggr] Connecting to', wsUrl);
		
		try {
			ws = new WebSocket(wsUrl);
		} catch (e) {
			console.error('[daggr] Failed to create WebSocket:', e);
			isConnecting = false;
			scheduleReconnect();
			return;
		}
		
		ws.onopen = async () => {
			console.log('[daggr] WebSocket connected');
			isConnecting = false;
			wsConnected = true;
			reconnectAttempts = 0;
			
			const token = getStoredToken();
			if (canPersist && currentSheetId) {
				ws?.send(JSON.stringify({ action: 'get_graph', sheet_id: currentSheetId, hf_token: token }));
			} else {
				ws?.send(JSON.stringify({ action: 'get_graph', hf_token: token }));
			}
		};
		
		ws.onmessage = (event) => {
			const data = JSON.parse(event.data);
			handleMessage(data);
		};
		
		ws.onclose = () => {
			isConnecting = false;
			wsConnected = false;
			scheduleReconnect();
		};
		
		ws.onerror = () => {
			console.error('[daggr] WebSocket error');
			isConnecting = false;
		};
	}
	
	function scheduleReconnect() {
		if (reconnectTimer) return;
		reconnectAttempts++;
		const delay = reconnectAttempts === 1 ? 0 : reconnectAttempts <= 5 ? 50 : Math.min(1000 * Math.pow(2, reconnectAttempts - 5), 30000);
		console.log(`[daggr] Reconnecting in ${delay}ms (attempt ${reconnectAttempts}/${maxReconnectAttempts})`);
		reconnectTimer = window.setTimeout(() => {
			reconnectTimer = null;
			connectWebSocket();
		}, delay);
	}

	function handleMessage(data: any) {
		if (data.type === 'graph') {
			const newUserId = data.data.user_id;
			const newSheetId = data.data.sheet_id;
			const userOrSheetChanged = newUserId !== userId || newSheetId !== currentSheetId;
			
			if (userOrSheetChanged) {
				nodeResults = {};
				nodeInputsSnapshots = {};
				selectedResultIndex = {};
				nodeErrors = {};
				inputValues = {};
				itemListValues = {};
				selectedVariants = {};
				nodeExecutionTimes = {};
			}
			
			graphData = data.data;
			userId = newUserId;
			
			if (newSheetId) {
				currentSheetId = newSheetId;
			}
			
			if (data.data.nodes) {
				let hasNewErrors = false;
				for (const node of data.data.nodes) {
					if (node.validation_error) {
						nodeErrors[node.name] = node.validation_error;
						hasNewErrors = true;
					}
				}
				if (hasNewErrors) {
					nodeErrors = { ...nodeErrors };
				}
			}
			
			if (data.data.persisted_results) {
				for (const [nodeName, results] of Object.entries(data.data.persisted_results as Record<string, any[]>)) {
					if (results && results.length > 0) {
						const node = data.data.nodes?.find((n: GraphNode) => n.name === nodeName);
						if (node && node.output_components?.length > 0) {
							const snapshots: (Record<string, any> | null)[] = [];
							nodeResults[nodeName] = results.map((entry: any) => {
								const result = entry?.result !== undefined ? entry.result : entry;
								const inputsSnapshot = entry?.inputs_snapshot || null;
								snapshots.push(inputsSnapshot);
								
								return node.output_components.map((comp: GradioComponentData) => {
									if (result === null || result === undefined) {
										return { ...comp, value: comp.value };
									}
									if (typeof result !== 'object' || Array.isArray(result)) {
										const expectedKeys = node.output_components.map((c: GradioComponentData) => c.port_name).join(', ');
										nodeErrors[nodeName] = `Function must return a dict with keys: {${expectedKeys}}. Got ${Array.isArray(result) ? 'list' : typeof result} instead.`;
										return { ...comp, value: comp.value };
									}
									if (!(comp.port_name in result)) {
										const expectedKeys = node.output_components.map((c: GradioComponentData) => c.port_name).join(', ');
										const gotKeys = Object.keys(result).join(', ');
										nodeErrors[nodeName] = `Missing key "${comp.port_name}" in return value. Expected: {${expectedKeys}}, got: {${gotKeys}}`;
										return { ...comp, value: comp.value };
									}
									return { ...comp, value: result[comp.port_name] };
								});
							});
							nodeInputsSnapshots[nodeName] = snapshots;
							selectedResultIndex[nodeName] = nodeResults[nodeName].length - 1;
						}
					}
				}
			}
			
			if (data.data.inputs) {
				inputValues = data.data.inputs;
				for (const [nodeId, nodeInputs] of Object.entries(inputValues)) {
					const variant = (nodeInputs as Record<string, any>)['_selected_variant'];
					if (variant !== undefined) {
						selectedVariants[nodeId] = variant;
					}
				}
			}
			
			if (data.data.transform) {
				transform = {
					x: data.data.transform.x ?? 0,
					y: data.data.transform.y ?? 0,
					scale: data.data.transform.scale ?? 1
				};
			}
		} else if (data.type === 'node_started') {
			const startedNode = data.started_node;
			if (startedNode) {
				runningNodes.add(startedNode);
				runningNodes = new Set(runningNodes);
				nodeStartTimes[startedNode] = Date.now();
				delete nodeErrors[startedNode];
				startTimer();
			}
		} else if (data.type === 'error' && data.error) {
			console.error('[daggr] server error:', data.error);
			const errorNode = data.node || data.completed_node;
			if (errorNode) {
				nodeErrors[errorNode] = data.error;
			}
			const nodesToClear = data.nodes_to_clear || (errorNode ? [errorNode] : []);
			for (const nodeName of nodesToClear) {
				delete nodeStartTimes[nodeName];
				runningNodes.delete(nodeName);
			}
			runningNodes = new Set(runningNodes);
			stopTimerIfNoRunning();
		} else if (data.type === 'node_complete' || data.type === 'error') {
			const completedNode = data.completed_node;
			
			if (completedNode) {
				runningNodes.delete(completedNode);
				runningNodes = new Set(runningNodes);
			}
			
			if (completedNode && data.execution_time_ms != null) {
				nodeExecutionTimes[completedNode] = data.execution_time_ms;
				delete nodeStartTimes[completedNode];
				
				if (!nodeAvgTimes[completedNode]) {
					nodeAvgTimes[completedNode] = { total: 0, count: 0 };
				}
				nodeAvgTimes[completedNode].total += data.execution_time_ms;
				nodeAvgTimes[completedNode].count++;
				
				stopTimerIfNoRunning();
			}
			
			if (data.nodes) {
				graphData = { ...graphData!, nodes: data.nodes, edges: data.edges || graphData!.edges };
				
				let hasNewErrors = false;
				for (const node of data.nodes) {
					if (node.validation_error) {
						nodeErrors[node.name] = node.validation_error;
						hasNewErrors = true;
					}
				}
				if (hasNewErrors) {
					nodeErrors = { ...nodeErrors };
				}
				
				if (completedNode) {
					const node = data.nodes?.find((n: GraphNode) => n.name === completedNode);
					if (node && node.output_components?.length > 0) {
						const hasResult = node.output_components.some((c: GradioComponentData) => c.value != null);
						if (hasResult) {
							if (!nodeResults[completedNode]) {
								nodeResults[completedNode] = [];
							}
							if (!nodeInputsSnapshots[completedNode]) {
								nodeInputsSnapshots[completedNode] = [];
							}
							const resultSnapshot = node.output_components.map((c: GradioComponentData) => ({ ...c }));
							nodeResults[completedNode] = [...nodeResults[completedNode], resultSnapshot];
							const snapshot = data.inputs || data.selected_results ? {
								inputs: data.inputs || {},
								selected_results: data.selected_results || {},
							} : null;
							nodeInputsSnapshots[completedNode] = [...nodeInputsSnapshots[completedNode], snapshot];
							selectedResultIndex[completedNode] = nodeResults[completedNode].length - 1;

							if (isOnSpaces && !hfUser && !hasShownPersistencePrompt) {
								hasShownPersistencePrompt = true;
								showLoginTooltip = true;
							}
						}
					}
				}
			}
		}
	}

	onMount(() => {
		async function initialize() {
			await fetchUserInfo();
			
			if (canPersist) {
				await fetchSheets();
				if (sheets.length === 0) {
					await createSheet();
				} else {
					currentSheetId = sheets[0].sheet_id;
				}
			}
			
			connectWebSocket();
		}
		
		initialize();
		
		return () => {
			if (reconnectTimer) {
				clearTimeout(reconnectTimer);
				reconnectTimer = null;
			}
			if (timerInterval) {
				clearInterval(timerInterval);
				timerInterval = null;
			}
			if (saveDebounceTimer) {
				clearTimeout(saveDebounceTimer);
				saveDebounceTimer = null;
			}
			if (transformDebounceTimer) {
				clearTimeout(transformDebounceTimer);
				transformDebounceTimer = null;
			}
			if (ws) {
				ws.onclose = null;
				ws.onerror = null;
				ws.close();
				ws = null;
			}
		};
	});

	function getAncestors(nodeName: string): string[] {
		const ancestors = new Set<string>();
		const toVisit = [nodeName];
		
		while (toVisit.length > 0) {
			const current = toVisit.pop()!;
			for (const edge of edges) {
				if (edge.to_node === current.replace(/ /g, '_').replace(/-/g, '_')) {
					const sourceNode = nodes.find(n => n.id === edge.from_node);
					if (sourceNode && !ancestors.has(sourceNode.name)) {
						ancestors.add(sourceNode.name);
						if (!sourceNode.is_input_node) {
							toVisit.push(sourceNode.name);
						}
					}
				}
			}
		}
		
		return Array.from(ancestors);
	}

	function debounceSaveInput(nodeId: string, portName: string, value: any) {
		if (!canPersist || !currentSheetId) return;
		
		if (saveDebounceTimer) {
			clearTimeout(saveDebounceTimer);
		}
		
		saveDebounceTimer = window.setTimeout(() => {
			if (ws && wsConnected) {
				ws.send(JSON.stringify({
					action: 'save_input',
					node_id: nodeId,
					port_name: portName,
					value: value
				}));
			}
		}, 500);
	}

	function debounceSaveTransform() {
		if (!canPersist || !currentSheetId) return;
		
		if (transformDebounceTimer) {
			clearTimeout(transformDebounceTimer);
		}
		
		transformDebounceTimer = window.setTimeout(() => {
			if (ws && wsConnected) {
				ws.send(JSON.stringify({
					action: 'save_transform',
					x: transform.x,
					y: transform.y,
					scale: transform.scale
				}));
			}
		}, 300);
	}

	async function handleInputChange(nodeId: string, portName: string, value: any) {
		if (!inputValues[nodeId]) {
			inputValues[nodeId] = {};
		}
		if (value instanceof Blob || value instanceof File) {
			const dataUrl = await blobToDataUrl(value);
			inputValues[nodeId][portName] = dataUrl;
			debounceSaveInput(nodeId, portName, dataUrl);
		} else {
			inputValues[nodeId][portName] = value;
			debounceSaveInput(nodeId, portName, value);
		}
	}

	function blobToDataUrl(blob: Blob): Promise<string> {
		return new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = () => resolve(reader.result as string);
			reader.onerror = reject;
			reader.readAsDataURL(blob);
		});
	}

	function getComponentValue(node: GraphNode, comp: GradioComponentData): any {
		const nodeInputs = inputValues[node.id];
		if (nodeInputs && comp.port_name in nodeInputs) {
			return nodeInputs[comp.port_name];
		}
		return comp.value ?? '';
	}

	function handleItemListChange(nodeId: string, itemIndex: number, fieldName: string, value: any) {
		if (!itemListValues[nodeId]) {
			itemListValues[nodeId] = {};
		}
		if (!itemListValues[nodeId][itemIndex]) {
			itemListValues[nodeId][itemIndex] = {};
		}
		itemListValues[nodeId][itemIndex][fieldName] = value;
	}

	function getItemListValue(nodeId: string, itemIndex: number, fieldName: string): any {
		const edited = itemListValues[nodeId]?.[itemIndex]?.[fieldName];
		if (edited !== undefined) return edited;
		const node = nodes.find(n => n.id === nodeId);
		const item = node?.item_list_items?.find(i => i.index === itemIndex);
		return item?.fields?.[fieldName] ?? '';
	}

	function handleVariantSelect(nodeId: string, variantIndex: number) {
		selectedVariants[nodeId] = variantIndex;
		if (!inputValues[nodeId]) {
			inputValues[nodeId] = {};
		}
		inputValues[nodeId]['_selected_variant'] = variantIndex;
		
		if (ws && wsConnected) {
			ws.send(JSON.stringify({
				action: 'save_variant_selection',
				node_id: nodeId,
				variant_index: variantIndex
			}));
		}
	}

	function getSelectedVariant(node: GraphNode): number {
		if (selectedVariants[node.id] !== undefined) {
			return selectedVariants[node.id];
		}
		return node.selected_variant ?? 0;
	}

	function getComponentsToRender(node: GraphNode): GradioComponentData[] {
		if (node.is_input_node && node.input_components?.length) {
			return node.input_components;
		}
		return getSelectedResults(node);
	}

	function hasUserProvidedOutput(node: GraphNode): boolean {
		if (!node.output_components || node.output_components.length === 0) return false;
		const nodeInputs = inputValues[node.id];
		if (!nodeInputs) return false;
		for (const comp of node.output_components) {
			if (nodeInputs[comp.port_name] != null) return true;
		}
		return false;
	}

	function getNodeHeight(node: GraphNode): number {
		const portRows = Math.max(node.inputs.length, node.outputs.length, 1);
		const componentsToRender = getComponentsToRender(node);
		const embeddedHeight = componentsToRender.length * EMBEDDED_COMPONENT_HEIGHT;
		return HEADER_HEIGHT + HEADER_BORDER + BODY_PADDING_TOP + (portRows * PORT_ROW_HEIGHT) + embeddedHeight + BODY_PADDING_TOP;
	}

	let nodeMap = $derived.by(() => {
		const map = new Map<string, GraphNode>();
		for (const node of nodes) {
			map.set(node.id, node);
		}
		return map;
	});

	function getPortY(portIndex: number): number {
		return HEADER_HEIGHT + HEADER_BORDER + BODY_PADDING_TOP + (portIndex * PORT_ROW_HEIGHT) + (PORT_ROW_HEIGHT / 2);
	}

	let edgePaths = $derived.by(() => {
		const paths: { 
			id: string; 
			d: string; 
			is_scattered: boolean; 
			is_gathered: boolean;
			isStale: boolean;
			forkPaths?: string[];
			fromNodeName: string;
			toNodeName: string;
		}[] = [];
		
		for (const edge of edges) {
			const fromNode = nodeMap.get(edge.from_node);
			const toNode = nodeMap.get(edge.to_node);
			
			if (!fromNode || !toNode) continue;

			const fromPortIdx = fromNode.outputs.indexOf(edge.from_port);
			const toPortIdx = toNode.inputs.findIndex(p => p.name === edge.to_port);

			if (fromPortIdx === -1 || toPortIdx === -1) continue;

			const fromPortY = getPortY(fromPortIdx);
			const toPortY = getPortY(toPortIdx);

			const x1 = fromNode.x + NODE_WIDTH;
			const y1 = fromNode.y + fromPortY;
			const x2 = toNode.x;
			const y2 = toNode.y + toPortY;

			const dx = Math.abs(x2 - x1);
			const cp = Math.max(dx * 0.4, 50);

			const is_scattered = edge.is_scattered || false;
			const is_gathered = edge.is_gathered || false;

			const toNodeSelectedIdx = selectedResultIndex[toNode.name];
			const toNodeSnapshot = nodeInputsSnapshots[toNode.name]?.[toNodeSelectedIdx];
			
			let isStale = false;
			if (toNodeSnapshot == null) {
				isStale = true;
			} else {
				if (selectedResultIndex[fromNode.name] !== toNodeSnapshot.selected_results?.[fromNode.name]) {
					isStale = true;
				}
				if (JSON.stringify(inputValues[fromNode.id]) !== JSON.stringify(toNodeSnapshot.inputs?.[fromNode.id])) {
					isStale = true;
				}
			}

			let forkPaths: string[] = [];

			if (is_scattered) {
				const forkStart = x2 - 30;
				const forkSpread = 8;
				const d = `M ${x1} ${y1} C ${x1 + cp} ${y1}, ${forkStart - 20} ${y2}, ${forkStart} ${y2}`;
				forkPaths = [
					`M ${forkStart} ${y2} L ${x2} ${y2 - forkSpread}`,
					`M ${forkStart} ${y2} L ${x2} ${y2}`,
					`M ${forkStart} ${y2} L ${x2} ${y2 + forkSpread}`,
				];
				paths.push({ id: edge.id, d, is_scattered, is_gathered, isStale, forkPaths, fromNodeName: fromNode.name, toNodeName: toNode.name });
			} else if (is_gathered) {
				const forkEnd = x1 + 30;
				const forkSpread = 8;
				forkPaths = [
					`M ${x1} ${y1 - forkSpread} L ${forkEnd} ${y1}`,
					`M ${x1} ${y1} L ${forkEnd} ${y1}`,
					`M ${x1} ${y1 + forkSpread} L ${forkEnd} ${y1}`,
				];
				const d = `M ${forkEnd} ${y1} C ${forkEnd + cp - 30} ${y1}, ${x2 - cp} ${y2}, ${x2} ${y2}`;
				paths.push({ id: edge.id, d, is_scattered, is_gathered, isStale, forkPaths, fromNodeName: fromNode.name, toNodeName: toNode.name });
			} else {
				const d = `M ${x1} ${y1} C ${x1 + cp} ${y1}, ${x2 - cp} ${y2}, ${x2} ${y2}`;
				paths.push({ id: edge.id, d, is_scattered, is_gathered, isStale, fromNodeName: fromNode.name, toNodeName: toNode.name });
			}
		}
		
		return paths;
	});

	function zoomToFit() {
		if (nodes.length === 0 || !canvasEl) return;

		const padding = 40;
		const canvasRect = canvasEl.getBoundingClientRect();
		const canvasWidth = canvasRect.width;
		const canvasHeight = canvasRect.height;

		let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
		for (const node of nodes) {
			const nodeHeight = getNodeHeight(node);
			minX = Math.min(minX, node.x);
			minY = Math.min(minY, node.y);
			maxX = Math.max(maxX, node.x + NODE_WIDTH);
			maxY = Math.max(maxY, node.y + nodeHeight);
		}

		const contentWidth = maxX - minX;
		const contentHeight = maxY - minY;

		const scaleX = (canvasWidth - padding * 2) / contentWidth;
		const scaleY = (canvasHeight - padding * 2) / contentHeight;
		const newScale = Math.min(scaleX, scaleY, 1.5);

		const centerX = (minX + maxX) / 2;
		const centerY = (minY + maxY) / 2;
		const newX = canvasWidth / 2 - centerX * newScale;
		const newY = canvasHeight / 2 - centerY * newScale;

		transform = { x: newX, y: newY, scale: Math.max(0.2, newScale) };
		debounceSaveTransform();
	}

	function zoomIn() {
		transform.scale = Math.min(3, transform.scale * 1.2);
		debounceSaveTransform();
	}

	function zoomOut() {
		transform.scale = Math.max(0.2, transform.scale / 1.2);
		debounceSaveTransform();
	}

	function handleMouseDown(e: MouseEvent) {
		if (e.button === 0 && e.target === canvasEl) {
			isPanning = true;
			startPan = { x: e.clientX - transform.x, y: e.clientY - transform.y };
		}
		const target = e.target as HTMLElement;
		if (!target.closest('.run-controls')) {
			runModeMenuOpen = null;
		}
	}

	function handleMouseMove(e: MouseEvent) {
		if (isPanning) {
			transform.x = e.clientX - startPan.x;
			transform.y = e.clientY - startPan.y;
		}
	}

	function handleMouseUp() {
		if (isPanning) {
			isPanning = false;
			debounceSaveTransform();
		}
	}

	function handleWheel(e: WheelEvent) {
		const target = e.target as HTMLElement;
		const scrollableParent = target.closest('.item-list-items, .map-items-list, .embedded-components');
		
		if (scrollableParent && !e.ctrlKey && !e.metaKey) {
			const el = scrollableParent as HTMLElement;
			const canScrollUp = el.scrollTop > 0;
			const canScrollDown = el.scrollTop < el.scrollHeight - el.clientHeight;
			const scrollingDown = e.deltaY > 0;
			const scrollingUp = e.deltaY < 0;
			
			if ((scrollingDown && canScrollDown) || (scrollingUp && canScrollUp)) {
				return;
			}
		}
		
		e.preventDefault();
		
		if (e.ctrlKey || e.metaKey) {
			const rect = canvasEl.getBoundingClientRect();
			const mouseX = e.clientX - rect.left;
			const mouseY = e.clientY - rect.top;
			
			const canvasX = (mouseX - transform.x) / transform.scale;
			const canvasY = (mouseY - transform.y) / transform.scale;
			
			const delta = e.deltaY > 0 ? 0.97 : 1.03;
			const newScale = Math.max(0.2, Math.min(3, transform.scale * delta));
			
			transform = {
				x: mouseX - canvasX * newScale,
				y: mouseY - canvasY * newScale,
				scale: newScale
			};
		} else {
			transform = {
				...transform,
				x: transform.x - e.deltaX,
				y: transform.y - e.deltaY
			};
		}
		debounceSaveTransform();
	}

	function handleRunNode(e: MouseEvent, nodeName: string, runMode?: 'step' | 'toHere') {
		e.stopPropagation();
		
		if (runningNodes.has(nodeName)) {
			return;
		}
		
		const mode = runMode ?? nodeRunModes[nodeName] ?? 'toHere';
		const runId = `${nodeName}_${Date.now()}_${Math.random().toString(36).slice(2)}`;
		
		runningNodes.add(nodeName);
		runningNodes = new Set(runningNodes);
		delete nodeExecutionTimes[nodeName];
		
		if (ws && wsConnected) {
			ws.send(JSON.stringify({
				action: 'run',
				node_name: nodeName,
				inputs: inputValues,
				item_list_values: itemListValues,
				selected_results: selectedResultIndex,
				run_id: runId,
				sheet_id: currentSheetId,
				hf_token: getStoredToken(),
				run_ancestors: mode === 'toHere'
			}));
		}
	}

	function setRunMode(nodeName: string, mode: 'step' | 'toHere') {
		nodeRunModes[nodeName] = mode;
		nodeRunModes = { ...nodeRunModes };
		runModeVersion++;
		runModeMenuOpen = null;
	}

	function highlightRunTargets(nodeName: string, mode: 'step' | 'toHere') {
		if (mode === 'step') {
			highlightedNodes = new Set([nodeName]);
		} else {
			const ancestors = getAncestors(nodeName);
			highlightedNodes = new Set([nodeName, ...ancestors]);
		}
	}

	function clearHighlight() {
		highlightedNodes = new Set();
	}

	function toggleRunModeMenu(e: MouseEvent, nodeName: string) {
		e.stopPropagation();
		if (runModeMenuOpen === nodeName) {
			runModeMenuOpen = null;
		} else {
			runModeMenuOpen = nodeName;
		}
	}

	function getRunMode(nodeName: string): 'step' | 'toHere' {
		void runModeVersion;
		return nodeRunModes[nodeName] ?? 'toHere';
	}

	function getBadgeStyle(type: string): string {
		const colors: Record<string, string> = {
			'FN': 'var(--color-accent)',
			'INPUT': 'var(--secondary-500, #06b6d4)',
			'MAP': 'var(--primary-400, #a855f7)',
			'GRADIO': 'var(--color-accent)',
			'MODEL': 'var(--primary-500, #22c55e)',
			'CHOICE': 'var(--primary-400, #8b5cf6)',
		};
		return `background: ${colors[type] || 'var(--neutral-500)'};`;
	}

	function getSelectedResults(node: GraphNode): GradioComponentData[] {
		const results = nodeResults[node.name];
		if (!results || results.length === 0) {
			return node.output_components || [];
		}
		const idx = selectedResultIndex[node.name] ?? results.length - 1;
		return results[idx] || node.output_components || [];
	}

	function getResultCount(nodeName: string): number {
		return nodeResults[nodeName]?.length || 0;
	}

	function restoreInputsSnapshot(nodeName: string, index: number) {
		const snapshots = nodeInputsSnapshots[nodeName];
		if (!snapshots || !snapshots[index]) return;
		
		const snapshot = snapshots[index];
		
		const inputs = snapshot.inputs || snapshot;
		for (const [inputNodeId, nodeInputs] of Object.entries(inputs)) {
			if (typeof nodeInputs === 'object' && nodeInputs !== null) {
				inputValues[inputNodeId] = { ...inputValues[inputNodeId], ...nodeInputs };
			}
		}
		
		if (snapshot.selected_results) {
			for (const [upstreamNode, resultIdx] of Object.entries(snapshot.selected_results)) {
				if (upstreamNode === nodeName) continue;
				if (typeof resultIdx === 'number') {
					selectedResultIndex[upstreamNode] = resultIdx;
				}
			}
		}
	}

	function autoMatchDownstream(changedNode: string, newIndex: number) {
		for (const [nodeName, snapshots] of Object.entries(nodeInputsSnapshots)) {
			if (!snapshots || nodeName === changedNode) continue;
			const matchIdx = snapshots.findIndex(
				s => s?.selected_results?.[changedNode] === newIndex
			);
			if (matchIdx !== -1) {
				selectedResultIndex[nodeName] = matchIdx;
				autoMatchDownstream(nodeName, matchIdx);
			}
		}
	}

	function prevResult(e: MouseEvent, nodeName: string) {
		e.stopPropagation();
		const current = selectedResultIndex[nodeName] ?? 0;
		if (current > 0) {
			const newIndex = current - 1;
			selectedResultIndex[nodeName] = newIndex;
			selectedResultIndex = { ...selectedResultIndex };
			restoreInputsSnapshot(nodeName, newIndex);
			autoMatchDownstream(nodeName, newIndex);
		}
	}

	function nextResult(e: MouseEvent, nodeName: string) {
		e.stopPropagation();
		const total = getResultCount(nodeName);
		const current = selectedResultIndex[nodeName] ?? 0;
		if (current < total - 1) {
			const newIndex = current + 1;
			selectedResultIndex[nodeName] = newIndex;
			selectedResultIndex = { ...selectedResultIndex };
			restoreInputsSnapshot(nodeName, newIndex);
			autoMatchDownstream(nodeName, newIndex);
		}
	}

	function handleReplayItem(nodeName: string, itemIndex: number) {
	}

	let zoomPercent = $derived(Math.round(transform.scale * 100));

	function formatTime(ms: number): string {
		if (ms < 1000) {
			return `${(ms / 1000).toFixed(1)}s`;
		} else if (ms < 60000) {
			return `${(ms / 1000).toFixed(1)}s`;
		} else {
			const mins = Math.floor(ms / 60000);
			const secs = ((ms % 60000) / 1000).toFixed(0);
			return `${mins}m ${secs}s`;
		}
	}

	function getNodeTimeDisplay(nodeName: string): { text: string; isRunning: boolean; isError: boolean } | null {
		void timerTick;
		
		if (nodeErrors[nodeName]) {
			return { text: 'Error', isRunning: false, isError: true };
		}
		
		const isRunning = runningNodes.has(nodeName);
		const startTime = nodeStartTimes[nodeName];
		const finalTime = nodeExecutionTimes[nodeName];
		const avgData = nodeAvgTimes[nodeName];
		const avgTime = avgData ? avgData.total / avgData.count : null;
		
		if (isRunning && startTime) {
			const elapsed = Date.now() - startTime;
			if (avgTime) {
				return { text: `${formatTime(elapsed)}/${formatTime(avgTime)}`, isRunning: true, isError: false };
			}
			return { text: formatTime(elapsed), isRunning: true, isError: false };
		}
		
		if (finalTime != null) {
			return { text: formatTime(finalTime), isRunning: false, isError: false };
		}
		
		return null;
	}

	function startEditingSheetName() {
		if (currentSheet) {
			editSheetNameValue = currentSheet.name;
			editingSheetName = true;
		}
	}

	function finishEditingSheetName() {
		if (editingSheetName && currentSheetId && editSheetNameValue.trim()) {
			renameSheet(currentSheetId, editSheetNameValue.trim());
		}
		editingSheetName = false;
	}

	function handleSheetNameKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			finishEditingSheetName();
		} else if (e.key === 'Escape') {
			editingSheetName = false;
		}
	}
</script>

<div 
	class="canvas"
	bind:this={canvasEl}
	onmousedown={handleMouseDown}
	onmousemove={handleMouseMove}
	onmouseup={handleMouseUp}
	onmouseleave={handleMouseUp}
	onwheel={handleWheel}
	role="application"
>
	<div class="grid-bg"></div>

	<div 
		class="canvas-transform"
		style="transform: translate({transform.x}px, {transform.y}px) scale({transform.scale})"
	>
		<svg class="edges-svg">
			{#each edgePaths as edge (edge.id)}
				<path d={edge.d} class="edge-path" class:stale={edge.isStale} class:will-run={highlightedNodes.has(edge.fromNodeName) && highlightedNodes.has(edge.toNodeName)} />
				{#if edge.forkPaths}
					{#each edge.forkPaths as forkD}
						<path d={forkD} class="edge-path edge-fork" class:stale={edge.isStale} class:will-run={highlightedNodes.has(edge.fromNodeName) && highlightedNodes.has(edge.toNodeName)} />
					{/each}
				{/if}
			{/each}
		</svg>

		{#each nodes as node (node.id)}
			{@const componentsToRender = getComponentsToRender(node)}
			{@const timeDisplay = getNodeTimeDisplay(node.name)}
			<div 
				class="node"
				class:will-run={highlightedNodes.has(node.name)}
				style="left: {node.x}px; top: {node.y}px; width: {NODE_WIDTH}px;"
			>
				{#if timeDisplay}
					<div class="exec-time" class:running={timeDisplay.isRunning} class:error={timeDisplay.isError}>{timeDisplay.text}</div>
				{/if}
				<div class="node-header">
					<span class="type-badge" style={getBadgeStyle(node.type)}>{node.type}{#if node.is_local}&nbsp;⚡{/if}</span>
					{#if node.url}
						<a class="node-name node-link" href={node.url} target="_blank" rel="noopener noreferrer" title="Open on Hugging Face">{node.name}</a>
					{:else}
						<span class="node-name">{node.name}</span>
					{/if}
					{#if !node.is_input_node}
						{#key runModeVersion}
						<div class="run-controls">
							<span 
								class="run-btn"
								class:running={runningNodes.has(node.name)}
								class:disabled={runningNodes.has(node.name)}
								onclick={(e) => handleRunNode(e, node.name)}
								title={runningNodes.has(node.name) ? "Running..." : ((nodeRunModes[node.name] ?? 'toHere') === 'toHere' ? "Run to here" : "Run this step")}
								role="button"
								tabindex="0"
							>
								{#if node.is_map_node || (nodeRunModes[node.name] ?? 'toHere') === 'toHere'}
									<svg class="run-icon-svg run-icon-double" viewBox="0 0 14 12" fill="currentColor">
										<path d="M2 1 L10 6 L2 11 Z" opacity="0.5" transform="translate(-2, 0)"/>
										<path d="M2 1 L10 6 L2 11 Z" transform="translate(2, 0)"/>
									</svg>
								{:else}
									<svg class="run-icon-svg" viewBox="0 0 14 12" fill="currentColor">
										<path d="M3 1 L11 6 L3 11 Z"/>
									</svg>
								{/if}
								{#if runningNodes.has(node.name)}
									<span class="run-badge"></span>
								{/if}
							</span>
							<span 
								class="run-mode-toggle"
								onclick={(e) => toggleRunModeMenu(e, node.name)}
								role="button"
								tabindex="0"
								title="Run options"
							>
								<svg viewBox="0 0 10 6" fill="currentColor">
									<path d="M1 1 L5 5 L9 1" stroke="currentColor" stroke-width="1.5" fill="none"/>
								</svg>
							</span>
							{#if runModeMenuOpen === node.name}
								<div class="run-mode-menu" onmouseleave={() => clearHighlight()}>
									<button 
										class="run-mode-option"
										class:active={(nodeRunModes[node.name] ?? 'toHere') === 'step'}
										onclick={(e) => { e.stopPropagation(); setRunMode(node.name, 'step'); clearHighlight(); }}
										onmouseenter={() => highlightRunTargets(node.name, 'step')}
									>
										<svg class="run-mode-icon" viewBox="0 0 10 12" fill="currentColor">
											<path d="M1 1 L9 6 L1 11 Z"/>
										</svg>
										<span>Run this step</span>
									</button>
									<button 
										class="run-mode-option"
										class:active={(nodeRunModes[node.name] ?? 'toHere') === 'toHere'}
										onclick={(e) => { e.stopPropagation(); setRunMode(node.name, 'toHere'); clearHighlight(); }}
										onmouseenter={() => highlightRunTargets(node.name, 'toHere')}
									>
										<svg class="run-mode-icon run-mode-icon-double" viewBox="0 0 14 12" fill="currentColor">
											<path d="M2 1 L10 6 L2 11 Z" opacity="0.5" transform="translate(-2, 0)"/>
											<path d="M2 1 L10 6 L2 11 Z" transform="translate(2, 0)"/>
										</svg>
										<span>Run to here</span>
									</button>
								</div>
							{/if}
						</div>
						{/key}
					{/if}
				</div>

				<div class="node-body">
					<div class="ports-left">
						{#each node.inputs as port (port.name)}
							<div class="port-row">
								<span class="port-dot input"></span>
								<span class="port-label">{port.name}</span>
							</div>
						{/each}
					</div>
					<div class="ports-right">
						{#each node.outputs as portName (portName)}
							<div class="port-row">
								<span class="port-label">{portName}</span>
								<span class="port-dot output"></span>
							</div>
						{/each}
					</div>
				</div>

				{#if nodeErrors[node.name]}
					<div class="node-error">
						<div class="node-error-label">Error</div>
						<div class="node-error-message">{nodeErrors[node.name]}</div>
					</div>
				{:else if node.variants && node.variants.length > 0}
					{@const currentVariantIdx = getSelectedVariant(node)}
					<div class="variants-accordion">
						{#each node.variants as variant, idx (idx)}
							{@const isSelected = idx === currentVariantIdx}
							<div 
								class="variant-card"
								class:selected={isSelected}
								onclick={() => handleVariantSelect(node.id, idx)}
								role="button"
								tabindex="0"
							>
								<div class="variant-header">
									<span class="variant-radio" class:checked={isSelected}>
										{#if isSelected}●{:else}○{/if}
									</span>
									<span class="variant-name">{variant.name}</span>
								</div>
								{#if isSelected && variant.input_components.length > 0}
									<div class="variant-inputs">
										{#each variant.input_components as comp (comp.port_name)}
											<EmbeddedComponent
												{comp}
												nodeId={node.id}
												isInputNode={true}
												value={inputValues[node.id]?.[`variant_${idx}_${comp.port_name}`] ?? comp.value ?? ''}
												onchange={(portName, value) => handleInputChange(node.id, `variant_${idx}_${portName}`, value)}
											/>
										{/each}
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{:else if componentsToRender.length > 0}
					<div class="embedded-components">
						{#each componentsToRender as comp (comp.port_name)}
							<EmbeddedComponent
								{comp}
								nodeId={node.id}
								isInputNode={node.is_input_node}
								value={getComponentValue(node, comp)}
								onchange={(portName, value) => handleInputChange(node.id, portName, value)}
							/>
						{/each}
					</div>
					
					{#if !node.is_input_node && getResultCount(node.name) > 1}
						<div class="result-selector">
							<button 
								class="result-nav" 
								onclick={(e) => prevResult(e, node.name)}
								disabled={(selectedResultIndex[node.name] ?? 0) === 0}
							>‹</button>
							<span class="result-counter">
								{(selectedResultIndex[node.name] ?? 0) + 1}/{getResultCount(node.name)}
							</span>
							<button 
								class="result-nav" 
								onclick={(e) => nextResult(e, node.name)}
								disabled={(selectedResultIndex[node.name] ?? 0) >= getResultCount(node.name) - 1}
							>›</button>
						</div>
					{/if}
				{/if}

				{#if node.is_map_node && node.map_items && node.map_items.length > 0}
					<MapItemsSection
						nodeId={node.id}
						nodeName={node.name}
						items={node.map_items}
						onReplayItem={handleReplayItem}
					/>
				{/if}

				{#if node.item_list_schema && node.item_list_items && node.item_list_items.length > 0}
					<ItemListSection
						nodeId={node.id}
						schema={node.item_list_schema}
						items={node.item_list_items}
						getValue={getItemListValue}
						onchange={handleItemListChange}
					/>
				{/if}
			</div>
		{/each}
	</div>

	<div class="zoom-controls">
		<img src="/daggr-assets/logo_dark_small.png" alt="daggr" class="daggr-logo" />
		<button class="zoom-btn" onclick={zoomOut} title="Zoom out">−</button>
		<span class="zoom-level">{zoomPercent}%</span>
		<button class="zoom-btn" onclick={zoomIn} title="Zoom in">+</button>
		<button class="zoom-btn fit-btn" onclick={zoomToFit} title="Fit all nodes">⊡</button>
	</div>

	<div class="title-bar">
		<span class="title">{graphData?.name || 'daggr'}</span>
		{#if canPersist && sheets.length > 0}
			<span class="title-separator">|</span>
			<div class="sheet-selector">
				{#if editingSheetName}
					<input
						type="text"
						class="sheet-name-input"
						bind:value={editSheetNameValue}
						onblur={finishEditingSheetName}
						onkeydown={handleSheetNameKeydown}
						autofocus
					/>
				{:else}
					<button 
						class="sheet-current"
						onclick={() => sheetDropdownOpen = !sheetDropdownOpen}
						ondblclick={startEditingSheetName}
						title="Double-click to rename"
					>
						<span class="sheet-name">{currentSheet?.name || 'Sheet'}</span>
						<svg class="dropdown-arrow" viewBox="0 0 10 6" fill="currentColor">
							<path d="M1 1 L5 5 L9 1" stroke="currentColor" stroke-width="1.5" fill="none"/>
						</svg>
					</button>
				{/if}
				{#if sheetDropdownOpen}
					<div class="sheet-dropdown">
						{#each sheets as sheet (sheet.sheet_id)}
							<div 
								class="sheet-option"
								class:active={sheet.sheet_id === currentSheetId}
							>
								<button 
									class="sheet-option-name"
									onclick={() => selectSheet(sheet.sheet_id)}
								>
									{sheet.name}
								</button>
								{#if sheets.length > 1}
									<button 
										class="sheet-delete"
										onclick={() => deleteSheet(sheet.sheet_id)}
										title="Delete sheet"
									>×</button>
								{/if}
							</div>
						{/each}
						<button class="sheet-new" onclick={() => createSheet()}>
							+ New Sheet
						</button>
					</div>
				{/if}
			</div>
		{/if}
	</div>

	{#if !wsConnected}
		<div class="connection-status">Connecting...</div>
	{:else if !graphData}
		<div class="connection-status">Loading graph...</div>
	{:else if hfUser}
		<div class="hf-user">
			{#if hfUser.avatar_url}
				<img src={hfUser.avatar_url} alt="" class="hf-avatar" />
			{/if}
			<span class="hf-username">{hfUser.username}</span>
			<button class="logout-btn" onclick={handleLogout} title="Logout">×</button>
			<div class="hf-tooltip">
				Your Hugging Face token is used for all GradioNode and InferenceNode calls. This enables ZeroGPU quota tracking and access to private Spaces and gated models.
			</div>
		</div>
	{:else}
		<div class="login-section">
			<button class="login-btn" onclick={() => showLoginTooltip = !showLoginTooltip} title="Login with Hugging Face">
				<img src="/daggr-assets/hf-logo-pirate.png" alt="HF" class="hf-logo-icon" />
				<span>Login</span>
			</button>
			{#if showLoginTooltip}
				<div class="login-tooltip">
					<div class="login-tooltip-header">Login with Hugging Face</div>
					{#if isOnSpaces}
						<p class="login-tooltip-desc login-tooltip-highlight">
							Login to save your outputs and resume your work later.
						</p>
					{/if}
					<p class="login-tooltip-desc">
						Your token is used to authenticate with Hugging Face APIs for InferenceNode calls and ZeroGPU-powered Spaces. Create a token with <strong>Read</strong> scope (or <strong>Fine-grained</strong> with Inference API access) at <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener">huggingface.co/settings/tokens</a>
					</p>
					<input
						type="password"
						class="login-token-input"
						placeholder="hf_..."
						bind:value={tokenInputValue}
						onkeydown={(e) => e.key === 'Enter' && handleLogin()}
						disabled={loginLoading}
					/>
					{#if loginError}
						<div class="login-error">{loginError}</div>
					{/if}
					<button class="login-submit-btn" onclick={handleLogin} disabled={loginLoading}>
						{loginLoading ? 'Verifying...' : 'Login'}
					</button>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.canvas {
		position: fixed;
		inset: 0;
		width: 100vw;
		height: 100vh;
		overflow: hidden;
		background: var(--body-background-fill);
		cursor: grab;
		font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
	}

	.canvas:active {
		cursor: grabbing;
	}

	.grid-bg {
		position: absolute;
		inset: 0;
		background-image: radial-gradient(circle, color-mix(in srgb, var(--color-accent) 6%, transparent) 1px, transparent 1px);
		background-size: 20px 20px;
		pointer-events: none;
	}

	.canvas-transform {
		position: absolute;
		top: 0;
		left: 0;
		transform-origin: 0 0;
	}

	.connection-status {
		position: fixed;
		top: 16px;
		right: 16px;
		background: color-mix(in srgb, var(--color-accent) 90%, transparent);
		color: var(--button-primary-text-color);
		padding: 8px 16px;
		border-radius: 8px;
		font-size: 12px;
		font-weight: 600;
		z-index: 1000;
	}

	.title-bar {
		position: fixed;
		top: 16px;
		left: 50%;
		transform: translateX(-50%);
		background: color-mix(in srgb, var(--block-background-fill) 90%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 20%, transparent);
		border-radius: 8px;
		padding: 8px 20px;
		z-index: 100;
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.title {
		font-size: 14px;
		font-weight: 600;
		color: var(--color-accent);
	}

	.title-separator {
		color: color-mix(in srgb, var(--color-accent) 30%, transparent);
		font-weight: 300;
	}

	.sheet-selector {
		position: relative;
	}

	.sheet-current {
		display: flex;
		align-items: center;
		gap: 6px;
		background: transparent;
		border: none;
		color: var(--body-text-color-subdued);
		font-size: 13px;
		font-weight: 500;
		cursor: pointer;
		padding: 4px 8px;
		border-radius: 4px;
		transition: all 0.15s;
	}

	.sheet-current:hover {
		background: color-mix(in srgb, var(--color-accent) 10%, transparent);
		color: var(--color-accent);
	}

	.sheet-name {
		max-width: 150px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.sheet-name-input {
		background: color-mix(in srgb, var(--body-background-fill) 30%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 40%, transparent);
		border-radius: 4px;
		color: var(--body-text-color);
		font-size: 13px;
		font-weight: 500;
		padding: 4px 8px;
		width: 140px;
		outline: none;
	}

	.sheet-name-input:focus {
		border-color: var(--color-accent);
	}

	.dropdown-arrow {
		width: 10px;
		height: 6px;
		opacity: 0.6;
	}

	.sheet-dropdown {
		position: absolute;
		top: 100%;
		left: 0;
		margin-top: 8px;
		min-width: 180px;
		background: color-mix(in srgb, var(--block-background-fill) 98%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 30%, transparent);
		border-radius: 8px;
		padding: 6px;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
	}

	.sheet-option {
		display: flex;
		align-items: center;
		border-radius: 4px;
		overflow: hidden;
	}

	.sheet-option.active {
		background: color-mix(in srgb, var(--color-accent) 15%, transparent);
	}

	.sheet-option-name {
		flex: 1;
		background: none;
		border: none;
		color: var(--body-text-color-subdued);
		font-size: 12px;
		padding: 8px 10px;
		text-align: left;
		cursor: pointer;
		transition: all 0.15s;
	}

	.sheet-option-name:hover {
		color: var(--body-text-color);
	}

	.sheet-option.active .sheet-option-name {
		color: var(--color-accent);
	}

	.sheet-delete {
		background: none;
		border: none;
		color: var(--neutral-500);
		font-size: 16px;
		padding: 6px 10px;
		cursor: pointer;
		transition: color 0.15s;
	}

	.sheet-delete:hover {
		color: var(--error-text-color);
	}

	.sheet-new {
		width: 100%;
		background: none;
		border: none;
		border-top: 1px solid color-mix(in srgb, var(--color-accent) 15%, transparent);
		color: var(--body-text-color-subdued);
		font-size: 12px;
		padding: 10px;
		margin-top: 4px;
		cursor: pointer;
		transition: all 0.15s;
	}

	.sheet-new:hover {
		color: var(--color-accent);
		background: color-mix(in srgb, var(--color-accent) 10%, transparent);
	}

	.hf-user {
		position: fixed;
		top: 16px;
		right: 16px;
		display: flex;
		align-items: center;
		gap: 8px;
		background: color-mix(in srgb, var(--block-background-fill) 90%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 20%, transparent);
		border-radius: 8px;
		padding: 6px 12px;
		z-index: 100;
		cursor: help;
	}

	.hf-avatar {
		width: 22px;
		height: 22px;
		border-radius: 50%;
		object-fit: cover;
	}

	.hf-username {
		font-size: 13px;
		font-weight: 500;
		color: var(--body-text-color-subdued);
	}

	.hf-tooltip {
		position: absolute;
		top: 100%;
		right: 0;
		margin-top: 8px;
		width: 280px;
		background: color-mix(in srgb, var(--block-background-fill) 98%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 30%, transparent);
		border-radius: 8px;
		padding: 12px;
		font-size: 12px;
		line-height: 1.5;
		color: var(--body-text-color-subdued);
		opacity: 0;
		visibility: hidden;
		transition: opacity 0.2s, visibility 0.2s;
		pointer-events: none;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
	}

	.hf-user:hover .hf-tooltip {
		opacity: 1;
		visibility: visible;
	}

	.logout-btn {
		background: transparent;
		border: none;
		color: var(--neutral-500);
		font-size: 16px;
		cursor: pointer;
		padding: 0 4px;
		margin-left: 4px;
		line-height: 1;
		opacity: 0;
		transition: opacity 0.2s, color 0.2s;
	}

	.hf-user:hover .logout-btn {
		opacity: 1;
	}

	.logout-btn:hover {
		color: var(--color-accent);
	}

	.login-section {
		position: fixed;
		top: 16px;
		right: 16px;
		z-index: 100;
	}

	.login-btn {
		background: color-mix(in srgb, var(--block-background-fill) 90%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 20%, transparent);
		border-radius: 8px;
		padding: 8px 12px;
		color: var(--body-text-color-subdued);
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 12px;
		transition: all 0.2s;
	}

	.login-btn:hover {
		border-color: color-mix(in srgb, var(--color-accent) 40%, transparent);
		color: var(--color-accent);
	}

	.hf-logo-icon {
		width: 18px;
		height: 18px;
		object-fit: contain;
	}

	.login-tooltip {
		position: absolute;
		top: calc(100% + 8px);
		right: 0;
		background: color-mix(in srgb, var(--block-background-fill) 98%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 30%, transparent);
		border-radius: 10px;
		padding: 16px;
		width: 280px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
	}

	.login-tooltip-header {
		font-size: 14px;
		font-weight: 600;
		color: var(--color-accent);
		margin-bottom: 8px;
	}

	.login-tooltip-desc {
		font-size: 12px;
		color: var(--body-text-color-subdued);
		margin: 0 0 12px 0;
		line-height: 1.4;
	}

	.login-tooltip-desc a {
		color: var(--color-accent);
		text-decoration: none;
	}

	.login-tooltip-desc a:hover {
		text-decoration: underline;
	}

	.login-tooltip-highlight {
		background: color-mix(in srgb, var(--color-accent) 15%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 30%, transparent);
		border-radius: 6px;
		padding: 8px 10px;
		color: var(--color-accent);
		font-weight: 500;
	}

	.login-token-input {
		width: 100%;
		padding: 10px 12px;
		background: var(--input-background-fill);
		border: 1px solid color-mix(in srgb, var(--color-accent) 20%, transparent);
		border-radius: 6px;
		color: var(--body-text-color);
		font-size: 13px;
		font-family: 'SF Mono', Monaco, monospace;
		margin-bottom: 8px;
		box-sizing: border-box;
	}

	.login-token-input:focus {
		outline: none;
		border-color: color-mix(in srgb, var(--color-accent) 50%, transparent);
	}

	.login-token-input::placeholder {
		color: var(--input-placeholder-color);
	}

	.login-error {
		font-size: 11px;
		color: var(--error-text-color);
		margin-bottom: 8px;
	}

	.login-submit-btn {
		width: 100%;
		padding: 10px;
		background: var(--color-accent);
		border: none;
		border-radius: 6px;
		color: var(--button-primary-text-color);
		font-size: 13px;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.2s;
	}

	.login-submit-btn:hover:not(:disabled) {
		background: var(--color-accent-soft);
	}

	.login-submit-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.zoom-controls {
		position: fixed;
		bottom: 16px;
		left: 16px;
		display: flex;
		align-items: center;
		gap: 4px;
		background: color-mix(in srgb, var(--block-background-fill) 90%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 20%, transparent);
		border-radius: 8px;
		padding: 4px;
		z-index: 100;
	}

	.daggr-logo {
		height: 20px;
		width: auto;
		margin: 0 6px 0 4px;
		opacity: 0.9;
	}

	.zoom-btn {
		width: 28px;
		height: 28px;
		border: none;
		background: transparent;
		color: var(--body-text-color-subdued);
		font-size: 16px;
		font-weight: 600;
		cursor: pointer;
		border-radius: 4px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
	}

	.zoom-btn:hover {
		background: color-mix(in srgb, var(--color-accent) 15%, transparent);
		color: var(--color-accent);
	}

	.fit-btn {
		font-size: 14px;
		margin-left: 4px;
		border-left: 1px solid color-mix(in srgb, var(--color-accent) 15%, transparent);
		padding-left: 8px;
		border-radius: 0 4px 4px 0;
	}

	.zoom-level {
		font-size: 11px;
		font-weight: 600;
		color: var(--body-text-color-subdued);
		min-width: 40px;
		text-align: center;
		font-family: 'SF Mono', Monaco, monospace;
	}

	.edges-svg {
		position: absolute;
		top: 0;
		left: 0;
		width: 4000px;
		height: 3000px;
		pointer-events: none;
		overflow: visible;
	}

	.edge-path {
		fill: none;
		stroke: var(--color-accent);
		transition: stroke 0.15s ease, stroke-width 0.15s ease, filter 0.15s ease;
		stroke-width: 2.5;
		stroke-linecap: round;
		transition: stroke 0.2s ease;
	}

	.edge-path.stale {
		stroke: var(--neutral-500);
	}

	.edge-path.will-run {
		stroke: var(--color-accent);
		stroke-width: 3;
		filter: drop-shadow(0 0 4px var(--color-accent));
	}

	.edge-fork {
		stroke-width: 2;
	}

	.node {
		position: absolute;
		background: linear-gradient(175deg, color-mix(in srgb, var(--block-background-fill) 92%, transparent) 0%, color-mix(in srgb, var(--block-background-fill) 92%, black 8%) 100%);
		border: 1px solid color-mix(in srgb, var(--color-accent) 20%, transparent);
		border-radius: 10px;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
		overflow: visible;
		cursor: default;
		transition: border-color 0.15s ease, box-shadow 0.15s ease;
	}

	.node.will-run {
		border-color: var(--color-accent);
		box-shadow: 0 0 20px color-mix(in srgb, var(--color-accent) 50%, transparent), 0 4px 20px rgba(0, 0, 0, 0.5);
	}

	.exec-time {
		position: absolute;
		top: -18px;
		right: 4px;
		font-size: 10px;
		font-weight: 500;
		color: var(--neutral-500);
		font-family: 'SF Mono', Monaco, monospace;
	}

	.exec-time.running {
		color: var(--color-accent);
	}

	.exec-time.error {
		color: var(--error-text-color);
		font-weight: 600;
	}

	.node-header {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 0 12px;
		height: 36px;
		background: color-mix(in srgb, var(--color-accent) 6%, transparent);
		border-bottom: 1px solid color-mix(in srgb, var(--color-accent) 10%, transparent);
	}

	.type-badge {
		font-size: 8px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		padding: 3px 8px;
		border-radius: 4px;
		color: var(--button-primary-text-color);
		flex-shrink: 0;
	}

	.node-name {
		flex: 1;
		font-size: 11px;
		font-weight: 600;
		color: var(--body-text-color);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.node-link {
		text-decoration: none;
		transition: color 0.15s;
	}

	.node-link:hover {
		color: var(--color-accent);
		text-decoration: underline;
	}

	.run-controls {
		position: relative;
		display: flex;
		align-items: center;
	}

	.run-btn {
		position: relative;
		font-size: 10px;
		color: var(--color-accent);
		cursor: pointer;
		padding: 2px 6px;
		border-radius: 4px 0 0 4px;
		border: 1px solid var(--color-accent);
		border-right: none;
		background: transparent;
		user-select: none;
		transition: all 0.15s;
	}

	.run-btn:hover {
		background: color-mix(in srgb, var(--color-accent) 20%, transparent);
	}

	.run-btn.running {
		animation: pulse 1.5s ease-in-out infinite;
	}

	.run-mode-toggle {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 16px;
		height: 18px;
		border: 1px solid var(--color-accent);
		border-radius: 0 4px 4px 0;
		color: var(--color-accent);
		cursor: pointer;
		transition: all 0.15s;
	}

	.run-mode-toggle:hover {
		background: color-mix(in srgb, var(--color-accent) 20%, transparent);
	}

	.run-mode-toggle svg {
		width: 8px;
		height: 5px;
	}

	.run-mode-menu {
		position: absolute;
		top: calc(100% + 4px);
		right: 0;
		background: color-mix(in srgb, var(--block-background-fill) 98%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 30%, transparent);
		border-radius: 6px;
		padding: 4px;
		min-width: 130px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
		z-index: 1000;
	}

	.run-mode-option {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		padding: 6px 8px;
		background: transparent;
		border: none;
		border-radius: 4px;
		color: var(--body-text-color-subdued);
		font-size: 11px;
		cursor: pointer;
		transition: all 0.15s;
		text-align: left;
	}

	.run-mode-option:hover {
		background: color-mix(in srgb, var(--color-accent) 15%, transparent);
		color: var(--body-text-color);
	}

	.run-mode-option.active {
		color: var(--color-accent);
		background: color-mix(in srgb, var(--color-accent) 10%, transparent);
	}

	.run-mode-icon {
		width: 10px;
		height: 10px;
		flex-shrink: 0;
	}

	.run-mode-icon-double {
		width: 12px;
	}

	.run-icon-svg {
		width: 14px;
		height: 12px;
		display: block;
	}

	@keyframes pulse {
		0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--color-accent) 40%, transparent); }
		50% { box-shadow: 0 0 0 4px transparent; }
	}

	.run-badge {
		position: absolute;
		top: -6px;
		right: -6px;
		min-width: 14px;
		height: 14px;
		background: var(--color-accent);
		color: var(--button-primary-text-color);
		font-size: 9px;
		font-weight: 700;
		border-radius: 7px;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0 3px;
	}

	.node-body {
		display: flex;
		justify-content: space-between;
		padding-top: 8px;
		padding-bottom: 8px;
		min-height: 30px;
		overflow: hidden;
	}

	.ports-left, .ports-right {
		display: flex;
		flex-direction: column;
		min-width: 0;
		max-width: 50%;
	}

	.ports-right {
		align-items: flex-end;
	}

	.port-row {
		display: flex;
		align-items: center;
		gap: 6px;
		height: 22px;
		padding: 0 10px;
		min-width: 0;
		max-width: 100%;
	}

	.port-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.port-dot.input {
		background: linear-gradient(135deg, var(--color-accent) 0%, color-mix(in srgb, var(--color-accent) 80%, black) 100%);
		box-shadow: 0 0 6px color-mix(in srgb, var(--color-accent) 50%, transparent);
	}

	.port-dot.output {
		background: linear-gradient(135deg, var(--color-accent-soft) 0%, var(--color-accent) 100%);
		box-shadow: 0 0 6px color-mix(in srgb, var(--color-accent-soft) 50%, transparent);
	}

	.port-label {
		font-size: 10px;
		font-weight: 500;
		color: var(--body-text-color-subdued);
		font-family: 'SF Mono', Monaco, monospace;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 100%;
	}

	.node-error {
		padding: 8px 10px;
		border-top: 1px solid color-mix(in srgb, var(--error-border-color) 20%, transparent);
		background: color-mix(in srgb, var(--error-background-fill) 5%, transparent);
		max-height: 200px;
		overflow-y: auto;
	}

	.node-error-label {
		font-size: 10px;
		font-weight: 600;
		color: var(--error-text-color);
		text-transform: uppercase;
		letter-spacing: 0.5px;
		margin-bottom: 4px;
	}

	.node-error-message {
		font-size: 11px;
		color: var(--error-border-color);
		font-family: 'SF Mono', Monaco, monospace;
		white-space: pre-wrap;
		word-break: break-word;
		line-height: 1.4;
	}

	.embedded-components {
		padding: 8px 10px;
		border-top: 1px solid color-mix(in srgb, var(--color-accent) 8%, transparent);
		max-height: 200px;
		overflow-y: auto;
	}

	.variants-accordion {
		border-top: 1px solid color-mix(in srgb, var(--color-accent) 8%, transparent);
		max-height: 350px;
		overflow-y: auto;
	}

	.variant-card {
		border-bottom: 1px solid color-mix(in srgb, var(--color-accent) 8%, transparent);
		cursor: pointer;
		transition: background 0.15s;
	}

	.variant-card:last-child {
		border-bottom: none;
	}

	.variant-card:hover {
		background: color-mix(in srgb, var(--color-accent) 3%, transparent);
	}

	.variant-card.selected {
		background: color-mix(in srgb, var(--color-accent) 6%, transparent);
	}

	.variant-header {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
	}

	.variant-radio {
		font-size: 12px;
		color: var(--color-accent);
		width: 14px;
		flex-shrink: 0;
	}

	.variant-radio.checked {
		font-weight: 700;
	}

	.variant-name {
		font-size: 11px;
		font-weight: 500;
		color: var(--body-text-color-subdued);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.variant-card.selected .variant-name {
		color: var(--color-accent);
	}

	.variant-inputs {
		padding: 0 12px 10px 34px;
	}

	.result-selector {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		padding: 6px 10px;
		background: color-mix(in srgb, var(--color-accent) 5%, transparent);
		border-top: 1px solid color-mix(in srgb, var(--color-accent) 10%, transparent);
	}

	.result-nav {
		width: 20px;
		height: 20px;
		border: none;
		background: color-mix(in srgb, var(--color-accent) 10%, transparent);
		color: var(--color-accent);
		font-size: 14px;
		font-weight: 600;
		border-radius: 4px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
	}

	.result-nav:hover:not(:disabled) {
		background: color-mix(in srgb, var(--color-accent) 25%, transparent);
	}

	.result-nav:disabled {
		opacity: 0.3;
		cursor: not-allowed;
	}

	.result-counter {
		font-size: 11px;
		font-weight: 600;
		color: var(--body-text-color-subdued);
		font-family: 'SF Mono', Monaco, monospace;
		min-width: 32px;
		text-align: center;
	}
</style>
