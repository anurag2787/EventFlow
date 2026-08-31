// Shared TypeScript types for EventFlow

export interface Organization {
  id: number;
  name: string;
}

export interface Repository {
  id: number;
  organization: Organization;
  name: string;
  external_id: string;
  provider: string;
}

export interface UserActor {
  id: number;
  username: string;
}

export interface ActivityItem {
  id: number;
  repository: Repository;
  actor: UserActor | null;
  activity_type: string;
  target_id: string;
  source_provider: string;
  source_event_id: string;
  source_event_type: string;
  source_url: string;
  metadata: Record<string, any>;
  created_at: string;
}

export interface ActivityStats {
  total_activities: number;
  by_type: Record<string, number>;
  by_repository: Record<string, number>;
}
