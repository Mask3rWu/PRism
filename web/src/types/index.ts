export interface Project {
  id: number;
  name: string;
  repo_owner: string;
  repo_name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreatePayload {
  name: string;
  repo_owner: string;
  repo_name: string;
  pat: string;
  description: string;
}

export interface ProjectUpdatePayload {
  description?: string;
  pat?: string;
}
