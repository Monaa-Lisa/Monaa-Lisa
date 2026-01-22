export interface Paper {
  id?: number | string;
  entry_id?: string;
  title?: string;
  authors?: string | string[];
  summary?: string;
  published?: string | null; // Date string
  category?: string;
  url?: string;
  tsne?: [number, number] | { x: number; y: number } | { tsne1: number; tsne2: number };
  added?: string;
  cluster?: string;
}

export interface PapersResponse {
  items: Paper[];
  total: number;
}

export interface PaperCitation {
  belonging_paper_entry_id: string;
  cited_paper_entry_id: string;
}

export interface PaperReference {
  belonging_paper_entry_id: string;
  referenced_paper_entry_id: string;
}

export interface Citation {
  id: number;
  belonging_paper_entry_id: string;
  semanticscholar_obj: Record<string, any>;
}

export interface Reference {
  id: number;
  belonging_paper_entry_id: string;
  semanticscholar_obj: Record<string, any>;
}

export interface Relation {
  source_id: string;
  target_id: string;
  confidence: number;
}

export interface Hull {
  path: [number, number][];
  color: string;
  strokeColor: string;
  label: string;
  cx: number;
  cy: number;
}

