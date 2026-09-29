export interface ChatRequest {
  question: string;
}

export interface Source {
  document_id: string;
  filename: string;
  page_number?: number;
  chunk_id?: string;
  text?: string;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  metadata?: Record<string, unknown>;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  status: string;
}

export interface DocumentStatusResponse {
  id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  file_size: number;
  status: string;
  chunk_count?: number;
  error_message?: string;
  allowed_roles?: string[];
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: string; // 'user' | 'assistant'
  content: string;
  metadata?: {
    route?: string;
    router_reason?: string;
    router_confidence?: number;
    sources?: Source[];
    [key: string]: unknown;
  };
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface PermissionRef {
  name: string;
}

export interface RoleRef {
  name: string;
  permissions: PermissionRef[];
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  roles: RoleRef[];
}
