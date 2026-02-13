export interface Port {
	name: string;
	history_count?: number;
}

export interface GradioComponentData {
	component: string;
	type: string;
	port_name: string;
	props: Record<string, any>;
	value?: any;
}

export interface MapItem {
	index: number;
	preview: string;
	output: string | null;
	is_audio_output: boolean;
	status?: string;
}

export interface ItemListItem {
	index: number;
	fields: Record<string, any>;
}

export interface NodeVariant {
	name: string;
	input_components: GradioComponentData[];
	output_components: GradioComponentData[];
}

export interface GraphNode {
	id: string;
	name: string;
	embed_inputs?: boolean;
	type: string;
	url?: string;
	inputs: Port[];
	outputs: string[];
	input_components?: GradioComponentData[];
	output_components?: GradioComponentData[];
	x: number;
	y: number;
	status: string;
	is_output_node: boolean;
	is_input_node: boolean;
	is_map_node?: boolean;
	map_items?: MapItem[];
	map_item_count?: number;
	item_list_schema?: GradioComponentData[];
	item_list_items?: ItemListItem[];
	variants?: NodeVariant[];
	selected_variant?: number;
}

export interface GraphEdge {
	id: string;
	from_node: string;
	from_port: string;
	to_node: string;
	to_port: string;
	is_scattered?: boolean;
	is_gathered?: boolean;
}

export interface CanvasData {
	name: string;
	nodes: GraphNode[];
	edges: GraphEdge[];
	inputs?: Record<string, Record<string, string>>;
	session_id?: string;
	run_id?: string;
	completed_node?: string;
}

