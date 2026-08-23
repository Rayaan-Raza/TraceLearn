export type ProblemSummary = {
  id: string
  title: string
  function_name: string
  concept_tags: string[]
}

export type ProblemDetail = ProblemSummary & {
  slug: string
  description: string
  prerequisite_tags: string[]
  starter_code: string
  test_cases: { id: string; name: string; test_type: string; input_json: unknown }[]
}

export type StudentOption = {
  id: number
  display_name: string
}

export type TestResultSummary = {
  test_case_id: string
  test_case_name?: string
  passed: boolean
  stdout?: string
  stderr?: string
  actual_output_json?: unknown
  expected_output_json?: unknown
  error_type?: string | null
}

export type DiagnosisResult = {
  mode: 'current_only' | 'history_aware'
  primary_misconception: string
  primary_confidence: number
  alternative_misconception?: string | null
  alternative_confidence?: number | null
  uncertainty_level?: string
  requires_teacher_review?: boolean
  explanation?: unknown
}

export type EvidenceItem = {
  id: number
  submission_id: number
  source_type: string
  evidence_code: string
  misconception_id?: string | null
  direction: string
  weight: number
  description: string
  details_json: string
}

export type HintPayload = {
  text?: string
  level?: number
  hint_type?: string
}

export type DiagnosisBrief = DiagnosisResult & { id?: number }

export type RunAnalyzeResponse = {
  submission_id: number
  attempt_number?: number
  execution_status?: string
  stdout?: string
  stderr?: string
  runtime_ms?: number | null
  test_results: TestResultSummary[]
  current_only?: DiagnosisBrief | null
  history_aware?: DiagnosisBrief | null
  evidence_count?: number
  diagnoses?: DiagnosisResult[]
  evidence?: EvidenceItem[]
  hint?: HintPayload | string | null
}

export type TimelineEvent = {
  id: string
  timestamp: string
  event_type: string
  problem_id?: string
  submission_id?: number
  summary: string
  details?: Record<string, unknown>
}

export type LearnerStateRow = {
  id: number
  student_id: number
  misconception_id: string
  state: string
  confidence?: number
  updated_at: string
}

export type ExperimentMetrics = {
  name: string
  value: number | string
  notes?: string
}

export type TeacherReviewRow = {
  id: number
  submission_id: number
  diagnosis_id?: number | null
  action?: string
  notes?: string
  created_at?: string
}


export type TimelineEntry = {
  submission_id: number
  problem_id: string
  attempt_number: number
  submitted_at: string
  execution_status?: string | null
  primary_diagnosis?: string | null
  state_transitions?: { misconception_id: string; old_state: string; new_state: string; timestamp: string }[]
}

export type LearnerProfile = {
  student_id: number
  display_name: string
  learner_states: LearnerStateRow[]
}

